"""Public inbound behavior injects the configured Gateway dispatch URL."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.internal_dispatch import InternalDispatchEndpoint
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


def test_session_metadata_uses_published_listener_url_or_omits_it(
    tmp_path: Path,
) -> None:
    """A session advertises only an endpoint published by a successful listener."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    endpoint = InternalDispatchEndpoint()
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=(AgentWorkspaceConfig(agent_id="agent_a", workspace_root=workspace),),
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        gateway_internal_port=0,
        gateway_dispatch_url_provider=endpoint.current_url,
    )

    asyncio.run(pipeline.handle_inbound(_make_direct_message()))
    assert "gateway_dispatch_url" not in kernel.create_session_calls[0]["metadata"]

    endpoint.publish(host="127.0.0.1", port=43210)
    second = replace(_make_direct_message(), external_chat_id="chat_2")
    asyncio.run(pipeline.handle_inbound(second))
    assert kernel.create_session_calls[1]["metadata"]["gateway_dispatch_url"] == (
        "http://127.0.0.1:43210/internal/dispatch"
    )


def test_compose_gateway_injects_process_endpoint_provider_before_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production PA tool receives the endpoint owner created before Kernel build."""

    from personal_assistant.gateway.composition import compose_gateway
    from personal_assistant.tools.send_message import SendMessageTool

    from ._main_helpers import make_minimal_config

    endpoint = InternalDispatchEndpoint()
    captured_providers = []

    class _TrackingSendMessageTool(SendMessageTool):
        def __init__(self, *, gateway_dispatch_url_provider=None) -> None:  # noqa: ANN001
            captured_providers.append(gateway_dispatch_url_provider)
            super().__init__(
                gateway_dispatch_url_provider=gateway_dispatch_url_provider
            )

    monkeypatch.setattr(
        "personal_assistant.gateway.composition.InternalDispatchEndpoint",
        lambda: endpoint,
    )
    monkeypatch.setattr(
        "personal_assistant.product.SendMessageTool", _TrackingSendMessageTool
    )

    compose_gateway(make_minimal_config(tmp_path))

    assert len(captured_providers) == 1
    provider = captured_providers[0]
    assert callable(provider)
    assert provider() is None
    endpoint.publish(host="127.0.0.1", port=43210)
    assert provider() == "http://127.0.0.1:43210/internal/dispatch"
