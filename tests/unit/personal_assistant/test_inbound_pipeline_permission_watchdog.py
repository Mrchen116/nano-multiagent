"""bugfix-410-M2 R2: Gateway run-idle watchdog must exempt the permission-pending
wait from the 120s idle timeout (#98).

When the kernel parks a run awaiting a human permission decision it emits a
``permission_request`` event and then — legitimately — produces no further events
until the user decides. The run-idle watchdog (``_await_terminal_run_async``) used
to ``cancel(run_id)`` after ``run_idle_timeout_seconds`` of silence, killing the
run while the user was still reading the card (and bricking the session via the
orphaned tool_call, which is the #82 side of the same incident). After a
``permission_request`` the watchdog must enter an exemption state with no idle
timeout, and exit it on the next event of any kind.
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


def _build_pipeline(kernel: Any, *, idle_timeout: float) -> InboundPipeline:
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
    )


async def test_permission_pending_exempts_idle_watchdog() -> None:
    """After permission_request, silence longer than the idle timeout must NOT cancel."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    async def _drive() -> None:
        # 1. permission_request enters the exemption state.
        kernel.push(
            {"event": "permission_request", "run_id": "run-1", "request_id": "p1"}
        )
        # 2. Stay silent for well over the 0.1s idle timeout — must survive.
        await asyncio.sleep(0.4)
        # 3. User decides → a subsequent event arrives; watchdog resumes normal timing.
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
        "permission-pending silence must not trigger the idle watchdog cancel"
    )
    assert run_state.get("status") == "completed"


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


async def test_exemption_exits_after_subsequent_event_then_stalls() -> None:
    """After the exemption is cleared by a follow-up event, a fresh stall is reaped."""
    kernel = _ControlledStreamKernel()
    pipeline = _build_pipeline(kernel, idle_timeout=0.1)

    async def _drive() -> None:
        kernel.push(
            {"event": "permission_request", "run_id": "run-3", "request_id": "p3"}
        )
        await asyncio.sleep(0.3)  # exempt — no cancel
        # User allows → tool_start clears exemption; then the tool hangs forever.
        kernel.push({"event": "tool_start", "run_id": "run-3", "call_id": "c3"})
        # Do NOT end the stream — the post-exemption stall must be reaped.

    driver = asyncio.create_task(_drive())
    with pytest.raises(TimeoutError):
        await pipeline._await_terminal_run_async(
            kernel_session_id="sess-3", run_id="run-3"
        )
    await driver

    assert kernel.cancel_calls == ["run-3"], (
        "once the exemption is cleared, a new stall must hit the watchdog again"
    )
