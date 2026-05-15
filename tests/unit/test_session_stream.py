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
    """Regression: 持续有事件的长 run 不应被空闲超时误杀（bugfix-351 的核心回归）。"""
    events = [{"event": "tool_start", "run_id": "r1"}] * 50
    events.append({"event": "run_status", "run_id": "r1", "status": "completed"})
    client = _FakeClient(events=events)
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        result = reader.drain_run(run_id="r1", timeout=0.1, idle_timeout=0.3)
        assert result[-1]["event"] == "run_status"
        assert result[-1]["status"] == "completed"
    finally:
        reader.stop()


def test_drain_run_idle_timeout_triggers_when_no_events() -> None:
    """真卡死时仍抛 TimeoutError。"""
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


# ---------------------------------------------------------------------------
# feat-333-M1: CLI SSE drain permission_request hook
# ---------------------------------------------------------------------------

def test_drain_run_calls_on_permission_request_for_matching_events() -> None:
    """drain_run should invoke on_permission_request callback for permission_request events."""
    permission_events: list[dict[str, Any]] = []

    client = _FakeClient(
        events=[
            {"event": "tool_start", "run_id": "r1"},
            {
                "event": "permission_request",
                "run_id": "r1",
                "request_id": "perm-1",
                "tool_name": "write",
                "tool_input": {"file_path": "/tmp/f"},
                "options": [{"id": "allow_once", "label": "Allow once"}],
            },
            {"event": "assistant_message", "run_id": "r1", "content": "done"},
            {"event": "run_status", "run_id": "r1", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        events = reader.drain_run(
            run_id="r1",
            timeout=0.1,
            idle_timeout=2.0,
            on_permission_request=permission_events.append,
        )
        event_names = [e.get("event") for e in events]
        assert "permission_request" not in event_names, (
            "permission_request should be handled via on_permission_request callback, "
            "not included in the returned events list"
        )
        assert len(permission_events) == 1
        assert permission_events[0]["request_id"] == "perm-1"
        assert permission_events[0]["tool_name"] == "write"
    finally:
        reader.stop()


def test_drain_run_permission_request_without_callback_is_passed_to_on_event() -> None:
    """When no on_permission_request is provided, permission_request events go to on_event."""
    collected: list[dict[str, Any]] = []

    client = _FakeClient(
        events=[
            {
                "event": "permission_request",
                "run_id": "r1",
                "request_id": "perm-2",
                "tool_name": "bash",
            },
            {"event": "run_status", "run_id": "r1", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="s1")
    try:
        reader.drain_run(
            run_id="r1",
            timeout=0.1,
            idle_timeout=2.0,
            on_event=collected.append,
        )
        event_names = [e.get("event") for e in collected]
        assert "permission_request" in event_names
    finally:
        reader.stop()
