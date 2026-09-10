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
        "target": "room",
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
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "private image",
                        },
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


def test_model_inbox_read_hides_receipts_and_preserves_same_named_identities():
    page = {
        "target": "room",
        "name": "Design group",
        "receipt_id": "private-receipt",
        "has_more": False,
        "next_cursor": None,
        "messages": [
            {
                "message_id": f"message-{i}",
                "sender": {"id": f"user-{i}", "name": "Alex", "kind": "user"},
                "source_time": "2026-09-10T11:30:04.229072+08:00",
                "received_at": "2026-09-10T03:30:04.235470+00:00",
                "source": {"channel": "web_relay", "reply_target": "room"},
                "part_key": "0:text:0",
                "complete_message": True,
                "content": [{"type": "text", "text": f"Request {i}"}],
            }
            for i in range(2)
        ],
    }
    result = json.loads(InboxTool().serialize_result(page))
    assert result == {
        "type": "unknown",
        "channel": "web",
        "target": "room",
        "name": "Design group",
        "messages": [
            {
                "id": f"message-{i}",
                "sender": {"name": "Alex", "user_id": f"user-{i}", "type": "user"},
                "time": "2026-09-10T03:30:04Z",
                "text": f"Request {i}",
            }
            for i in range(2)
        ],
    }
    assert page["receipt_id"] == "private-receipt"


def test_model_inbox_preserves_mixed_content_order_partial_and_errors():
    image = {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "YWJj"},
    }
    parts = [
        {"type": "text", "text": "Before"},
        image,
        {"type": "text", "text": "After"},
        {
            "type": "attachment",
            "file_name": "notes.pdf",
            "url": "https://example.test/notes.pdf",
        },
    ]
    page = {
        "target": "room",
        "receipt_id": "receipt",
        "next_cursor": "continue-here",
        "messages": [
            {
                "message_id": "message",
                "sender": {"kind": "user", "id": "u", "name": "User"},
                "content": [part],
                "part_key": str(i),
                "complete_message": False,
            }
            for i, part in enumerate(parts)
        ],
        "errors": [
            {
                "code": "attachment_unavailable",
                "message_id": "missing",
                "part_key": "0:image",
                "retryable": True,
            }
        ],
    }
    result = InboxTool().serialize_result(page)
    assert result[1] == {"type": "image", "data": "YWJj", "mimeType": "image/png"}
    model = json.loads(result[0]["text"])
    assert len(model["messages"]) == 1
    assert model["messages"][0]["content"] == [
        parts[0],
        {"type": "image", "image_index": 0},
        *parts[2:],
    ]
    assert model["messages"][0]["partial"] is True
    assert model["next_cursor"] == "continue-here"
    assert "part_key" not in model["errors"][0]
    assert (
        json.loads(InboxTool().to_auto_classifier_result(result).split(": ", 1)[1])[0][
            "text"
        ]
        == "Before\nAfter"
    )
    assert ConversationsTool().to_auto_classifier_result(result) is None


def test_inbox_image_survives_actual_provider_request_mapping():
    from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
    from agent.platform.llm.providers.anthropic.mapper import AnthropicMapper

    page = {
        "target": "room",
        "messages": [
            {
                "message_id": "picture",
                "sender": {"kind": "user"},
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "YWJj",
                        },
                    }
                ],
            }
        ],
    }
    content = InboxTool().serialize_result(page)
    request = LLMGenerateRequest(
        model="fixture",
        session_id="main",
        messages=(LLMMessage(role="tool", content=content, tool_call_id="read-image"),),
    )
    mapped = AnthropicMapper().map_generate_request(request)
    result = mapped["messages"][0]["content"][0]
    assert result["type"] == "tool_result"
    assert result["content"][1] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "YWJj"},
    }
