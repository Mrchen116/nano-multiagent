"""bugfix-417-M3 R4: Gateway run-idle watchdog is a pure liveness detector.

Supersedes bugfix-410-M2 R2's permission-specific exemption (#98). The kernel now
emits a periodic ``run_heartbeat`` during every alive-but-quiet window (silent long
tool / awaiting LLM / parked on a permission decision), all on the same stream. ANY
event — business OR heartbeat — resets the idle timer, so there is no ``permission_request``
exemption branch anymore: a parked permission wait survives because its heartbeat keeps
arriving, and a genuinely dead run (heartbeat stopped, e.g. crash) is still reaped after
the timeout. When the watchdog does reap, it reports ``reason="stalled"`` (中断), distinct
from a tool hitting its own deadline (``tool_timeout``/执行超时).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel, _make_stream_event


class _ControlledStreamKernel:
    """Kernel double whose stream yields from an asyncio.Queue under test control.

    ``cancel`` records calls so the test can assert the watchdog did/did not fire.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.cancel_calls: list[str] = []

    def push(self, event: dict[str, Any]) -> None:
        self._queue.put_nowait(_make_stream_event(dict(event)))

    def end(self) -> None:
        self._queue.put_nowait(None)

    def cancel(self, run_id: str) -> None:
        self.cancel_calls.append(run_id)

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        async def _gen() -> AsyncIterator[dict[str, Any]]:
            while True:
                item = await self._queue.get()
                if item is None:
                    return
                yield item

        return _gen()


def _build_pipeline(
    kernel: Any, *, idle_timeout: float, observer: Any = None
) -> InboundPipeline:
    return InboundPipeline(
        kernel=kernel,
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a", workspace_root=Path("/tmp"), title="Agent A"
            ),
        ),
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        run_idle_timeout_seconds=idle_timeout,
        kernel_event_observer=observer,
    )


async def test_permission_pending_kept_alive_by_heartbeat() -> None:
    """A parked permission wait survives a long decision because its run_heartbeat keeps
    arriving (no permission-specific exemption branch) — each heartbeat resets the timer."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.15)

    async def _drive() -> None:
        # 1. Run parks awaiting a permission decision.
        kernel.push(
            {"event": "permission_request", "run_id": "run-1", "request_id": "p1"}
        )
        # 2. The kernel emits periodic liveness heartbeats while parked — each one well
        #    inside the 0.15s idle window, so the run is never reaped.
        for _ in range(5):
            await asyncio.sleep(0.08)
            kernel.push(
                {"event": "run_heartbeat", "run_id": "run-1", "source": "permission"}
            )
        # 3. User decides → the run resumes and completes.
        kernel.push({"event": "tool_start", "run_id": "run-1", "call_id": "c1"})
        kernel.push(
            {
                "event": "run_status",
                "run_id": "run-1",
                "status": "completed",
                "output_text": "ok",
            }
        )
        kernel.end()

    driver = asyncio.create_task(_drive())
    run_state, _reply = await pipeline._await_terminal_run_async(
        kernel_session_id="sess-1", run_id="run-1"
    )
    await driver

    assert kernel.cancel_calls == [], (
        "a permission wait kept alive by heartbeats must not be reaped"
    )
    assert run_state.get("status") == "completed"


async def test_permission_pending_reaped_when_heartbeat_stops() -> None:
    """Decision 4 crash detection: if the heartbeat stops (Gateway/kernel crash) a parked
    permission wait is reaped after the idle window — no permanently-exempt ghost."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    async def _drive() -> None:
        kernel.push(
            {"event": "permission_request", "run_id": "run-c", "request_id": "pc"}
        )
        # Heartbeat stops here (simulated crash) — no further events. Watchdog must reap.

    driver = asyncio.create_task(_drive())
    with pytest.raises(TimeoutError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-c", run_id="run-c"
        )
    await driver

    assert kernel.cancel_calls == ["run-c"], (
        "a permission wait whose heartbeat stopped must still be reaped"
    )


async def test_idle_watchdog_still_fires_without_permission_request() -> None:
    """A genuinely stalled run (no permission_request) must still be cancelled."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    # Never push any event — the stream stalls from the start (true hang).
    with pytest.raises(TimeoutError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-2", run_id="run-2"
        )

    assert kernel.cancel_calls == ["run-2"], (
        "a stalled run with no permission_request must still hit the watchdog"
    )


async def test_post_decision_stall_is_reaped() -> None:
    """After the user decides and the tool starts, a fresh stall (heartbeat stops) is
    reaped — liveness is uniform, no leftover exemption keeps a dead run alive."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    async def _drive() -> None:
        kernel.push(
            {"event": "permission_request", "run_id": "run-3", "request_id": "p3"}
        )
        # A couple of heartbeats keep it alive during the wait.
        await asyncio.sleep(0.06)
        kernel.push(
            {"event": "run_heartbeat", "run_id": "run-3", "source": "permission"}
        )
        # User allows → tool_start; then the tool hangs with NO further heartbeat.
        kernel.push({"event": "tool_start", "run_id": "run-3", "call_id": "c3"})
        # Do NOT end the stream — the post-decision stall must be reaped.

    driver = asyncio.create_task(_drive())
    with pytest.raises(TimeoutError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-3", run_id="run-3"
        )
    await driver

    assert kernel.cancel_calls == ["run-3"], (
        "a post-decision stall with no heartbeat must hit the watchdog"
    )


async def test_watchdog_timeout_emits_stalled_reconcile() -> None:
    """When the watchdog reaps a run that lost liveness, the pipeline must feed a
    run_terminal_reconcile(stalled) event — distinct from a tool's own deadline
    (tool_timeout). bugfix-417-M3 decision 5."""
    kernel = _ControlledStreamKernel()
    observed: list[dict[str, Any]] = []
    pipeline = _build_pipeline(
        kernel, idle_timeout=0.1, observer=lambda ev: observed.append(dict(ev))
    )

    # Stream stalls from the start → watchdog fires.
    with pytest.raises(TimeoutError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-1", run_id="run-1"
        )

    reconciles = [e for e in observed if e.get("event") == "run_terminal_reconcile"]
    assert len(reconciles) == 1
    assert reconciles[0]["run_id"] == "run-1"
    assert reconciles[0]["reason"] == "stalled"


async def test_heartbeat_resets_idle_timer_for_silent_long_tool() -> None:
    """A silent long tool keeps the run alive purely via run_heartbeat — no business
    event needed (Req B: 静默长命令不被误杀)."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.15)

    async def _drive() -> None:
        kernel.push({"event": "tool_start", "run_id": "run-h", "call_id": "ch"})
        # No tool output for a long time, only heartbeats — must not be reaped.
        for _ in range(5):
            await asyncio.sleep(0.08)
            kernel.push({"event": "run_heartbeat", "run_id": "run-h", "source": "tool"})
        kernel.push(
            {
                "event": "run_status",
                "run_id": "run-h",
                "status": "completed",
                "output_text": "done",
            }
        )
        kernel.end()

    driver = asyncio.create_task(_drive())
    run_state, _reply = await pipeline._await_terminal_run_async(
        kernel_session_id="sess-h", run_id="run-h"
    )
    await driver

    assert kernel.cancel_calls == []
    assert run_state.get("status") == "completed"


async def test_terminal_failed_status_emits_interrupted_reconcile() -> None:
    """An abnormal terminal run_status (failed) must feed reconcile(interrupted)."""
    kernel = _ControlledStreamKernel()
    observed: list[dict[str, Any]] = []
    pipeline = _build_pipeline(
        kernel, idle_timeout=5.0, observer=lambda ev: observed.append(dict(ev))
    )

    async def _drive() -> None:
        kernel.push(
            {
                "event": "run_status",
                "run_id": "run-2",
                "status": "failed",
                "error": "boom",
            }
        )
        kernel.end()

    driver = asyncio.create_task(_drive())
    with pytest.raises(RuntimeError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-2", run_id="run-2"
        )
    await driver

    reconciles = [e for e in observed if e.get("event") == "run_terminal_reconcile"]
    assert len(reconciles) == 1
    assert reconciles[0]["reason"] == "interrupted"
