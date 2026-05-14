"""Unit tests: Gateway /internal/dispatch endpoint (M250 R4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_dispatch_handler(
    im_manager=None, *, kernel_client=None, session_store=None, agent_workspace_roots=None
):
    """Build a minimal InternalDispatchHandler for testing."""
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
    return InternalDispatchHandler(
        im_connection_manager=im_manager,
        kernel_client=kernel_client,
        session_store=session_store,
        agent_workspace_roots=agent_workspace_roots,
    )


def test_dispatch_handler_returns_ok_when_im_manager_available() -> None:
    """handle() must return ok=True when IM manager is connected and send succeeds."""
    import asyncio
    from personal_assistant.ws.im_connection import IMDispatchAck

    manager = MagicMock()
    manager.connected = True
    manager.send_agent_message = AsyncMock(
        return_value=IMDispatchAck(
            conversation_id="conv-1",
            message_id="msg-1",
            target_kind="conversation_id",
            target_id="conv-1",
            source_agent_id="agent_a",
        )
    )

    handler = _make_dispatch_handler(im_manager=manager)
    result = asyncio.run(handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"}))
    assert result["ok"] is True
    assert result["conversation_id"] == "conv-1"
    manager.send_agent_message.assert_called_once()


def test_dispatch_handler_returns_error_when_no_im_manager() -> None:
    """handle() must return ok=False with error when IM manager is absent."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    handler = InternalDispatchHandler(im_connection_manager=None)
    result = asyncio.run(handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"}))
    assert result["ok"] is False
    assert "error" in result


def test_dispatch_handler_returns_error_when_im_manager_disconnected() -> None:
    """handle() must return ok=False when IM manager is not connected."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    manager = MagicMock()
    manager.connected = False

    handler = InternalDispatchHandler(im_connection_manager=manager)
    result = asyncio.run(handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"}))
    assert result["ok"] is False
    assert "error" in result


def test_dispatch_handler_validates_required_fields() -> None:
    """handle() must return ok=False when required fields are missing."""
    import asyncio

    manager = MagicMock()
    manager.connected = True
    manager.send_agent_message = AsyncMock(return_value=None)

    handler = _make_dispatch_handler(im_manager=manager)
    result = asyncio.run(handler.handle({"text": "hi"}))
    assert result["ok"] is False
    assert "error" in result


def test_dispatch_handler_binds_direct_conversation_and_appends_history() -> None:
    import asyncio
    from pathlib import Path

    from personal_assistant.gateway.session_keys import PersistentSessionBindingStore
    from personal_assistant.ws.im_connection import IMDispatchAck

    manager = MagicMock()
    manager.connected = True
    manager.send_agent_message = AsyncMock(
        return_value=IMDispatchAck(
            conversation_id="conv-direct-1",
            message_id="msg-dm-1",
            target_kind="user_id",
            target_id="user-1",
            source_agent_id="agent_a",
        )
    )
    kernel_client = MagicMock()
    session_store = PersistentSessionBindingStore(db_path=Path("/tmp/test-dispatch-bindings.sqlite3"))
    handler = _make_dispatch_handler(
        im_manager=manager,
        kernel_client=kernel_client,
        session_store=session_store,
        agent_workspace_roots={"agent_a": "/tmp/agent-a-workspace"},
    )

    result = asyncio.run(
        handler.handle(
            {
                "text": "给你个冷笑话",
                "to": "user-1",
                "from_session_id": "agent_a|tool_call:toolu_1",
                "origin_kernel_session_id": "sess-origin-1",
                "source_agent_id": "agent_a",
                "dispatch_request_id": "toolu_1",
            }
        )
    )

    assert result["ok"] is True
    binding = session_store.get("web_relay:conv-direct-1:agent_a")
    assert binding is not None
    assert binding.kernel_session_id == "sess-origin-1"
    # workspace_root is forwarded so the stateless kernel can locate the origin
    # agent's session JSONL.
    kernel_client.append_message.assert_called_once_with(
        session_id="sess-origin-1",
        role="assistant",
        content="给你个冷笑话",
        message_id="msg-dm-1",
        metadata={
            "source": "send_message",
            "conversation_id": "conv-direct-1",
            "target_kind": "user_id",
            "target_id": "user-1",
            "source_agent_id": "agent_a",
        },
        idempotency_key="dispatch-sync:toolu_1",
        workspace_root="/tmp/agent-a-workspace",
    )


def test_dispatch_handler_build_aiohttp_handler_returns_callable() -> None:
    """InternalDispatchHandler.build_aiohttp_handler must return a callable."""
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    handler = InternalDispatchHandler(im_connection_manager=None)
    aiohttp_handler = handler.build_aiohttp_handler()
    assert callable(aiohttp_handler)
