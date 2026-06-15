"""feat-409-M1/R2: Gateway tool_end forwards presentation.detail to IM.

The kernel emits ``tool_end`` events carrying a ``presentation`` dict with both
``summary`` (human one-liner) and ``detail`` (structured, presenter-produced). The
Gateway observer must forward ``detail`` verbatim into the
``node.streaming_delta`` tool_call payload — before this fix it only read
``summary`` and dropped ``detail`` (design 决策 1 / breakpoint).
"""

from __future__ import annotations

import asyncio
from typing import Any

from personal_assistant.main import _build_kernel_event_observer


class _FakeManager:
    """Capture every send_json(message_type, payload) call."""

    connected = True

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []

    async def send_json(self, message_type: str, payload: dict[str, Any]) -> None:
        self.sent.append((message_type, payload))


def _run_observer_with_tool_end(event: dict[str, Any]) -> _FakeManager:
    manager = _FakeManager()
    run_ctx = {
        "run-1": {
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "agent_id": "agent-1",
        }
    }
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_ctx,
    )

    async def _drive() -> None:
        maybe = observer(event)
        if asyncio.iscoroutine(maybe):
            await maybe
        # Observer schedules send via loop.create_task; yield so it runs.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())
    return manager


def _tool_call_payload(manager: _FakeManager) -> dict[str, Any]:
    for message_type, payload in manager.sent:
        if (
            message_type == "node.streaming_delta"
            and payload.get("kind") == "tool_call_completed"
        ):
            return payload["tool_call"]
    raise AssertionError(f"no tool_call_completed sent; got {manager.sent}")


def test_tool_end_forwards_detail() -> None:
    detail = {
        "command": "pytest -q",
        "exit_code": 0,
        "stdout": "OK",
        "stderr": "",
        "truncated": False,
    }
    event = {
        "event": "tool_end",
        "run_id": "run-1",
        "call_id": "call-1",
        "name": "bash",
        "arguments": {"command": "pytest -q", "description": "跑测试"},
        "duration_ms": 12,
        "presentation": {"summary": "跑测试", "detail": detail},
    }
    manager = _run_observer_with_tool_end(event)
    tc = _tool_call_payload(manager)
    assert tc["name"] == "bash"
    assert tc["detail"] == detail
    # summary still lands in output (decision 2: no separate summary field)
    assert tc["output"] == "跑测试"


def test_tool_end_without_detail_omits_key() -> None:
    event = {
        "event": "tool_end",
        "run_id": "run-1",
        "call_id": "call-1",
        "name": "read",
        "arguments": {"path": "a.py"},
        "duration_ms": 3,
        "presentation": {"summary": "42 lines"},
    }
    manager = _run_observer_with_tool_end(event)
    tc = _tool_call_payload(manager)
    assert tc.get("detail") is None
