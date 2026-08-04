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
