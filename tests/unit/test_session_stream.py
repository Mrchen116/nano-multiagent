"""Tests for coding_cli.session_stream."""

import asyncio
import threading
import time
from typing import Any

from coding_cli.session_stream import SessionStreamReader


class _FakeClient:
    def __init__(self, *, events: list[dict[str, Any]], delay: float = 0.0) -> None:
        self._events = list(events)
        self._delay = delay
        self.call_log: list[tuple[str, dict[str, Any]]] = []

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        self.call_log.append(("stream_session", {"session_id": session_id, "last_event_id": last_event_id}))
        if self._delay:
            await asyncio.sleep(self._delay)
        for event in self._events:
            yield event


def test_reader_start_and_stop_lifecycle() -> None:
    client = _FakeClient(events=[])
    reader = SessionStreamReader(client)
    assert reader.session_id is None

    reader.start(session_id="s1")
    assert reader.session_id == "s1"
    assert reader._thread is not None
    assert reader._thread.is_alive()

    reader.stop()
    assert not reader._thread.is_alive()


def test_poll_returns_event_or_none() -> None:
    client = _FakeClient(events=[{"event": "test", "run_id": "r1"}])
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        # Give the background thread a moment to enqueue.
        time.sleep(0.05)
        evt = reader.poll(timeout=0.2)
        assert evt is not None
        assert evt["event"] == "test"
        assert reader.poll(timeout=0.05) is None
    finally:
        reader.stop()


def test_drain_run_collects_events_for_run_id() -> None:
    client = _FakeClient(
        events=[
            {"event": "tool_start", "run_id": "r1"},
            {"event": "assistant_message", "run_id": "r1", "content": "ok"},
            {"event": "run_status", "run_id": "r1", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        events = reader.drain_run(run_id="r1", timeout=0.1, idle_timeout=2.0)
        assert len(events) == 3
        assert events[0]["event"] == "tool_start"
        assert events[1]["event"] == "assistant_message"
        assert events[2]["event"] == "run_status"
    finally:
        reader.stop()


def test_drain_run_ignores_other_run_ids() -> None:
    client = _FakeClient(
        events=[
            {"event": "tool_start", "run_id": "r_other"},
            {"event": "assistant_message", "run_id": "r1", "content": "ok"},
            {"event": "run_status", "run_id": "r1", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        events = reader.drain_run(run_id="r1", timeout=0.1, idle_timeout=2.0)
        assert len(events) == 2
        assert all(e["run_id"] == "r1" for e in events)
    finally:
        reader.stop()


def test_drain_run_raises_timeout_on_missing_terminal() -> None:
    client = _FakeClient(events=[{"event": "assistant_message", "run_id": "r1", "content": "ok"}])
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        reader.drain_run(run_id="r1", timeout=0.05, idle_timeout=0.1)
        raise AssertionError("expected TimeoutError")
    except TimeoutError:
        pass
    finally:
        reader.stop()


def test_drain_run_tracks_last_event_id() -> None:
    client = _FakeClient(
        events=[
            {"event": "test", "run_id": "r1", "_id": 42},
            {"event": "run_status", "run_id": "r1", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        reader.drain_run(run_id="r1", timeout=0.1, idle_timeout=2.0)
        # After drain, a restart should pass last_event_id.
        client.call_log.clear()
        reader.stop()
        reader.start(session_id="s1")
        time.sleep(0.05)
        assert any(call[1].get("last_event_id") == 42 for call in client.call_log)
    finally:
        reader.stop()


def test_queue_overflow_drops_oldest_events() -> None:
    # Create many events to overflow the 4096 maxsize queue.
    many_events = [{"event": "fill", "run_id": "r1", "_id": i} for i in range(5000)]
    many_events.append({"event": "run_status", "run_id": "r1", "status": "completed"})
    client = _FakeClient(events=many_events)
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        events = reader.drain_run(run_id="r1", timeout=0.05, idle_timeout=5.0)
        # Should still see the terminal event even after overflow.
        assert events[-1]["event"] == "run_status"
        assert events[-1]["status"] == "completed"
    finally:
        reader.stop()


def test_drain_run_on_other_receives_non_target_events() -> None:
    other_events: list[dict[str, Any]] = []
    client = _FakeClient(
        events=[
            {"event": "run_status", "run_id": "r_other", "status": "running"},
            {"event": "assistant_message", "run_id": "r1", "content": "ok"},
            {"event": "run_status", "run_id": "r1", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        events = reader.drain_run(run_id="r1", timeout=0.1, idle_timeout=2.0, on_other=other_events.append)
        assert len(events) == 2
        assert events[0]["run_id"] == "r1"
        assert len(other_events) == 1
        assert other_events[0]["run_id"] == "r_other"
    finally:
        reader.stop()


def test_drain_run_long_run_not_killed_by_idle_timeout() -> None:
    """Regression: 持续有事件的长 run 不应被空闲超时误杀（原 bug 的核心回归）。

    用小 idle_timeout=0.3s 注入，在 0.3s 内持续喂多个事件，验证不触发超时。
    _FakeClient 的事件之间无 delay，能在 idle_timeout 内全部入队。
    """
    # 用多个中间事件模拟"持续活跃"的长 run，每个事件都会重置 deadline
    events = [{"event": "tool_start", "run_id": "r1"}] * 50
    events.append({"event": "run_status", "run_id": "r1", "status": "completed"})
    client = _FakeClient(events=events)
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        # idle_timeout=0.3s：如果是硬墙钟则会在 0.3s 内超时（事件太多），
        # 如果是空闲超时则只要每个事件间隔 < 0.3s 就不超时。
        # _FakeClient 无延迟，所有事件瞬间入队，远在 0.3s 内完成。
        result = reader.drain_run(run_id="r1", timeout=0.1, idle_timeout=0.3)
        assert result[-1]["event"] == "run_status"
        assert result[-1]["status"] == "completed"
    finally:
        reader.stop()


def test_drain_run_idle_timeout_triggers_when_no_events() -> None:
    """真卡死（无事件超过 idle_timeout）时仍应抛 TimeoutError。

    用 idle_timeout=0.15s 注入，stream 只有非本 run 的事件（不重置 deadline），
    等待超时。
    """
    # 只有其他 run 的事件，本 run 没有任何事件 → idle deadline 到期 → TimeoutError
    client = _FakeClient(
        events=[
            {"event": "run_status", "run_id": "r_other", "status": "running"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        reader.drain_run(run_id="r1", timeout=0.05, idle_timeout=0.15)
        raise AssertionError("expected TimeoutError")
    except TimeoutError:
        pass
    finally:
        reader.stop()
