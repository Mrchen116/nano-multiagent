"""Authenticated shadow-sync identity test."""

from __future__ import annotations

import asyncio
import json

import httpx

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.runtime_protocol import ShadowConversationRef
from personal_assistant.gateway.shadow_sync import IMShadowConversationSync


def test_external_shadow_sync_uses_authenticated_im_user_not_stale_config_user() -> (
    None
):
    """External shadow writes use the Bearer-token user, not config.node.user_id."""
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = {}
        if request.content:
            payload = dict(json.loads(request.content.decode("utf-8")))
        requests.append({"path": request.url.path, "payload": payload})
        if request.url.path == "/im/v1/me":
            return httpx.Response(
                200,
                json={
                    "id": "actual-user",
                    "user_id": "actual-user",
                    "username": "nano",
                    "display_name": "Nano",
                    "owner_id": "actual-user",
                    "owned_node_ids": [],
                    "default_entry_node_id": None,
                    "locale": "en",
                    "created_at": "2026-07-02T00:00:00Z",
                },
            )
        if request.url.path == "/im/v1/conversations/external/find-or-create":
            assert payload["participant_ids"] == [
                "user:actual-user",
                "agent:agent-a",
            ]
            return httpx.Response(201, json={"id": "conv-shadow"})
        if request.url.path == "/im/v1/conversations/conv-shadow/messages":
            assert payload["sender_user_id"] == "actual-user"
            assert payload["suppress_relay"] is True
            return httpx.Response(201, json={"id": "msg-shadow"})
        raise AssertionError(f"unexpected request: {request.url.path}")

    client = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=lambda: _async_value("token-1"),
        owner_user_id="stale-config-user",
        transport=httpx.MockTransport(handler),
    )
    inbound = InboundMessage(
        channel_name="feishu:agent-a",
        text="hello from lark",
        external_user_id="ou_user",
        external_chat_id="feishu:app:dm:ou_user",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:app:dm:ou_user",
            "sender_display_name": "你",
        },
    )

    shadow_ref = asyncio.run(client.sync_user_message(inbound, agent_id="agent-a"))

    assert shadow_ref == ShadowConversationRef(
        conversation_id="conv-shadow",
        im_message_id="msg-shadow",
    )
    assert [item["path"] for item in requests] == [
        "/im/v1/me",
        "/im/v1/conversations/external/find-or-create",
        "/im/v1/conversations/conv-shadow/messages",
    ]


async def _async_value(value: str) -> str:
    return value
