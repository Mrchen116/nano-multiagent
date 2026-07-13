"""Unit tests for UserStreamRegistry fan-out helpers (feat-340-M10)."""

from __future__ import annotations

import json

from IM.domain.models import ConversationEvent
from IM.ws.user_stream import (
    UserStreamRegistry,
    conversation_event_to_wire_data,
    encode_user_stream_event_frame,
)


class _StubWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def send_text(self, text: str) -> None:
        if self.closed:
            raise RuntimeError("closed")
        self.sent.append(text)


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
