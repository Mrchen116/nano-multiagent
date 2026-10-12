"""Native classifier failure reaches public approval; allow/deny controls real writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._im_polling import poll_until
from .test_tool_approval_model_critical_path import _running_stack, _login, _agent_ids


def _approval_journey(tmp_path: Path, decision: str) -> None:
    with _running_stack(tmp_path, tool_approval_model="approval-fail") as stack:
        client = _login(stack)
        try:
            agent, _ = _agent_ids(client)
            conversation = client.create_direct_conversation(agent)
            ws = client.connect_ws()
            try:
                client.send_message(
                    conversation, "完成一次工具写入；若被拒绝则收口，不再尝试。"
                )
                frame = ws.wait_for_event("permission.request", timeout=90)
                request = frame.data["permission_request"]
                assert frame.conversation_id == conversation
                client.resolve_permission(
                    conversation,
                    request["request_id"],
                    frame.data["message_id"],
                    decision,
                )
                ws.wait_for_event("permission.resolved", timeout=30)
                ws.wait_for_event("message.completed", timeout=90)
            finally:
                ws.close()
            target = (
                Path(stack.wt_dir)
                / ".gateway-workspace"
                / agent
                / "approval-route-1.txt"
            )
            if decision == "allow_once":
                assert target.read_text() == "approval-route-1"
            else:
                assert not target.exists()
            marker = "user_allow" if decision == "allow_once" else "user_deny"

            def tools() -> list[dict]:
                return [
                    call
                    for message in client.list_messages(conversation)
                    for call in message.get("tool_calls") or []
                ]

            calls = poll_until(
                tools,
                lambda rows: any(row.get("approval") == marker for row in rows),
                timeout=15,
                interval=0.2,
                desc="persisted human approval",
            )
            assert any(
                call["name"] == "write" and call.get("approval") == marker
                for call in calls
            )
        finally:
            client.close()


@pytest.mark.e2e
def test_permission_approve_lets_tool_run(tmp_path: Path) -> None:
    """The actual file exists only after approval, with a durable public grant marker."""
    _approval_journey(tmp_path, "allow_once")


@pytest.mark.e2e
def test_permission_deny_blocks_tool(tmp_path: Path) -> None:
    """Rejection prevents the actual write and remains visible in public history."""
    _approval_journey(tmp_path, "deny")
