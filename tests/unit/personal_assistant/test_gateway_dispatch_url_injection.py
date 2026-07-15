"""Public inbound behavior injects the configured Gateway dispatch URL."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from tests.helpers.inbound_pipeline import build_inbound_pipeline

from ._pipeline_helpers import _FakeChannel, _FakeKernel


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


@pytest.mark.parametrize("port", [8089, 9999])
def test_inbound_session_metadata_uses_configured_dispatch_port(
    tmp_path: Path, port: int
) -> None:
    """The public turn creates a session with one exact internal dispatch URL."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent_a", workspace_root=workspace, title="Agent A"
            ),
        ),
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        gateway_internal_port=port,
    )
    result = asyncio.run(pipeline.handle_inbound(_make_direct_message()))

    assert result is not None
    assert kernel.create_session_calls[0]["metadata"]["gateway_dispatch_url"] == (
        f"http://127.0.0.1:{port}/internal/dispatch"
    )
