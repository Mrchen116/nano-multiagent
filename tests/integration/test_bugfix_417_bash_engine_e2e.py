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
import os
import signal
import subprocess
import time
import uuid
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


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@pytest.mark.asyncio
async def test_interrupt_reaps_foreground_subprocess_and_self_heals(
    tmp_path: Path,
) -> None:
    """bugfix-417-M5 (#114) DONE hard gate, end-to-end through build_kernel.

    Drive a real foreground bash command that spawns a uniquely-tagged sleep
    child, then call ``kernel.interrupt`` while it is in-flight. Assert the three
    observable M5 contracts:
      1. the subprocess tree is killed — no orphan sleep survives;
      2. the in-flight bash tool_call is closed in the session stream as
         ``interrupted`` (not left running, not marked success/timeout);
      3. the same session self-heals — a subsequent turn reaches completed.
    """
    # Unique marker encoded into the sleep's OWN argv (a fractional duration), so
    # ``pgrep -f`` finds exactly this test's child and not unrelated host processes.
    # A trailing ``# comment`` would NOT work: bash strips it, leaving argv ``sleep
    # 30`` with no marker.  ``sleep 30.<unique>`` keeps the marker in the process
    # arguments while still sleeping ~30s.
    unique = uuid.uuid4().int % 1_000_000
    marker = f"30.{unique:06d}"
    command = f"sleep {marker}"

    kernel = _build(tmp_path, _BashThenStopLLM(command=command, timeout=None))
    session_id: str | None = None
    events: list[dict] = []
    stop = asyncio.Event()
    collector: asyncio.Task | None = None
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        session_id = session.session_id
        collector = asyncio.create_task(
            _collect_stream(kernel, session_id, stop, events)
        )

        run = kernel.submit(
            session_id=session_id,
            parts=[{"type": "text", "text": "run a long command"}],
            workspace_root=tmp_path,
        )

        # Wait until the foreground sleep child is actually spawned.
        def _find_marker_pids() -> list[int]:
            out = subprocess.run(
                ["pgrep", "-f", marker],
                capture_output=True,
                text=True,
            )
            return [int(p) for p in out.stdout.split() if p.strip().isdigit()]

        deadline = time.monotonic() + 10.0
        child_pids: list[int] = []
        while time.monotonic() < deadline:
            child_pids = _find_marker_pids()
            if child_pids:
                break
            await asyncio.sleep(0.1)
        assert child_pids, "foreground sleep child never spawned"

        # Interrupt the active run — must reap the subprocess tree.
        interrupted = kernel.interrupt(session_id)
        assert interrupted == run.run_id

        # 1. No orphan: the marked sleep process(es) die promptly.
        reap_deadline = time.monotonic() + 10.0
        while time.monotonic() < reap_deadline:
            if not _find_marker_pids():
                break
            await asyncio.sleep(0.1)
        survivors = _find_marker_pids()
        assert not survivors, (
            f"orphan subprocess(es) survived interrupt: {survivors} (marker {marker})"
        )

        # 3. Self-heal: a new turn in the same session reaches a terminal state.
        run2 = kernel.submit(
            session_id=session_id,
            parts=[{"type": "text", "text": "are you back"}],
            workspace_root=tmp_path,
        )
        heal_deadline = time.monotonic() + 15.0
        while time.monotonic() < heal_deadline:
            record = kernel.get_run(run2.run_id)
            if record and record.status in {"completed", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.05)
        record2 = kernel.get_run(run2.run_id)
        assert record2 is not None and record2.status == "completed", (
            f"session did not self-heal after interrupt: {record2!r}"
        )

        # 2. The interrupted run reaches the cancelled terminal state.
        record1 = kernel.get_run(run.run_id)
        assert record1 is not None and record1.status == "cancelled", (
            f"interrupted run did not reach cancelled: {record1!r}"
        )

        await asyncio.sleep(0.3)
        stop.set()
    finally:
        # Belt-and-suspenders: kill any surviving marked process so a failing test
        # never leaks a 30s sleep onto the host.
        with contextlib.suppress(Exception):
            leftover = subprocess.run(
                ["pgrep", "-f", marker], capture_output=True, text=True
            )
            for p in leftover.stdout.split():
                if p.strip().isdigit():
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(int(p), signal.SIGKILL)
        if collector is not None:
            stop.set()
            if session_id is not None:
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
        kernel.close()

    # 4. The in-flight bash tool_call is recovered as 'interrupted' in the session
    # transcript (kernel-level evidence; the Gateway projects this into the IM
    # "已中断" badge via run_terminal_reconcile). Scan the session JSONL for the
    # tool_call_recovery entry the runtime's finally path wrote.
    import json

    jsonl_files = list(tmp_path.rglob("*.jsonl"))
    recoveries: list[dict] = []
    for jf in jsonl_files:
        for line in jf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            with contextlib.suppress(json.JSONDecodeError):
                entry = json.loads(line)
                if entry.get("type") == "tool_call_recovery":
                    recoveries.append(entry)
    assert recoveries, (
        "no tool_call_recovery entry written for the interrupted in-flight bash "
        f"tool_call; jsonl files scanned: {[str(f) for f in jsonl_files]}"
    )
    assert any(r.get("reason") == "interrupted" for r in recoveries), (
        f"in-flight bash tool_call not recovered as 'interrupted': {recoveries!r}"
    )
