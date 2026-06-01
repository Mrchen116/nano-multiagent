"""Unit tests: InboundPipeline injects gateway_dispatch_url into session metadata (M250 R3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue


def _make_pipeline(gateway_internal_port: int = 8089) -> InboundPipeline:
    """Build a minimal InboundPipeline with the given gateway_internal_port."""
    kernel_client = MagicMock()
    agent = AgentWorkspaceConfig(
        agent_id="agent_a",
        workspace_root=Path("/tmp/agent_a"),
        title="Agent A",
    )
    registry = MagicMock()
    router = OutboundRouter(registry)
    return InboundPipeline(
        kernel=kernel_client,
        agents=(agent,),
        outbound_router=router,
        run_queue=SessionRunQueue(),
        gateway_internal_port=gateway_internal_port,
    )


def _make_direct_message() -> InboundMessage:
    return InboundMessage(
        channel_name="web_relay",
        external_user_id="user_1",
        external_chat_id="chat_1",
        text="hello",
        is_group=False,
        agent_id="agent_a",
        metadata={},
    )


def test_build_session_metadata_includes_gateway_dispatch_url() -> None:
    """_build_session_metadata must inject gateway_dispatch_url into session metadata."""
    pipeline = _make_pipeline(gateway_internal_port=8089)
    message = _make_direct_message()
    meta = pipeline._build_session_metadata(message, agent_id="agent_a")
    assert meta is not None
    assert "gateway_dispatch_url" in meta, (
        f"Expected gateway_dispatch_url in session metadata, got keys: {list(meta.keys())}"
    )
    assert "8089" in meta["gateway_dispatch_url"], (
        f"Expected port 8089 in gateway_dispatch_url, got: {meta['gateway_dispatch_url']}"
    )
    assert "/internal/dispatch" in meta["gateway_dispatch_url"]


def test_build_session_metadata_gateway_dispatch_url_respects_custom_port() -> None:
    """gateway_dispatch_url must use the configured gateway_internal_port."""
    pipeline = _make_pipeline(gateway_internal_port=9999)
    message = _make_direct_message()
    meta = pipeline._build_session_metadata(message, agent_id="agent_a")
    assert meta is not None
    assert "9999" in meta["gateway_dispatch_url"]


def test_inbound_pipeline_accepts_gateway_internal_port_kwarg() -> None:
    """InboundPipeline must accept gateway_internal_port constructor argument."""
    pipeline = _make_pipeline(gateway_internal_port=8089)
    assert hasattr(pipeline, "_gateway_internal_port")
    assert pipeline._gateway_internal_port == 8089


def test_inbound_pipeline_default_gateway_internal_port() -> None:
    """InboundPipeline must have a sensible default gateway_internal_port when not supplied."""
    kernel_client = MagicMock()
    agent = AgentWorkspaceConfig(
        agent_id="agent_a",
        workspace_root=Path("/tmp/agent_a"),
        title="Agent A",
    )
    registry = MagicMock()
    router = OutboundRouter(registry)
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=(agent,),
        outbound_router=router,
        run_queue=SessionRunQueue(),
    )
    assert hasattr(pipeline, "_gateway_internal_port")
    assert isinstance(pipeline._gateway_internal_port, int)
    assert pipeline._gateway_internal_port > 0
