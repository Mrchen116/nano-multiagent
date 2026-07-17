"""Shadow sync consumes canonical typed external conversation identity."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.runtime_protocol import (
    ExternalConversationIdentity,
    RuntimeProtocolFacts,
    attach_runtime_protocol,
)
from personal_assistant.gateway.shadow_sync import IMShadowConversationSync


def _build_sync(
    requests: list[dict[str, Any]],
) -> IMShadowConversationSync:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        requests.append({"path": request.url.path, "payload": payload})
        if request.url.path == "/im/v1/me":
            return httpx.Response(200, json={"id": "owner-a"})
        if request.url.path == "/im/v1/conversations/external/find-or-create":
            return httpx.Response(201, json={"id": "shadow-a"})
        if request.url.path == "/im/v1/conversations/shadow-a/messages":
            return httpx.Response(201, json={"id": "message-a"})
        raise AssertionError(f"unexpected request: {request.url.path}")

    async def token_getter() -> str:
        return "token-a"

    return IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=token_getter,
        owner_user_id="owner-a",
        transport=httpx.MockTransport(handler),
    )


def _message(*, metadata: dict[str, Any] | None = None) -> InboundMessage:
    return InboundMessage(
        channel_name="feishu:agent-a",
        text="hello",
        external_user_id="external-user",
        external_chat_id="channel-owned-chat-id",
        is_group=True,
        agent_id="agent-a",
        metadata=metadata or {},
    )


def test_typed_only_external_identity_creates_shadow_conversation() -> None:
    requests: list[dict[str, Any]] = []
    sync = _build_sync(requests)
    inbound = attach_runtime_protocol(
        _message(metadata={"chat_name": "Typed Team"}),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                conversation_type="group",
                trigger_source="external",
            )
        ),
    )

    conversation_id = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert conversation_id == "shadow-a"
    create_payload = requests[1]["payload"]
    assert create_payload["external_source"] == "feishu"
    assert create_payload["external_chat_id"] == "typed-chat-id"
    assert create_payload["title"] == "agent-a · Typed Team · feishu"
    assert "__runtime_protocol_facts__" not in create_payload["metadata"]


def test_typed_im_origin_is_rejected_by_shadow_adapter() -> None:
    requests: list[dict[str, Any]] = []
    sync = _build_sync(requests)
    inbound = attach_runtime_protocol(
        _message(
            metadata={
                "external_source": "feishu",
                "external_chat_id": "legacy-would-sync",
            }
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="im",
                external_chat_id="conversation-a",
                agent_id="agent-a",
                trigger_source="im",
            )
        ),
    )

    conversation_id = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert conversation_id is None
    assert requests == []


def test_legacy_external_metadata_remains_supported() -> None:
    requests: list[dict[str, Any]] = []
    sync = _build_sync(requests)
    inbound = _message(
        metadata={
            "external_source": "slack",
            "external_chat_id": "legacy-chat-id",
            "conversation_type": "group",
            "chat_name": "Legacy Team",
        }
    )

    conversation_id = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert conversation_id == "shadow-a"
    create_payload = requests[1]["payload"]
    assert create_payload["external_source"] == "slack"
    assert create_payload["external_chat_id"] == "legacy-chat-id"
    assert create_payload["title"] == "agent-a · Legacy Team · slack"
