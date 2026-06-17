"""bugfix-416 #111: reconcile of a timed-out tool must preserve its command/description.

When a bash tool times out, the watchdog emits a synthetic ``run_terminal_reconcile``
event to close the still-in-flight tool_call so the IM badge stops spinning. Before the
fix, ``running_tool_calls`` only stored the tool name, so reconcile re-emitted
``input: {}`` — wiping the command and description from the IM bubble (only a red ×
"bash Timed out" remained). The fix stores the full tool_call (name + input) at
``tool_start`` and re-sends the original input on reconcile, changing only
status=failed + reason.
"""

from __future__ import annotations

import asyncio
from typing import Any

from personal_assistant.main import _build_kernel_event_observer


class _FakeManager:
    connected = True

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []

    async def send_json(self, message_type: str, payload: dict[str, Any]) -> None:
        self.sent.append((message_type, payload))


def _drive(observer, event: dict[str, Any]) -> None:
    async def _go() -> None:
        maybe = observer(event)
        if asyncio.iscoroutine(maybe):
            await maybe
        # Observer schedules sends via loop.create_task; yield so they run.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_go())


def _completed_payload(manager: _FakeManager) -> dict[str, Any]:
    for message_type, payload in manager.sent:
        if (
            message_type == "node.streaming_delta"
            and payload.get("kind") == "tool_call_completed"
        ):
            return payload["tool_call"]
    raise AssertionError(f"no tool_call_completed sent; got {manager.sent}")


def test_reconcile_preserves_command_and_description() -> None:
    manager = _FakeManager()
    run_ctx = {
        "run-1": {
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "agent_id": "agent-1",
        }
    }
    running_tool_calls: dict[str, dict[str, Any]] = {}
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_ctx,
        running_tool_calls=running_tool_calls,
    )

    arguments = {
        "command": "npm run test:all",
        "description": "Run full frontend test suite",
        "timeout": 600000,
    }
    _drive(
        observer,
        {
            "event": "tool_start",
            "run_id": "run-1",
            "call_id": "call-1",
            "name": "bash",
            "arguments": arguments,
        },
    )
    # Watchdog reaps the run; the in-flight bash call never received tool_end.
    _drive(
        observer,
        {
            "event": "run_terminal_reconcile",
            "run_id": "run-1",
            "reason": "timed_out",
        },
    )

    tc = _completed_payload(manager)
    assert tc["status"] == "failed"
    assert tc["reason"] == "timed_out"
    assert tc["name"] == "bash"
    # The original command and description survive the reconcile — not wiped to {}.
    assert tc["input"] == arguments
    assert tc["input"]["command"] == "npm run test:all"
    assert tc["input"]["description"] == "Run full frontend test suite"


def test_reconcile_still_closes_in_flight_call_as_failed() -> None:
    """止转圈不退化：在飞 call 仍被收口为 failed（不再永久 running）。"""
    manager = _FakeManager()
    run_ctx = {
        "run-1": {
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "agent_id": "agent-1",
        }
    }
    running_tool_calls: dict[str, dict[str, Any]] = {}
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_ctx,
        running_tool_calls=running_tool_calls,
    )
    _drive(
        observer,
        {
            "event": "tool_start",
            "run_id": "run-1",
            "call_id": "call-1",
            "name": "bash",
            "arguments": {"command": "sleep 999"},
        },
    )
    _drive(
        observer,
        {
            "event": "run_terminal_reconcile",
            "run_id": "run-1",
            "reason": "interrupted",
        },
    )
    tc = _completed_payload(manager)
    assert tc["status"] == "failed"
    # The per-run entry is reaped so it can't be reconciled twice.
    assert "run-1" not in running_tool_calls
