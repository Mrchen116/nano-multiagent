"""Real Kernel to Gateway recovery-delivery regression."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage
from agent.sdk import LLMConfig, build_kernel
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_models import InboundRunRequest, RoutedInbound
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import (
    SessionBindingStore,
    build_session_key,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from tests.unit.personal_assistant._pipeline_helpers import _FakeChannel
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


class _CancelledThenRecoveredClient:
    """Park the predecessor and complete the successor with visible text."""

    def __init__(self) -> None:
        self.first_started = asyncio.Event()
        self.requests: list[Any] = []

    async def generate(self, request: Any):  # noqa: ANN202
        self.requests.append(request)
        if len(self.requests) == 1:
            self.first_started.set()
            await asyncio.Event().wait()
        yield LLMMessage(
            role="assistant",
            content="continued without resend",
            finish_reason="stop",
        )


def _request(message, catalog: LiveAgentCatalog) -> InboundRunRequest:  # noqa: ANN001
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


@pytest.mark.asyncio
async def test_real_kernel_recovery_handoff_delivers_accepted_follower_once(
    tmp_path: Path,
) -> None:
    """Old terminal precedes linked continuation and one Gateway final delivery."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    client = _CancelledThenRecoveredClient()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),)
    )
    channel = _FakeChannel("web_relay")
    events: list[dict[str, object]] = []
    lifecycle: list[tuple[str, str, str | None]] = []

    async def _capture(message, update) -> None:  # noqa: ANN001
        lifecycle.append((message.message.text, update.phase, update.run_id))

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=GatewaySessionBinder(
            catalog=catalog,
            repository=SessionBindingStore(),
            kernel=kernel,
        ),
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        group_context_store=GroupContextStore(tmp_path / "group.sqlite3"),
        kernel_event_observer=lambda event: events.append(dict(event)),
        relay_lifecycle_callback=_capture,
    )
    message = inbound(chat_id="chat-a", text="start long work")
    try:
        primary = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
        await asyncio.wait_for(client.first_started.wait(), timeout=2)
        follower = await coordinator.dispatch(
            _request(inbound(chat_id="chat-a", text="additional context"), catalog)
        )
        assert follower.run_id
        kernel.cancel(follower.run_id)

        result = await asyncio.wait_for(primary, timeout=3)
        assert result.reply_text == "continued without resend"
        assert result.run_id != follower.run_id
        assert [item.text for item in channel.sent] == ["continued without resend"]
        assert lifecycle == [
            ("start long work", "accepted", follower.run_id),
            ("additional context", "accepted", follower.run_id),
            ("start long work", "failed", follower.run_id),
            ("additional context", "recovery_adopted", result.run_id),
            ("additional context", "running", result.run_id),
            ("additional context", "completed", result.run_id),
        ]
        old_terminal = next(
            index
            for index, event in enumerate(events)
            if event.get("run_id") == follower.run_id
            and event.get("event") == "run_status"
            and event.get("status") in {"cancelled", "failed"}
        )
        successor_queued = next(
            index
            for index, event in enumerate(events)
            if event.get("run_id") == result.run_id
            and event.get("continuation") is not None
        )
        assert old_terminal < successor_queued
        assert len(client.requests) == 2
        assert "additional context" in " ".join(
            str(item.content) for item in client.requests[-1].messages
        )
    finally:
        await kernel.aclose()
