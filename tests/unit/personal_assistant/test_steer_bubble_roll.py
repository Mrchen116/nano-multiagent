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

    def __init__(self, new_message_id: str = "msg-B") -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._new_message_id = new_message_id

    async def send_json(self, message_type: str, payload: dict[str, Any]) -> None:
        self.sent.append((message_type, payload))

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.sent.append((message_type, payload))
        # IM returns the freshly-created bubble's message_id on turn_start.
        return {"payload": {"message_id": self._new_message_id}}


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


def test_injection_consumed_noop_without_bubble() -> None:
    """No active bubble (no message_id yet) → nothing to roll; emit nothing."""
    manager = _FakeManager()
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

    assert manager.sent == []
