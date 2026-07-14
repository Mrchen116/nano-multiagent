"""Unit tests for UserStreamRegistry fan-out helpers (feat-340-M10)."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import json

from IM.domain.models import ConversationEvent
from IM.infra.repositories import EventReplayResult
from IM.ws.user_stream import (
    UserStreamRegistry,
    conversation_event_to_wire_data,
    encode_user_stream_event_frame,
    serve_user_websocket,
)


class _StubWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def send_text(self, text: str) -> None:
        if self.closed:
            raise RuntimeError("closed")
        self.sent.append(text)


def _event(event_id: int) -> ConversationEvent:
    return ConversationEvent(
        event_id=event_id,
        conversation_id="conv-1",
        message_id=None,
        event_type="message.sent",
        delivery_status="sent",
        payload_json=json.dumps({"content": f"event-{event_id}"}),
        created_at="2026-07-13T00:00:00Z",
    )


class _PagedEventRepository:
    def __init__(self, count: int) -> None:
        self.events = [_event(event_id) for event_id in range(1, count + 1)]
        self.calls: list[int] = []

    def list_events_for_user_resume(
        self,
        *,
        user_id: str,
        after_event_id: int,
        max_batch: int,
        max_gap: int,
        replay_window_minutes: int,
        up_to_event_id: int | None = None,
    ) -> EventReplayResult:
        del user_id, max_gap, replay_window_minutes
        self.calls.append(after_event_id)
        replay_through = (
            up_to_event_id if up_to_event_id is not None else len(self.events)
        )
        page = [
            event
            for event in self.events
            if after_event_id < event.event_id <= replay_through
        ][:max_batch]
        return EventReplayResult(events=page, resync_required=False, reason=None)

    def global_max_event_id(self) -> int:
        return self.events[-1].event_id if self.events else 0


class _ResumeWebSocket(_StubWebSocket):
    def __init__(
        self, *, expected_events: int = 0, block_first_replay: bool = False
    ) -> None:
        super().__init__()
        self.expected_events = expected_events
        self.block_first_replay = block_first_replay
        self.accepted = False
        self.replay_started = asyncio.Event()
        self.release_replay = asyncio.Event()
        self.drained = asyncio.Event()
        self._received_resume = False
        self._event_frames_sent = 0

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if not self._received_resume:
            self._received_resume = True
            return json.dumps({"op": "resume", "after_event_id": 0})
        await asyncio.Future()
        raise AssertionError("unreachable")

    async def send_text(self, text: str) -> None:
        frame = json.loads(text)
        if self.block_first_replay and frame.get("event_id") == 1:
            self.replay_started.set()
            await self.release_replay.wait()
        self.sent.append(text)
        if frame.get("op") == "event":
            self._event_frames_sent += 1
        if self.expected_events and self._event_frames_sent >= self.expected_events:
            self.drained.set()


async def test_broadcast_to_user_delivers_only_to_target_user() -> None:
    registry = UserStreamRegistry()
    ws_a = _StubWebSocket()
    ws_b = _StubWebSocket()
    await registry.add("user-a", ws_a)
    await registry.add("user-b", ws_b)

    await registry.broadcast_to_user("user-a", '{"hello":"a"}')

    assert ws_a.sent == ['{"hello":"a"}']
    assert ws_b.sent == []


async def test_broadcast_to_user_fan_outs_multiple_tabs_for_same_user() -> None:
    registry = UserStreamRegistry()
    ws_one = _StubWebSocket()
    ws_two = _StubWebSocket()
    await registry.add("user-a", ws_one)
    await registry.add("user-a", ws_two)

    await registry.broadcast_to_user("user-a", '{"x":1}')

    assert ws_one.sent == ['{"x":1}']
    assert ws_two.sent == ['{"x":1}']


async def test_broadcast_to_user_prunes_dead_connections() -> None:
    registry = UserStreamRegistry()
    dead = _StubWebSocket()
    dead.closed = True
    alive = _StubWebSocket()
    await registry.add("user-a", dead)
    await registry.add("user-a", alive)

    await registry.broadcast_to_user("user-a", '{"x":1}')

    # First call: alive got it, dead errored and is pruned.
    assert alive.sent == ['{"x":1}']
    # Second call should only target alive (dead was pruned).
    await registry.broadcast_to_user("user-a", '{"x":2}')
    assert alive.sent == ['{"x":1}', '{"x":2}']
    assert dead.sent == []


async def test_broadcast_to_user_silent_when_user_absent() -> None:
    registry = UserStreamRegistry()
    # No add. Should not raise.
    await registry.broadcast_to_user("ghost", '{"x":1}')


async def test_resume_handoff_blocks_live_delivery_until_replay_is_registered() -> None:
    """Live broadcast cannot overtake an in-progress replay for the same user."""
    registry = UserStreamRegistry()
    repository = _PagedEventRepository(1)
    websocket = _ResumeWebSocket(block_first_replay=True)
    serving = asyncio.create_task(
        serve_user_websocket(
            websocket=websocket,
            event_repository=repository,  # type: ignore[arg-type]
            registry=registry,
            user_id="user-a",
        )
    )
    broadcast: asyncio.Task[None] | None = None
    try:
        await asyncio.wait_for(websocket.replay_started.wait(), timeout=1)
        broadcast = asyncio.create_task(
            registry.broadcast_to_user(
                "user-a",
                '{"op":"event","event_type":"message.sent","event_id":2,'
                '"data":{"content":"live"}}',
            )
        )
        await asyncio.sleep(0)
        assert not broadcast.done(), (
            "same-user live delivery must wait for replay handoff"
        )

        websocket.release_replay.set()
        await asyncio.wait_for(broadcast, timeout=5)
        frames = [json.loads(text) for text in websocket.sent]
        assert [frame["event_id"] for frame in frames] == [1, 2]
    finally:
        websocket.release_replay.set()
        if broadcast is not None and not broadcast.done():
            broadcast.cancel()
            with suppress(asyncio.CancelledError):
                await broadcast
        serving.cancel()
        with suppress(asyncio.CancelledError):
            await serving


async def test_resume_does_not_redeliver_same_persisted_event_as_live() -> None:
    """An event covered by replay must not be sent again by its queued broadcast."""
    registry = UserStreamRegistry()
    repository = _PagedEventRepository(501)
    websocket = _ResumeWebSocket(expected_events=501, block_first_replay=True)
    serving = asyncio.create_task(
        serve_user_websocket(
            websocket=websocket,
            event_repository=repository,  # type: ignore[arg-type]
            registry=registry,
            user_id="user-a",
        )
    )
    broadcast: asyncio.Task[None] | None = None
    try:
        await asyncio.wait_for(websocket.replay_started.wait(), timeout=1)
        broadcast = asyncio.create_task(
            registry.broadcast_to_user(
                "user-a",
                encode_user_stream_event_frame(repository.events[-1]),
            )
        )
        await asyncio.sleep(0)
        assert not broadcast.done()

        websocket.release_replay.set()
        await asyncio.wait_for(broadcast, timeout=5)
        frames = [json.loads(text) for text in websocket.sent]
        assert [frame["event_id"] for frame in frames] == list(range(1, 502))
    finally:
        websocket.release_replay.set()
        if broadcast is not None and not broadcast.done():
            broadcast.cancel()
            with suppress(asyncio.CancelledError):
                await broadcast
        serving.cancel()
        with suppress(asyncio.CancelledError):
            await serving


async def test_resume_drains_every_page_beyond_single_replay_batch() -> None:
    """A recoverable backlog larger than 500 is replayed completely before live mode."""
    registry = UserStreamRegistry()
    repository = _PagedEventRepository(650)
    websocket = _ResumeWebSocket(expected_events=650)
    serving = asyncio.create_task(
        serve_user_websocket(
            websocket=websocket,
            event_repository=repository,  # type: ignore[arg-type]
            registry=registry,
            user_id="user-a",
        )
    )
    try:
        await asyncio.wait_for(websocket.drained.wait(), timeout=1)
        frames = [json.loads(text) for text in websocket.sent]
        assert [frame["event_id"] for frame in frames] == list(range(1, 651))
        assert repository.calls == [0, 500]
    finally:
        serving.cancel()
        with suppress(asyncio.CancelledError):
            await serving


def test_replayed_tombstone_preserves_discarded_message_identity() -> None:
    event = ConversationEvent(
        event_id=5,
        conversation_id="conv-1",
        message_id=None,
        event_type="message.discarded",
        delivery_status="completed",
        payload_json=json.dumps(
            {
                "conversation_id": "conv-1",
                "message_id": "provisional-msg-1",
                "reason": "no_reply_token",
            }
        ),
        created_at="2026-07-13T00:00:00Z",
    )

    frame = json.loads(encode_user_stream_event_frame(event))

    assert frame["data"]["message_id"] == "provisional-msg-1"
    assert frame["data"]["reason"] == "no_reply_token"


def test_regular_event_fk_message_identity_still_overrides_payload() -> None:
    event = ConversationEvent(
        event_id=6,
        conversation_id="conv-1",
        message_id="canonical-msg-1",
        event_type="message.completed",
        delivery_status="completed",
        payload_json=json.dumps(
            {"conversation_id": "conv-1", "message_id": "stale-payload-msg"}
        ),
        created_at="2026-07-13T00:00:01Z",
    )

    data = conversation_event_to_wire_data(event)

    assert data["message_id"] == "canonical-msg-1"
