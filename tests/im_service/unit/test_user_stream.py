"""Unit tests for UserStreamRegistry fan-out helpers (feat-340-M10)."""

from __future__ import annotations

from IM.ws.user_stream import UserStreamRegistry


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
