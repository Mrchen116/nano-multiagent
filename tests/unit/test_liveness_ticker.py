"""bugfix-417-M3 R3: await-bound liveness ticker for LLM-await / parked-on-permission.

Two alive-but-quiet windows (waiting for the non-stream LLM's first chunk; parking on
a human permission decision) produce no business events on kernel.stream, so a live
wait used to look identical to a stall and get reaped. The ticker emits a periodic
`run_heartbeat` ONLY while the specific await is in flight, stopping the instant it
returns/raises/cancels — proving progress through the wait, never "the Task exists".
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent.core.agent.liveness import (
    _broker_publish_adapter,
    _emit_liveness_heartbeats,
    _with_liveness_heartbeat,
    liveness_ticker,
    session_event_publisher,
)

pytestmark = pytest.mark.asyncio


def _recorder() -> tuple[list[tuple[str, dict[str, Any]]], Any]:
    events: list[tuple[str, dict[str, Any]]] = []

    def _publish(event: str, data: dict[str, Any]) -> None:
        events.append((event, dict(data)))

    return events, _publish


async def test_liveness_ticker_emits_during_await_and_stops_after() -> None:
    events, publish = _recorder()
    async with liveness_ticker(
        publish=publish, run_id="run-1", source="llm", interval=0.02
    ):
        await asyncio.sleep(0.11)  # ~5 intervals
    count_at_exit = len(events)
    assert count_at_exit >= 3, f"expected periodic heartbeats, got {count_at_exit}"
    assert all(e == "run_heartbeat" for e, _ in events)
    assert all(d["run_id"] == "run-1" and d["source"] == "llm" for _, d in events)

    # After the context exits the ticker must be torn down — no further emits.
    await asyncio.sleep(0.06)
    assert len(events) == count_at_exit, (
        "ticker must stop emitting after the await ends"
    )


async def test_liveness_ticker_noop_without_publisher_or_run_id() -> None:
    events, publish = _recorder()
    async with liveness_ticker(
        publish=None, run_id="run-1", source="llm", interval=0.01
    ):
        await asyncio.sleep(0.05)
    assert events == []

    async with liveness_ticker(
        publish=publish, run_id=None, source="llm", interval=0.01
    ):
        await asyncio.sleep(0.05)
    assert events == []


async def test_liveness_ticker_torn_down_on_exception() -> None:
    events, publish = _recorder()
    with pytest.raises(RuntimeError):
        async with liveness_ticker(
            publish=publish, run_id="run-x", source="permission", interval=0.02
        ):
            await asyncio.sleep(0.05)
            raise RuntimeError("boom")
    count = len(events)
    await asyncio.sleep(0.06)
    assert len(events) == count, "ticker must stop even when the body raises"


async def test_with_liveness_heartbeat_reyields_and_ticks_during_gaps() -> None:
    events, publish = _recorder()

    async def _slow_stream() -> Any:
        for i in range(2):
            await asyncio.sleep(0.06)  # gap > interval → heartbeats fire
            yield i

    got: list[int] = []
    async for item in _with_liveness_heartbeat(
        _slow_stream(), publish=publish, run_id="run-llm", source="llm", interval=0.02
    ):
        got.append(item)

    assert got == [0, 1]
    assert len(events) >= 2, "heartbeats must fire during the inter-chunk gaps"
    # Once iteration completes the ticker is gone.
    count = len(events)
    await asyncio.sleep(0.06)
    assert len(events) == count


async def test_liveness_ticker_noop_when_missing() -> None:
    # The no-op-when-missing contract lives in liveness_ticker, not
    # _emit_liveness_heartbeats (bugfix-417-M4 fix-r1 removed the redundant park branch;
    # callers now guard before spawning the emit coroutine). A ticker with no publisher
    # must create no task and emit nothing.
    events, _publish = _recorder()
    async with liveness_ticker(publish=None, run_id="r", source="llm", interval=0.01):
        await asyncio.sleep(0.05)
    assert events == []


async def test_broker_publish_adapter_routes_to_raw_publisher() -> None:
    events, publish = _recorder()
    adapter = _broker_publish_adapter(publish)
    assert adapter is not None
    adapter("run_heartbeat", {"run_id": "r", "source": "permission"})
    assert events == [("run_heartbeat", {"run_id": "r", "source": "permission"})]
    assert _broker_publish_adapter(None) is None


async def test_session_event_publisher_adapter_from_hook_ctx() -> None:
    events, publish = _recorder()

    class _Ctx:
        session_event_publisher = staticmethod(publish)

    adapter = session_event_publisher(_Ctx())
    assert adapter is not None
    adapter("run_heartbeat", {"run_id": "r", "source": "llm"})
    assert events[0][0] == "run_heartbeat"

    class _NoPub:
        session_event_publisher = None

    assert session_event_publisher(_NoPub()) is None


async def test_permission_await_emits_heartbeats_then_stops_on_resolve() -> None:
    """Mirror runtime._permission_requester's parked-await structure: a ticker runs
    while the broker future is pending and is torn down the instant it resolves.

    Reproduces the production wiring (create_task(_emit_liveness_heartbeats) before the
    await, cancel + drain in finally) so any divergence in runtime.py breaks loudly —
    the same mirroring convention used by test_permission_requester_cancel.py.
    """
    events, publish = _recorder()
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    perm_heartbeat = asyncio.create_task(
        _emit_liveness_heartbeats(
            publish=_broker_publish_adapter(publish),
            run_id="run-perm",
            source="permission",
            interval=0.02,
        )
    )
    try:
        # Resolve the "user decision" after a few heartbeat intervals.
        loop.call_later(0.11, lambda: future.set_result("allow_once"))
        decision = await future
    finally:
        perm_heartbeat.cancel()
        with pytest.raises(asyncio.CancelledError):
            await perm_heartbeat

    assert decision == "allow_once"
    count = len(events)
    assert count >= 3, f"permission wait must emit periodic heartbeats, got {count}"
    assert all(d["source"] == "permission" for _, d in events)
    # No heartbeat after the decision (ticker torn down).
    await asyncio.sleep(0.06)
    assert len(events) == count
