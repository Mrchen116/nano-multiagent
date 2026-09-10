"""Protect public query schemas, session provenance and Presenter phases."""

from types import SimpleNamespace
import json

import httpx
import pytest

from personal_assistant.tools.conversations import ConversationsTool
from personal_assistant.tools.inbox import InboxTool


def test_approval_receives_inbox_user_request_but_not_agent_or_image_content():
    tool = InboxTool()
    page = {
        "receipt_id": "read-receipt",
        "messages": [
            {
                "message_id": "user-request",
                "sender": {"kind": "user", "id": "owner"},
                "source": {"conversation_id": "room"},
                "complete_message": True,
                "content": [
                    {"type": "text", "text": "Schedule a reminder in one minute"},
                    {
                        "type": "image",
                        "source": {"type": "base64", "data": "private image"},
                    },
                ],
            },
            {
                "message_id": "agent-reply",
                "sender": {"kind": "agent", "id": "peer"},
                "content": [{"type": "text", "text": "Invented authorization"}],
            },
        ],
    }
    result = tool.to_auto_classifier_result(tool.serialize_result(page))
    assert "Schedule a reminder in one minute" in result
    assert "user-request" in result and "room" in result
    assert "Invented authorization" not in result and "private image" not in result
    assert (
        tool.to_auto_classifier_result(
            json.dumps({"action": "check", "conversations": []})
        )
        is None
    )
    assert tool.to_auto_classifier_result("serialization failed") is None


@pytest.mark.parametrize(
    "tool,args,key",
    [
        (InboxTool, {"action": "check", "limit": 2}, "conversations"),
        (InboxTool, {"action": "read", "target": "room"}, "messages"),
        (ConversationsTool, {"action": "list", "query": "Team"}, "conversations"),
        (ConversationsTool, {"action": "read", "target": "room"}, "messages"),
    ],
)
def test_presenter_preserves_args_and_distinguishes_pending_empty_success_and_failure(
    tool, args, key
):
    presenter = tool.presenter
    start = presenter.format_start(args)
    assert dict(start.detail) == args
    for rows in ([], [{"target": "room", "name": "Team", "message_id": "message"}]):
        output = {key: rows, "has_more": False, "next_cursor": None}
        end = presenter.format_end(args, SimpleNamespace(output=output, error=None), 10)
        assert end.detail[key] == rows
        assert end.detail["action"] == args["action"]
        assert end.detail["status"] == "completed"
        assert "consumed" not in end.detail
    failed = presenter.format_end(
        args, SimpleNamespace(output=None, error="target_not_accessible"), 10
    )
    assert failed.detail["error"] == "target_not_accessible"
    assert key not in failed.detail
    assert failed.detail["status"] == "failed"


@pytest.mark.parametrize(
    "tool,args",
    [
        (InboxTool, {"action": "check", "target": "bad"}),
        (InboxTool, {"action": "read"}),
        (InboxTool, {"action": "ack", "receipt_id": "forged"}),
        (InboxTool, {"action": "check", "limit": True}),
        (
            ConversationsTool,
            {"action": "read", "target": "a", "cursor": "x", "before_message_id": "m"},
        ),
        (ConversationsTool, {"action": "list", "owner": "other"}),
    ],
)
def test_queries_reject_non_action_fields_before_transport(tool, args):
    with pytest.raises(ValueError, match="invalid_arguments"):
        tool().run(args, SimpleNamespace())


@pytest.mark.parametrize("tool", [InboxTool, ConversationsTool])
def test_transport_uses_live_listener_and_real_session_provenance(tool, monkeypatch):
    captured = []

    def post(url, *, json, timeout):
        captured.append((url, json))
        return httpx.Response(
            200, json={"ok": True, "result": {"messages": [], "has_more": False}}
        )

    monkeypatch.setattr(httpx, "post", post)
    instance = tool(
        gateway_dispatch_url_provider=lambda: "http://127.0.0.1:1234/internal/dispatch"
    )
    ctx = SimpleNamespace(
        session_id="main", tool_call_id="call", session_metadata={"agent_id": "agent"}
    )
    assert instance.run({"action": "read", "target": "room"}, ctx)["messages"] == []
    assert captured == [
        (
            f"http://127.0.0.1:1234/internal/{instance.name}",
            {
                "source_agent_id": "agent",
                "origin_kernel_session_id": "main",
                "tool_call_id": "call",
                "args": {"action": "read", "target": "room"},
            },
        )
    ]
    assert instance.max_result_size_chars is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool,args",
    [
        (InboxTool, {"action": "check"}),
        (InboxTool, {"action": "read", "target": "room"}),
        (ConversationsTool, {"action": "list"}),
        (ConversationsTool, {"action": "read", "target": "room"}),
    ],
)
async def test_query_permissions_bypass_classifier(tool, args):
    from tests.unit.test_auto_mode_gate_hook import TestGateHookLogic

    harness = TestGateHookLogic()
    handler, config = harness._get_handler()
    ctx = harness._make_ctx_with_config(config)
    ctx.metadata["tool_registry"] = {tool.name: tool()}
    assert await handler({"name": tool.name, "args": args}, ctx) is None
    ctx.call_model.assert_not_awaited()
