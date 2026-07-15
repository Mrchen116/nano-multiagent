"""Mirror external-channel inbound messages into IM shadow conversations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.agent_config_sync import _im_http_base_url, _im_http_headers


def _metadata_text(metadata: Mapping[str, Any], *, key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

class IMShadowConversationSync:
    """Best-effort HTTP writer for external-channel shadow conversations."""

    def __init__(
        self,
        *,
        base_url: str,
        token_getter: Callable[[], Awaitable[str | None]],
        owner_user_id: str,
        timeout_seconds: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = _im_http_base_url(base_url)
        self._token_getter = token_getter
        self._owner_user_id = owner_user_id.strip()
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._resolved_owner_user_id: str | None = None

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> str | None:
        metadata = dict(message.metadata)
        external_source = _metadata_text(metadata, key="external_source")
        external_chat_id = _metadata_text(metadata, key="external_chat_id")
        if external_source is None or external_chat_id is None:
            return None
        token = await self._token_getter()
        headers = _im_http_headers(token)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout_seconds,
            trust_env=False,
            transport=self._transport,
        ) as client:
            owner_user_id = await self._resolve_owner_user_id(client)
            conversation_response = await client.post(
                "/im/v1/conversations/external/find-or-create",
                json={
                    "external_source": external_source,
                    "external_chat_id": external_chat_id,
                    "agent_id": agent_id,
                    "title": _external_shadow_title(
                        metadata, agent_id=agent_id, external_source=external_source
                    ),
                    "is_group": bool(message.is_group),
                    "participant_ids": [
                        f"user:{owner_user_id}",
                        f"agent:{agent_id}",
                    ],
                    "metadata": {
                        key: value
                        for key, value in metadata.items()
                        if isinstance(key, str)
                    },
                },
            )
            conversation_response.raise_for_status()
            conversation_payload = conversation_response.json()
            conversation_id = str(conversation_payload.get("id") or "").strip()
            if not conversation_id:
                raise ValueError("external shadow conversation response missing id")
            message_response = await client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                json={
                    "sender_user_id": owner_user_id,
                    "sender_type": "user",
                    "content": message.text,
                    "sender_display_name": _metadata_text(
                        metadata, key="sender_display_name"
                    ),
                    "suppress_relay": True,
                },
            )
            message_response.raise_for_status()
            return conversation_id

    async def _resolve_owner_user_id(self, client: httpx.AsyncClient) -> str:
        if self._resolved_owner_user_id:
            return self._resolved_owner_user_id
        response = await client.get("/im/v1/me")
        response.raise_for_status()
        payload = response.json()
        user_id = payload.get("id") or payload.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("IM /me response missing user id")
        self._resolved_owner_user_id = user_id.strip()
        return self._resolved_owner_user_id


def _external_shadow_title(
    metadata: Mapping[str, object], *, agent_id: str, external_source: str
) -> str:
    title = _metadata_text(metadata, key="conversation_title")
    if title is not None:
        return title
    chat_name = _metadata_text(metadata, key="chat_name")
    conversation_type = _metadata_text(metadata, key="conversation_type")
    if conversation_type == "group":
        return f"{agent_id} · {chat_name or '群聊'} · {external_source}"
    return f"{agent_id} · {external_source}"



