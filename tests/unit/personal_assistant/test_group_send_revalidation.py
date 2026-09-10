"""Gateway same-group tool commits share the Kernel freshness boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
from personal_assistant.tools.send_message import SendMessageTool
from personal_assistant.ws.im_connection import IMDispatchAck


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision, target, sent",
    [
        ("stale", "c_group001", False),
        ("inactive", "c_group001", False),
        ("committed", "c_group001", True),
        ("stale", "other-group", True),
    ],
)
async def test_dispatch_only_sends_a_current_same_group_candidate(
    decision, target, sent
):
    manager = SimpleNamespace(
        connected=True,
        send_agent_message=AsyncMock(
            return_value=IMDispatchAck(
                conversation_id=target,
                message_id="published-1",
                target_kind="conversation_id",
                target_id=target,
                source_agent_id="agent-a",
            )
        ),
    )
    binder = MagicMock()
    binder.find_by_kernel_session_id.return_value = SimpleNamespace(
        reply_context=SimpleNamespace(
            channel_name="web_relay", target_chat_id="c_group001"
        )
    )

    def commit(**kwargs):
        if decision == "committed":
            kwargs["publish"]()
        return decision

    kernel = SimpleNamespace(try_commit_output=commit)
    handler = InternalDispatchHandler(
        im_connection_manager=manager, kernel=kernel, session_binder=binder
    )
    result = await handler.handle(
        {
            "to": target,
            "text": "Old draft",
            "source_agent_id": "agent-a",
            "origin_kernel_session_id": "session-a",
            "origin_run_id": "run-a",
            "context_revision": 0,
            "dispatch_request_id": "call-a",
        }
    )
    assert manager.send_agent_message.called is sent
    assert result["ok"] is sent
    if not sent and decision == "stale":
        assert result["status"] == "held_for_revalidation"
        assert result["draft_id"] == "draft:run-a:call-a"
    elif not sent:
        assert "error" in result


def test_send_tool_returns_held_without_raising_or_claiming_sent():
    ctx = SimpleNamespace(
        session_id="session-a",
        tool_call_id="call-a",
        run_id="run-a",
        context_revision=0,
        revalidate_output=True,
        session_metadata={"agent_id": "agent-a"},
    )
    tool = SendMessageTool(
        gateway_dispatch_url_provider=lambda: "http://localhost/internal/dispatch"
    )
    held = {
        "ok": False,
        "status": "held_for_revalidation",
        "draft_id": "draft:run-a:call-a",
    }
    response = httpx.Response(
        200,
        json=held,
        request=httpx.Request("POST", "http://localhost/internal/dispatch"),
    )
    with patch("httpx.post", return_value=response) as post:
        result = tool.run({"target": "c_group001", "text": "Old draft"}, ctx)
    assert result["status"] == "held_for_revalidation"
    assert result["ok"] is False
    assert post.call_args.kwargs["json"]["origin_run_id"] == "run-a"
    assert post.call_args.kwargs["json"]["context_revision"] == 0
    presentation = tool.presenter.format_end(
        {"target": "c_group001", "text": "Old draft"},
        SimpleNamespace(output=result, error=None),
        10,
    )
    assert presentation.detail["status"] == "held_for_revalidation"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result, expected_status",
    [
        ({"ok": False, "status": "held_for_revalidation", "draft_id": "draft-1"}, 200),
        ({"ok": False, "error": "IM offline"}, 503),
    ],
)
async def test_dispatch_http_keeps_held_distinct_from_delivery_failure(
    result, expected_status
):
    handler = InternalDispatchHandler()
    handler.handle = AsyncMock(return_value=result)
    request = SimpleNamespace(
        json=AsyncMock(return_value={"text": "draft", "to": "group"})
    )
    response = await handler.build_aiohttp_handler()(request)
    assert response.status == expected_status
    import json

    assert json.loads(response.text) == result
