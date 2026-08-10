"""Unit tests: Gateway /internal/dispatch endpoint (M250 R4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_dispatch_handler(
    im_manager=None,
    *,
    kernel_client=None,
    session_db_path=None,
    agent_workspace_roots=None,
    origin_sessions=None,
):
    """Build a minimal InternalDispatchHandler for testing."""
    from pathlib import Path

    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
    from personal_assistant.gateway.session_binder import GatewaySessionBinder

    catalog = None
    binder = None
    if session_db_path is not None:
        catalog = LiveAgentCatalog(
            tuple(
                AgentWorkspaceConfig(agent_id=agent_id, workspace_root=Path(root))
                for agent_id, root in (agent_workspace_roots or {}).items()
            )
        )
        binder = GatewaySessionBinder(
            catalog=catalog,
            kernel=kernel_client,
            db_path=session_db_path,
        )
        for agent_id, session_id in (origin_sessions or {}).items():
            binder.register_session_provenance(
                catalog.require(agent_id),
                kernel_session_id=session_id,
            )

    return InternalDispatchHandler(
        im_connection_manager=im_manager,
        kernel_client=kernel_client,
        session_binder=binder,
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
    result = asyncio.run(
        handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"})
    )
    assert result["ok"] is True
    assert result["conversation_id"] == "conv-1"
    manager.send_agent_message.assert_called_once()


def test_dispatch_handler_returns_error_when_no_im_manager() -> None:
    """handle() must return ok=False with error when IM manager is absent."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    handler = InternalDispatchHandler(im_connection_manager=None)
    result = asyncio.run(
        handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"})
    )
    assert result["ok"] is False
    assert "error" in result


def test_dispatch_handler_returns_error_when_im_manager_disconnected() -> None:
    """handle() must return ok=False when IM manager is not connected."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    manager = MagicMock()
    manager.connected = False

    handler = InternalDispatchHandler(im_connection_manager=manager)
    result = asyncio.run(
        handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"})
    )
    assert result["ok"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_dispatch_handler_seal_rejects_new_kernel_touch() -> None:
    """Shutdown seal makes new HTTP work unavailable without awaiting resources."""

    manager = MagicMock()
    manager.connected = True
    manager.send_agent_message = AsyncMock()
    handler = _make_dispatch_handler(im_manager=manager)

    handler.seal()
    result = await handler.handle({"text": "hi", "to": "agent_b"})

    assert result == {
        "ok": False,
        "error": "Gateway is shutting down; cannot dispatch message",
    }
    manager.send_agent_message.assert_not_called()


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
    handler = _make_dispatch_handler(
        im_manager=manager,
        kernel_client=kernel_client,
        session_db_path=Path("/tmp/test-dispatch-bindings.sqlite3"),
        agent_workspace_roots={"agent_a": "/tmp/agent-a-workspace"},
        origin_sessions={"agent_a": "sess-origin-1"},
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
    binding = handler._session_binder.lookup(  # noqa: SLF001
        "web_relay:conv-direct-1:agent_a"
    )
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
        workspace_root=Path("/tmp/agent-a-workspace"),
    )


def test_dispatch_handler_build_aiohttp_handler_returns_callable() -> None:
    """InternalDispatchHandler.build_aiohttp_handler must return a callable."""
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    handler = InternalDispatchHandler(im_connection_manager=None)
    aiohttp_handler = handler.build_aiohttp_handler()
    assert callable(aiohttp_handler)


@pytest.mark.asyncio
async def test_dispatch_ack_after_config_publish_does_not_restore_stale_binding(
    tmp_path,
) -> None:
    """An IM ack may finish the old request but cannot publish its stale row."""

    from pathlib import Path

    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
    from personal_assistant.gateway.session_binder import GatewaySessionBinder
    from personal_assistant.ws.im_connection import IMDispatchAck

    class _BlockingManager:
        connected = True

        def __init__(self) -> None:
            import asyncio

            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def send_agent_message(self, _payload):
            self.started.set()
            await self.release.wait()
            return IMDispatchAck(
                conversation_id="conv-stale-ack",
                message_id="msg-stale-ack",
                target_kind="user_id",
                target_id="user-1",
                source_agent_id="agent_a",
            )

    old_workspace = Path(tmp_path) / "old"
    new_workspace = Path(tmp_path) / "new"
    old_workspace.mkdir()
    new_workspace.mkdir()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent_a",
                workspace_root=old_workspace,
            ),
        )
    )
    binder = GatewaySessionBinder(catalog=catalog, kernel=MagicMock())
    binder.register_session_provenance(
        catalog.require("agent_a"), kernel_session_id="session-old"
    )
    manager = _BlockingManager()
    kernel = MagicMock()
    handler = InternalDispatchHandler(
        im_connection_manager=manager,
        kernel_client=kernel,
        session_binder=binder,
    )

    import asyncio

    dispatch = asyncio.create_task(
        handler.handle(
            {
                "text": "old snapshot reply",
                "to": "user-1",
                "origin_kernel_session_id": "session-old",
                "source_agent_id": "agent_a",
            }
        )
    )
    await manager.started.wait()
    current = catalog.publish(
        AgentWorkspaceConfig(agent_id="agent_a", workspace_root=new_workspace)
    )
    binder.invalidate_stale("agent_a", current_revision=current.revision)
    manager.release.set()
    result = await dispatch

    assert result["ok"] is True
    assert binder.lookup("web_relay:conv-stale-ack:agent_a") is None
    assert kernel.append_message.call_args.kwargs["workspace_root"] == old_workspace


@pytest.mark.asyncio
async def test_dispatch_from_old_session_keeps_captured_provenance_after_publish(
    tmp_path,
) -> None:
    """A running old session cannot be relabelled as the current Agent revision."""

    from pathlib import Path
    from types import SimpleNamespace

    from personal_assistant.channels.base import InboundMessage, ReplyContext
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
    from personal_assistant.gateway.session_binder import (
        GatewaySessionBinder,
        SessionBindingRequest,
    )
    from personal_assistant.ws.im_connection import IMDispatchAck

    old_workspace = Path(tmp_path) / "old"
    new_workspace = Path(tmp_path) / "new"
    old_workspace.mkdir()
    new_workspace.mkdir()
    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="agent_a", workspace_root=old_workspace),)
    )
    kernel = MagicMock()
    kernel.create_session = AsyncMock(
        return_value=SimpleNamespace(session_id="session-old")
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=kernel,
    )
    message = InboundMessage(
        channel_name="web_relay",
        text="start",
        external_user_id="user",
        external_chat_id="source",
        is_group=False,
        agent_id="agent_a",
    )
    await binder.resolve(
        SessionBindingRequest(
            session_key="web_relay:source:agent_a",
            reply_context=ReplyContext("web_relay", "source"),
            message=message,
            gateway_internal_port=8089,
        ),
        catalog.require("agent_a"),
    )
    current = catalog.publish(
        AgentWorkspaceConfig(agent_id="agent_a", workspace_root=new_workspace)
    )
    binder.invalidate_stale("agent_a", current_revision=current.revision)
    manager = MagicMock(connected=True)
    manager.send_agent_message = AsyncMock(
        return_value=IMDispatchAck(
            conversation_id="target-conv",
            message_id="target-msg",
            target_kind="user_id",
            target_id="target-user",
            source_agent_id="agent_a",
        )
    )
    handler = InternalDispatchHandler(
        im_connection_manager=manager,
        kernel_client=kernel,
        session_binder=binder,
    )

    result = await handler.handle(
        {
            "text": "from old run",
            "to": "target-user",
            "origin_kernel_session_id": "session-old",
            "source_agent_id": "agent_a",
        }
    )

    assert result["ok"] is True
    assert binder.lookup("web_relay:target-conv:agent_a") is None
    assert kernel.append_message.call_args.kwargs["workspace_root"] == old_workspace
