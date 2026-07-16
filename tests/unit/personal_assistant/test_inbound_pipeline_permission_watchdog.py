"""bugfix-465: permission waits are fully exempt from the idle watchdog.

During a permission_request the run is intentionally waiting for a human decision,
so it must not be reaped even if no run_heartbeat arrives. Once the kernel emits
permission_resolved the normal idle watchdog is restored, so a subsequent stall
(crashed tool, dead loop, etc.) is still cancelled after the idle window.
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


async def test_permission_pending_survives_without_heartbeat() -> None:
    """A parked permission wait is fully exempt from the idle watchdog: even when no
    run_heartbeat arrives for longer than the idle window, the run is NOT reaped.
    Once the user resolves it, the run completes normally."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    async def _drive() -> None:
        # Run parks awaiting a permission decision.
        kernel.push(
            {"event": "permission_request", "run_id": "run-1", "request_id": "p1"}
        )
        # No heartbeat for longer than the 0.1s idle window — must stay alive.
        await asyncio.sleep(0.25)
        # User resolves the permission request.
        kernel.push(
            {"event": "permission_resolved", "run_id": "run-1", "request_id": "p1"}
        )
        # Run resumes and completes.
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
        "a permission wait must not be reaped while awaiting a human decision"
    )
    assert run_state.get("status") == "completed"


async def test_permission_resolved_restores_watchdog() -> None:
    """After permission_resolved, the idle watchdog is restored. If the run stalls
    without heartbeats again, it is reaped — the exemption ends at resolution."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    async def _drive() -> None:
        kernel.push(
            {"event": "permission_request", "run_id": "run-c", "request_id": "pc"}
        )
        # Permission wait is exempt, so wait longer than the idle window before resolving.
        await asyncio.sleep(0.25)
        kernel.push(
            {"event": "permission_resolved", "run_id": "run-c", "request_id": "pc"}
        )
        # After resolution the normal watchdog is back; no further events → reap.

    driver = asyncio.create_task(_drive())
    with pytest.raises(TimeoutError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-c", run_id="run-c"
        )
    await driver

    assert kernel.cancel_calls == ["run-c"], (
        "after permission_resolved, a stalled run must be reaped again"
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
    """After permission_resolved restores the watchdog, a fresh stall (no heartbeat)
    is reaped — the exemption ends at resolution, so a dead run is still caught."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    async def _drive() -> None:
        kernel.push(
            {"event": "permission_request", "run_id": "run-3", "request_id": "p3"}
        )
        # While parked, the run is fully exempt from the idle watchdog.
        await asyncio.sleep(0.15)
        # User resolves the request; the watchdog is restored from this point.
        kernel.push(
            {"event": "permission_resolved", "run_id": "run-3", "request_id": "p3"}
        )
        kernel.push({"event": "tool_start", "run_id": "run-3", "call_id": "c3"})
        # Then the tool hangs with NO further heartbeat — must be reaped.

    driver = asyncio.create_task(_drive())
    with pytest.raises(TimeoutError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-3", run_id="run-3"
        )
    await driver

    assert kernel.cancel_calls == ["run-3"], (
        "a post-decision stall after permission_resolved must hit the watchdog"
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


async def test_user_stop_cancelled_returns_cleanly_without_raising() -> None:
    """bugfix-417-fix2 (#114, Issue 1): a USER /stop ends the run as `cancelled` — an
    EXPECTED terminal, NOT an error. When the run is marked user-interrupted,
    _await_terminal_run_async must reconcile the badge and return normally (no
    RuntimeError), so the originating turn finalizes cleanly instead of emitting
    phase=failed and wedging the bubble on the running spinner. The reconcile must
    carry finalize_bubble so the observer closes the agent bubble."""
    kernel = _ControlledStreamKernel()
    observed: list[dict[str, Any]] = []
    pipeline = _build_pipeline(
        kernel, idle_timeout=5.0, observer=lambda ev: observed.append(dict(ev))
    )
    # /stop marks the run user-interrupted before the cancel terminal arrives.
    pipeline._user_interrupted_runs.add("run-x")

    async def _drive() -> None:
        kernel.push({"event": "tool_start", "run_id": "run-x", "call_id": "cx"})
        kernel.push({"event": "run_status", "run_id": "run-x", "status": "cancelled"})
        kernel.end()

    driver = asyncio.create_task(_drive())
    run_state, _reply = await pipeline._await_terminal_run_async(
        kernel_session_id="sess-x", run_id="run-x"
    )
    await driver

    assert run_state.get("status") == "cancelled"
    reconciles = [e for e in observed if e.get("event") == "run_terminal_reconcile"]
    assert len(reconciles) == 1 and reconciles[0]["run_id"] == "run-x"
    # User stop → reconcile carries finalize_bubble + the CC content.
    assert reconciles[0].get("finalize_bubble") is True
    assert reconciles[0].get("content") == "[Request interrupted by user for tool use]"
    assert kernel.cancel_calls == []


async def test_non_user_cancelled_still_raises() -> None:
    """A `cancelled` from a NON-user source (watchdog reap / defensive cancel —
    run NOT in _user_interrupted_runs) must still raise, so Req B's stalled→failed
    reaping does not regress (bugfix-417-fix2 Issue 1 precision)."""
    kernel = _ControlledStreamKernel()
    observed: list[dict[str, Any]] = []
    pipeline = _build_pipeline(
        kernel, idle_timeout=5.0, observer=lambda ev: observed.append(dict(ev))
    )
    # NOT marked user-interrupted.

    async def _drive() -> None:
        kernel.push({"event": "run_status", "run_id": "run-nc", "status": "cancelled"})
        kernel.end()

    driver = asyncio.create_task(_drive())
    with pytest.raises(RuntimeError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-nc", run_id="run-nc"
        )
    await driver
    # Reconcile fired but WITHOUT finalize_bubble (system reap → bubble stays failed).
    reconciles = [e for e in observed if e.get("event") == "run_terminal_reconcile"]
    assert len(reconciles) == 1
    assert not reconciles[0].get("finalize_bubble")


async def test_failed_terminal_still_raises() -> None:
    """A genuine `failed` terminal must still raise (surfaced as an error)."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=5.0)

    async def _drive() -> None:
        kernel.push(
            {
                "event": "run_status",
                "run_id": "run-f",
                "status": "failed",
                "error": {"message": "boom"},
            }
        )
        kernel.end()

    driver = asyncio.create_task(_drive())
    with pytest.raises(RuntimeError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-f", run_id="run-f"
        )
    await driver


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
