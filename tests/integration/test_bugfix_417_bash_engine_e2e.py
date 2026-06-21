"""bugfix-417-M4 R4: end-to-end guard for the unified bash engine (decision 8).

This incident's deepest root cause was "all unit tests green / live all red": M2's
killpg and M3's bash heartbeat / reason_code each had isolated, passing unit tests,
but production bash runs through ``build_kernel`` → ``ShellRunner`` (the foreground
``_run_foreground`` path), while those changes landed on the dead ``run_stream`` /
``_run_legacy_sync`` path. Isolated unit tests could not prove the heartbeat actually
reaches a watchdog, because that path spans five layers:

    build_kernel → ShellRunner → ctx.emit_execution_event → tools/registry executor
    (run_coroutine_threadsafe bridge) → realtime_stream publisher → kernel.stream

These two tests drive a real ``build_kernel`` wiring end-to-end and assert the two
observable contracts that B1/C1 broke in live:
  1. a silent long-running bash command makes ``kernel.stream`` emit ``run_heartbeat``
     (liveness reaches the stream → watchdogs see it → no false reap), and
  2. a bash command that hits its own ``timeout`` surfaces ``reason_code=tool_timeout``
     on the ``tool_end`` stream event (→ IM ``tool_call.reason`` → "执行超时" badge).

They are the DONE hard gate that replaces "trust the human live re-test" with an
automated regression. A fake LLM client issues the bash tool_call so no real upstream
is needed (not an e2e-marked test — no external services).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

_SUPPRESS_STREAM_STOP = (asyncio.TimeoutError, asyncio.CancelledError)

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import LLMConfig, LLMModel, LLMProvider, build_kernel


def _llm_config() -> LLMConfig:
    return LLMConfig(
        provider="openai_compat",
        model="codex_oauth:gpt-5.5",
        base_url="http://127.0.0.1:4000",
        default_model="codex_oauth:gpt-5.5",
        providers=(
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(LLMModel(name="codex_oauth:gpt-5.5"),),
            ),
        ),
    )


async def _allow_all(tool, input, ctx) -> Any:  # noqa: ANN001
    from agent.platform.permissions.broker import PermissionDecision

    return PermissionDecision(behavior="allow")


class _BashThenStopLLM:
    """First turn: emit one bash tool_call. After the tool result: stop.

    Mirrors the real provider's two-step tool loop so build_kernel actually executes
    the bash tool through the production ShellRunner foreground path.
    """

    def __init__(self, *, command: str, timeout: float | None) -> None:
        self._command = command
        self._timeout = timeout
        self._calls = 0

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        self._calls += 1
        first = self._calls == 1
        return self._stream(first)

    async def _stream(self, first: bool):
        # The loop treats a message with empty content AND finish_reason set as a
        # terminal metadata frame (it skips its body). So the tool_call must ride a
        # frame with finish_reason=None, followed by a separate terminal frame that
        # carries finish_reason — mirroring the real provider's streamed shape.
        if first:
            args: dict[str, Any] = {"command": self._command}
            if self._timeout is not None:
                args["timeout"] = self._timeout
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(call_id="call_1", name="bash", arguments=args),
                ),
                finish_reason=None,
            )
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="tool_calls",
                usage=None,
            )
        else:
            yield LLMMessage(
                role="assistant",
                content="done",
                finish_reason=None,
            )
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=None,
            )


def _build(tmp_path: Path, llm_client: Any) -> Any:
    return build_kernel(
        llm=_llm_config(),
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=llm_client,
    )


async def _collect_stream(
    kernel: Any, session_id: str, stop: asyncio.Event, sink: list[dict]
) -> None:
    async for event in kernel.stream(session_id):
        if stop.is_set():
            break
        sink.append(event)


async def _run_turn_and_collect(
    kernel: Any, session_id: str, tmp_path: Path, text: str
) -> list[dict]:
    """Submit one turn, collect every stream event until the run reaches a terminal
    status (plus a short drain for trailing events), then tear the collector down.

    Avoids the fragile "stop after N seconds" race: the collector runs concurrently
    with the run and is stopped only once we have observed the terminal run_status.
    """
    events: list[dict] = []
    stop = asyncio.Event()
    collector = asyncio.create_task(_collect_stream(kernel, session_id, stop, events))
    run = kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": text}],
        workspace_root=tmp_path,
    )
    deadline = asyncio.get_event_loop().time() + 20.0
    while asyncio.get_event_loop().time() < deadline:
        record = kernel.get_run(run.run_id)
        if record and record.status in {"completed", "failed", "cancelled"}:
            break
        await asyncio.sleep(0.05)
    # Let trailing events (turn_end / terminal run_status) flush into the stream.
    await asyncio.sleep(0.5)
    stop.set()
    # Unblock the collector's pending anext with one more event, then drain it.
    kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": "noop"}],
        workspace_root=tmp_path,
    )
    with contextlib.suppress(*_SUPPRESS_STREAM_STOP):
        await asyncio.wait_for(collector, timeout=3.0)
    if not collector.done():
        collector.cancel()
        with contextlib.suppress(*_SUPPRESS_STREAM_STOP):
            await collector
    return events


@pytest.mark.asyncio
async def test_silent_long_bash_emits_run_heartbeat_through_build_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silent long bash command must make kernel.stream emit run_heartbeat (B1).

    Heartbeat interval is patched small so a ~1.5s sleep yields several ticks well
    within the foreground budget (no auto-background). Pre-M4 the production
    foreground path emitted zero events for the whole run.
    """
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._FOREGROUND_HEARTBEAT_INTERVAL", 0.2
    )
    kernel = _build(tmp_path, _BashThenStopLLM(command="sleep 1.5", timeout=None))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a slow command"
        )
    finally:
        kernel.close()

    heartbeats = [e for e in events if e.get("event") == "run_heartbeat"]
    assert heartbeats, (
        "no run_heartbeat reached kernel.stream during a silent long bash command — "
        f"liveness chain broken; saw events: {[e.get('event') for e in events]}"
    )


@pytest.mark.asyncio
async def test_bash_timeout_surfaces_tool_timeout_reason_through_build_kernel(
    tmp_path: Path,
) -> None:
    """A bash command hitting its own timeout must surface reason_code=tool_timeout
    on the tool_end stream event (C1: live had reason=null).
    """
    kernel = _build(tmp_path, _BashThenStopLLM(command="sleep 30", timeout=0.5))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a command that times out"
        )
    finally:
        kernel.close()

    tool_ends = [e for e in events if e.get("event") == "tool_end"]
    assert tool_ends, (
        f"no tool_end event seen; events: {[e.get('event') for e in events]}"
    )
    bash_end = next((e for e in tool_ends if e.get("name") == "bash"), None)
    assert bash_end is not None, f"no bash tool_end; tool_ends: {tool_ends}"
    assert bash_end.get("reason_code") == "tool_timeout", (
        f"bash timeout did not surface reason_code=tool_timeout: {bash_end!r}"
    )


# --- bugfix-417-M6 (#115): generic (non-bash) tool liveness --------------------
#
# Pre-M6 only bash emitted execution heartbeats; any other long-running to_thread
# tool (web_fetch etc.) produced zero events for its whole duration → both watchdogs
# saw "output silent" and reaped the live run. M6 lifts liveness to the executor's
# generic layer (an await-bound ticker wrapping to_thread(tool.run)), so EVERY long
# tool inherits it. This guard drives a real build_kernel wiring with a non-bash tool
# that deliberately blocks WITHOUT calling ctx.emit_execution_event, and asserts the
# generic ticker still makes kernel.stream emit run_heartbeat — the DONE hard gate
# that pins the generalization, not just bash's own phase:running path.


class _SlowSleepTool:
    """A non-bash tool whose run() blocks in a thread WITHOUT emitting any heartbeat.

    Satisfies the SDK Tool Protocol structurally (name/description/input_schema/run).
    It calls neither ctx.emit_execution_event nor any phase event, so any run_heartbeat
    reaching the stream proves the executor's generic liveness ticker (not the tool)
    produced it. Mirrors the real gap: web_fetch et al. are silent during execution.
    """

    name = "slow_sleep"
    description = "Sleep for `seconds` seconds without emitting progress (test tool)."
    input_schema = {
        "type": "object",
        "properties": {"seconds": {"type": "number"}},
        "required": ["seconds"],
    }

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:  # noqa: ANN401
        time.sleep(float(args["seconds"]))
        return {"slept": args["seconds"]}


class _SlowToolThenStopLLM:
    """First turn: emit one slow_sleep tool_call. After the tool result: stop.

    Same two-step streamed tool-loop shape as _BashThenStopLLM so build_kernel runs the
    non-bash tool through the production executor path.
    """

    def __init__(self, *, seconds: float) -> None:
        self._seconds = seconds
        self._calls = 0

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        self._calls += 1
        return self._stream(self._calls == 1)

    async def _stream(self, first: bool):
        if first:
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="call_1",
                        name="slow_sleep",
                        arguments={"seconds": self._seconds},
                    ),
                ),
                finish_reason=None,
            )
            yield LLMMessage(
                role="assistant", content="", finish_reason="tool_calls", usage=None
            )
        else:
            yield LLMMessage(role="assistant", content="done", finish_reason=None)
            yield LLMMessage(
                role="assistant", content="", finish_reason="stop", usage=None
            )


@pytest.mark.asyncio
async def test_silent_non_bash_tool_emits_run_heartbeat_through_build_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silent long non-bash tool must make kernel.stream emit run_heartbeat (#115).

    The executor's generic ticker interval is patched small so a ~1.5s sleep yields
    several ticks. Pre-M6 this tool produced zero events for its whole run.
    """
    monkeypatch.setattr(
        "agent.core.tools.registry._GENERIC_EXECUTION_HEARTBEAT_INTERVAL", 0.2
    )
    kernel = build_kernel(
        llm=_llm_config(),
        tools=[_SlowSleepTool()],
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=_SlowToolThenStopLLM(seconds=1.5),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a slow non-bash tool"
        )
    finally:
        kernel.close()

    heartbeats = [e for e in events if e.get("event") == "run_heartbeat"]
    assert heartbeats, (
        "no run_heartbeat reached kernel.stream during a silent long non-bash tool — "
        "generic executor liveness not wired; saw events: "
        f"{[e.get('event') for e in events]}"
    )
    # The heartbeat must come from the generic executing-phase ticker, not bash.
    assert any(e.get("phase") == "executing" for e in heartbeats), (
        f"expected an executing-phase heartbeat from the generic ticker: {heartbeats!r}"
    )


# --- bugfix-417-M7 (decision 12): foreground bash single-channel DONE hard gate ----
#
# round-6 acceptance proved (proxy log) that a foreground bash timeout produced BOTH a
# tool_result AND a <task-notification> — the dual-channel bug. M7 removes foreground
# bash from BackgroundTaskRegistry entirely, so the notification channel is physically
# unreachable for foreground commands. These two guards replace "trust the human live
# re-test" with an automated regression driven through a real build_kernel:
#   1. a foreground bash that times out → exactly one channel (tool result with the
#      timeout reason), and NO <task-notification> is ever injected into the session;
#   2. a run_in_background command → still gets its <task-notification> (the real
#      background path must not regress).
#
# Observability: the fake LLM records every request's message text. A <task-notification>
# is delivered by injecting it into the parent session's next input, so it would surface
# as a message in a subsequent generate() request. Asserting its absence/presence across
# all captured requests is the cross-layer observable.


class _RecordingBashThenStopLLM:
    """Like _BashThenStopLLM but records the text of every message it is asked to
    generate against, so a test can assert whether a <task-notification> was ever
    injected into the session input."""

    def __init__(
        self, *, command: str, timeout: float | None, run_in_background: bool = False
    ) -> None:
        self._command = command
        self._timeout = timeout
        self._run_in_background = run_in_background
        self._calls = 0
        # Texts of non-system messages only (the system prompt documents the
        # <task-notification> mechanism in prose, so it must be excluded — only an
        # ACTUAL injected notification, a user-role message carrying a <task-id>,
        # counts as "the notification channel fired").
        self.seen_message_texts: list[str] = []

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        for message in request.messages:
            if getattr(message, "role", None) == "system":
                continue
            content = getattr(message, "content", "")
            if isinstance(content, str):
                self.seen_message_texts.append(content)
        self._calls += 1
        return self._stream(self._calls == 1)

    async def _stream(self, first: bool):
        if first:
            args: dict[str, Any] = {"command": self._command}
            if self._timeout is not None:
                args["timeout"] = self._timeout
            if self._run_in_background:
                args["run_in_background"] = True
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(call_id="call_1", name="bash", arguments=args),
                ),
                finish_reason=None,
            )
            yield LLMMessage(
                role="assistant", content="", finish_reason="tool_calls", usage=None
            )
        else:
            # Any subsequent turn (including one woken by a <task-notification>
            # submit) just stops — but its request messages were already recorded.
            yield LLMMessage(role="assistant", content="done", finish_reason=None)
            yield LLMMessage(
                role="assistant", content="", finish_reason="stop", usage=None
            )


def _seen_any_task_notification(llm: _RecordingBashThenStopLLM) -> bool:
    # An actual injected notification carries both the wrapper and a <task-id> tag
    # (build_task_notification_xml). The system prompt's prose mention of
    # "<task-notification>" is excluded both here (needs <task-id>) and at capture
    # (system-role messages are skipped).
    return any(
        "<task-notification>" in text and "<task-id>" in text
        for text in llm.seen_message_texts
    )


@pytest.mark.asyncio
async def test_foreground_bash_timeout_emits_no_task_notification_through_build_kernel(
    tmp_path: Path,
) -> None:
    """A foreground bash command that hits its own timeout must surface its result
    ONLY via the tool result (reason=tool_timeout) — never an additional
    <task-notification>. This is the M7 dual-channel negative invariant, proven
    end-to-end through build_kernel (foreground bash never enters BackgroundTaskRegistry,
    so the notification path is structurally unreachable)."""
    llm = _RecordingBashThenStopLLM(command="sleep 30", timeout=0.5)
    kernel = _build(tmp_path, llm)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a command that times out"
        )
        # Give any (erroneous) async notification delivery a chance to land before we
        # assert its absence — a false negative would otherwise be a flaky pass.
        await asyncio.sleep(0.5)
    finally:
        kernel.close()

    # Channel 1 (tool result) fired with the timeout reason.
    bash_end = next(
        (e for e in events if e.get("event") == "tool_end" and e.get("name") == "bash"),
        None,
    )
    assert bash_end is not None, (
        f"no bash tool_end event; events: {[e.get('event') for e in events]}"
    )
    assert bash_end.get("reason_code") == "tool_timeout", (
        f"foreground timeout did not surface via the tool result: {bash_end!r}"
    )
    # Channel 2 (notification) must NOT have fired — neither in the stream nor injected
    # into any subsequent LLM request.
    assert not _seen_any_task_notification(llm), (
        "a <task-notification> was injected for a FOREGROUND bash timeout — the "
        "dual-channel bug is back (foreground must be single-channel)"
    )
    assert not any("<task-notification>" in str(e.get("text", "")) for e in events), (
        "a <task-notification> surfaced on the stream for a foreground bash timeout"
    )


@pytest.mark.asyncio
async def test_run_in_background_command_still_emits_task_notification(
    tmp_path: Path,
) -> None:
    """A run_in_background bash command must still deliver its <task-notification>
    when it completes — the real background path must not regress under M7."""
    llm = _RecordingBashThenStopLLM(
        command="echo hi", timeout=None, run_in_background=True
    )
    kernel = _build(tmp_path, llm)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a background command"
        )
        # The background task completes async; its notification is delivered by
        # submitting (or injecting) into the parent session, which drives another
        # generate() call. Poll the recorded requests for the notification.
        deadline = asyncio.get_event_loop().time() + 5.0
        while asyncio.get_event_loop().time() < deadline:
            if _seen_any_task_notification(llm):
                break
            await asyncio.sleep(0.1)
    finally:
        kernel.close()

    # The background completion delivered a <task-notification> into the session —
    # the real background notification path is intact under M7.
    assert _seen_any_task_notification(llm), (
        "run_in_background command completed but no <task-notification> was delivered "
        "— the real background notification path regressed under M7"
    )
