"""Unit tests for EventStreamHub extensions in feat-338."""

import asyncio
import queue
import threading
import time
from typing import Any

import pytest

from agent.platform.http_api.sse import (
    EventStreamHub,
    StreamEvent,
    SubscriberOverflowError,
    encode_stream_error,
)


class TestCurrentSequence:
    def test_initial_sequence_is_zero(self) -> None:
        hub = EventStreamHub()
        assert hub.current_sequence() == 0

    def test_sequence_increments_after_publish(self) -> None:
        hub = EventStreamHub()
        hub.publish(event="run_status", session_id="sess_1", data={"run_id": "run_1"})
        assert hub.current_sequence() == 1
        hub.publish(event="run_status", session_id="sess_1", data={"run_id": "run_1"})
        assert hub.current_sequence() == 2


class TestHasSequence:
    def test_has_sequence_within_window(self) -> None:
        hub = EventStreamHub(history_limit=5)
        for i in range(3):
            hub.publish(event="run_status", session_id="sess_1", data={"run_id": f"run_{i}"})
        assert hub.has_sequence(1) is True
        assert hub.has_sequence(2) is True
        assert hub.has_sequence(3) is True

    def test_has_sequence_beyond_window(self) -> None:
        hub = EventStreamHub(history_limit=2)
        for i in range(5):
            hub.publish(event="run_status", session_id="sess_1", data={"run_id": f"run_{i}"})
        # history now contains seq 4, 5
        # has_sequence checks whether events *after* the given sequence are replayable.
        # Last-Event-ID: 3 means "send events after 3" → 4,5 are available → True.
        assert hub.has_sequence(1) is False
        assert hub.has_sequence(2) is False
        assert hub.has_sequence(3) is True
        assert hub.has_sequence(4) is True
        assert hub.has_sequence(5) is True

    def test_has_sequence_for_future(self) -> None:
        hub = EventStreamHub()
        hub.publish(event="run_status", session_id="sess_1", data={})
        # sequence 2 doesn't exist yet but is within the "future" range
        assert hub.has_sequence(2) is True

    def test_has_sequence_empty_history(self) -> None:
        hub = EventStreamHub()
        assert hub.has_sequence(0) is True
        assert hub.has_sequence(1) is False


class TestStreamSession:
    async def test_replays_history_then_live(self) -> None:
        hub = EventStreamHub()
        for i in range(3):
            hub.publish(event="run_status", session_id="sess_1", data={"run_id": f"run_{i}"})

        gen = hub.stream_session(session_id="sess_1", after_sequence=1)
        events = [await gen.asend(None), await gen.asend(None)]
        assert [e.sequence_num for e in events] == [2, 3]

    async def test_filters_by_session_id(self) -> None:
        hub = EventStreamHub()
        hub.publish(event="run_status", session_id="sess_1", data={"run_id": "r1"})
        hub.publish(event="run_status", session_id="sess_2", data={"run_id": "r2"})
        hub.publish(event="run_status", session_id="sess_1", data={"run_id": "r3"})

        gen = hub.stream_session(session_id="sess_1", after_sequence=0)
        events = [await gen.asend(None), await gen.asend(None)]
        assert all(e.session_id == "sess_1" for e in events)
        assert [e.data["run_id"] for e in events] == ["r1", "r3"]

    async def test_does_not_auto_close_on_terminal(self) -> None:
        hub = EventStreamHub()
        hub.publish(event="run_status", session_id="sess_1", data={"run_id": "r1", "status": "completed"})

        gen = hub.stream_session(session_id="sess_1", after_sequence=0)
        evt = await gen.asend(None)
        assert evt.data["status"] == "completed"

        # generator should still be alive, waiting for next event
        # publish another event and verify we receive it
        hub.publish(event="run_status", session_id="sess_1", data={"run_id": "r2"})
        evt2 = await gen.asend(None)
        assert evt2.data["run_id"] == "r2"

    async def test_live_event_delivery(self) -> None:
        hub = EventStreamHub()
        gen = hub.stream_session(session_id="sess_1", after_sequence=0)

        def _publish_later() -> None:
            import time
            time.sleep(0.05)
            hub.publish(event="assistant_message", session_id="sess_1", data={"content": "hello"})

        t = threading.Thread(target=_publish_later)
        t.start()

        evt = await gen.asend(None)
        assert evt.data["content"] == "hello"
        t.join(timeout=2.0)

    async def test_overflow_raises_subscriber_overflow(self) -> None:
        hub = EventStreamHub()
        gen = hub.stream_session(session_id="sess_1", after_sequence=0, tick_seconds=0.05)

        errors: list[Exception] = []

        async def _consume() -> None:
            try:
                while True:
                    await gen.asend(None)
                    await asyncio.sleep(0.05)
            except Exception as exc:
                errors.append(exc)

        # Run consumer in a separate thread with its own event loop because
        # the async generator shares the same event loop as the test.
        def _run_consumer() -> None:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_consume())
            finally:
                loop.close()

        consumer = threading.Thread(target=_run_consumer)
        consumer.start()

        # give generator time to register subscriber and block on get()
        time.sleep(0.02)

        # rapidly publish more events than buffer can hold
        for i in range(300):
            hub.publish(event="run_status", session_id="sess_1", data={"run_id": f"run_{i}"})

        consumer.join(timeout=5.0)
        assert consumer.is_alive() is False, "consumer should have exited after overflow"
        assert len(errors) == 1
        assert isinstance(errors[0], SubscriberOverflowError)


class TestEncodeStreamError:
    def test_encodes_error_frame(self) -> None:
        raw = encode_stream_error(
            session_id="sess_1",
            run_id="run_1",
            code="resume_window_exceeded",
            message="history pruned",
        )
        text = raw.decode()
        assert "event: error" in text
        assert '"code":"resume_window_exceeded"' in text
        assert '"retryable":false' in text

    def test_subscriber_overflow_is_retryable(self) -> None:
        raw = encode_stream_error(
            session_id="sess_1",
            run_id=None,
            code="subscriber_overflow",
            message="backlog overflow",
        )
        text = raw.decode()
        assert '"retryable":true' in text
