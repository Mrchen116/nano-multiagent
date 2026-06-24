"""bugfix-426-M4 决策6: a consumed steer rolls the IM bubble (close A, open B).

When the kernel drains a steered message into context it emits ``injection_consumed``
(same run_id under 决策5). IM is a time-ordered bubble chat, so the reply to the steer
must land in a NEW bubble that sorts after the steer message — not appended to the
bubble that was answering the prior message. The observer must:

- finalize the current bubble A as ``completed`` (the prior reply genuinely ended —
  not failed, which is the #140 watchdog symptom this fixes), then
- open a new bubble B (turn_start → new message_id) at the consume moment, and
- route subsequent deltas to B.
"""

from __future__ import annotations

import asyncio
from typing import Any

from personal_assistant.main import _build_kernel_event_observer


class _FakeManager:
    connected = True

    def __init__(self, new_message_id: str | None = "msg-B") -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []
        # When set, every turn_start ack returns this fixed id. When None, each ack
        # returns a fresh incrementing id (so back-to-back rolls get distinct bubbles).
        self._new_message_id = new_message_id
        self._bubble_seq = 0

    async def send_json(self, message_type: str, payload: dict[str, Any]) -> None:
        self.sent.append((message_type, payload))

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.sent.append((message_type, payload))
        if self._new_message_id is not None:
            msg_id = self._new_message_id
        else:
            self._bubble_seq += 1
            msg_id = f"bubble-{self._bubble_seq}"
        # IM returns the freshly-created bubble's message_id on turn_start.
        return {"payload": {"message_id": msg_id}}


def _drive(observer, event: dict[str, Any]) -> None:
    async def _go() -> None:
        maybe = observer(event)
        if asyncio.iscoroutine(maybe):
            await maybe
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_go())


def _kinds(manager: _FakeManager) -> list[str]:
    return [p.get("kind") for mt, p in manager.sent if mt == "node.streaming_delta"]


def test_injection_consumed_closes_bubble_a_completed_then_opens_b() -> None:
    manager = _FakeManager(new_message_id="msg-B")
    run_ctx = {
        "run-1": {
            "conversation_id": "conv-1",
            "message_id": "msg-A",
            "agent_id": "agent-1",
            "kernel_message_id": "kmsg-A",
        }
    }
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_ctx,
        running_tool_calls={},
    )

    _drive(
        observer,
        {"event": "injection_consumed", "run_id": "run-1", "turn_id": "turn-1"},
    )

    # Bubble A finalized as completed (clean end, not failed), THEN B opened.
    assert _kinds(manager) == ["message_completed", "turn_start"]
    completed = next(
        p for _mt, p in manager.sent if p.get("kind") == "message_completed"
    )
    assert completed["message_id"] == "msg-A"
    assert completed["delivery_status"] == "completed"
    turn_start = next(p for _mt, p in manager.sent if p.get("kind") == "turn_start")
    assert turn_start["conversation_id"] == "conv-1"
    assert turn_start["run_id"] == "run-1"

    # The run now streams into bubble B; the stale kernel_message_id is cleared so
    # the next assistant_message delta flows straight into B.
    assert run_ctx["run-1"]["message_id"] == "msg-B"
    assert "kernel_message_id" not in run_ctx["run-1"]


def test_injection_consumed_opens_b_even_when_message_id_empty() -> None:
    """bugfix-426-M4 V3: in the narrow window where message_id is transiently empty
    (turn_start ack not yet returned), the steer must still get a bubble — open B so
    its reply is not stranded. With no bubble A to close, only turn_start is sent."""
    manager = _FakeManager(new_message_id="msg-B")
    run_ctx = {
        "run-1": {
            "conversation_id": "conv-1",
            "message_id": "",
            "agent_id": "agent-1",
        }
    }
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_ctx,
        running_tool_calls={},
    )

    _drive(observer, {"event": "injection_consumed", "run_id": "run-1"})

    # No message_completed (no bubble A to close), but B is opened and the run points
    # at it so the steer reply streams into B.
    assert _kinds(manager) == ["turn_start"]
    assert run_ctx["run-1"]["message_id"] == "msg-B"


def test_two_back_to_back_steers_roll_safely() -> None:
    """bugfix-426-M4 V3: 决策6 supports multiple steers. Two injection_consumed signals
    for the same run must each roll cleanly — bubble A closed once, a fresh bubble per
    consume, no double-close of an already-finalized bubble, no zombie running bubble.
    """
    manager = _FakeManager(new_message_id=None)  # fresh distinct id per turn_start
    run_ctx = {
        "run-1": {
            "conversation_id": "conv-1",
            "message_id": "bubble-A",
            "agent_id": "agent-1",
            "kernel_message_id": "kmsg-A",
        }
    }
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_ctx,
        running_tool_calls={},
    )

    # First steer rolls A→B1; second steer rolls B1→B2. Each completes the prior
    # bubble exactly once and opens exactly one new bubble.
    _drive(observer, {"event": "injection_consumed", "run_id": "run-1"})
    first_bubble = run_ctx["run-1"]["message_id"]
    _drive(observer, {"event": "injection_consumed", "run_id": "run-1"})
    second_bubble = run_ctx["run-1"]["message_id"]

    kinds = _kinds(manager)
    # Each roll = one message_completed (close prior) + one turn_start (open next).
    assert kinds.count("message_completed") == 2
    assert kinds.count("turn_start") == 2
    # Each message_completed closes a DISTINCT bubble (A then B1) — no double-close.
    completed_ids = [
        p["message_id"]
        for _mt, p in manager.sent
        if p.get("kind") == "message_completed"
    ]
    assert len(set(completed_ids)) == 2
    # The run ends pointing at the latest bubble (no zombie left running).
    assert second_bubble and second_bubble != first_bubble
    # The reentrancy flag is cleared (not leaked) after both rolls settle.
    assert "rolling" not in run_ctx["run-1"]


def test_concurrent_injection_consumed_guard_drops_duplicate() -> None:
    """bugfix-426-M4 V3: if a second injection_consumed roll starts while the first is
    still awaiting its turn_start ack (concurrent reentrancy), the per-run guard drops
    the duplicate so bubble A is closed once and only one new bubble B is opened (no
    double-close, no zombie running bubble)."""
    import asyncio as _asyncio

    from personal_assistant.main import _roll_bubble

    class _BlockingManager:
        connected = True

        def __init__(self) -> None:
            self.sent: list[tuple[str, dict[str, Any]]] = []
            self._gate = _asyncio.Event()
            self._seq = 0

        async def send_json(self, mt: str, payload: dict[str, Any]) -> None:
            self.sent.append((mt, payload))

        async def send_json_await_ack(
            self, mt: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            self.sent.append((mt, payload))
            await self._gate.wait()  # hold the first roll inside the await
            self._seq += 1
            return {"payload": {"message_id": f"bubble-{self._seq}"}}

    async def _go() -> None:
        manager = _BlockingManager()
        run_ctx = {
            "run-1": {
                "conversation_id": "conv-1",
                "message_id": "bubble-A",
                "agent_id": "agent-1",
            }
        }

        def _roll():
            return _roll_bubble(
                manager,
                run_id="run-1",
                conversation_id="conv-1",
                agent_id="agent-1",
                run_context_store=run_ctx,
                old_message_id="bubble-A",
            )

        # Start roll #1; it parks on the ack gate holding the per-run flag.
        t1 = _asyncio.ensure_future(_roll())
        await _asyncio.sleep(0)  # let t1 reach the gated ack
        # Roll #2 starts while #1 is in flight → guard drops it immediately.
        r2 = await _roll()
        assert r2 is None, "concurrent duplicate roll must be dropped by the guard"
        # Release #1.
        manager._gate.set()
        r1 = await t1
        assert r1 == "bubble-1"

        kinds = [p.get("kind") for _mt, p in manager.sent]
        # Bubble A closed exactly once; exactly one new bubble opened.
        assert kinds.count("message_completed") == 1
        assert kinds.count("turn_start") == 1
        assert run_ctx["run-1"]["message_id"] == "bubble-1"
        assert "rolling" not in run_ctx["run-1"]

    asyncio.run(_go())
