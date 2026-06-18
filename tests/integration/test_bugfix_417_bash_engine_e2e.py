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
