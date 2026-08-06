"""Ownership regressions for IM Agent reconciliation and durable bindings."""

from pathlib import Path
from unittest.mock import MagicMock

import httpx

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from personal_assistant.channels.base import ReplyContext
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    GatewayLifecycleConfig,
    HeartbeatConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import SessionBindingStore


def test_identical_reconcile_preserves_restart_binding(tmp_path: Path) -> None:
    """A reconnect mirror read is not a config change and must not drop SQLite state."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace,
        title="Agent A",
        custom_prompt="You are Agent A.",
        group_reply_policy="MENTION",
    )
    catalog = LiveAgentCatalog((agent,))
    store = SessionBindingStore()
    store.bind(
        session_key="web_relay:conv-1:agent-a",
        kernel_session_id="session-before-restart",
        reply_context=ReplyContext(
            channel_name="web_relay",
            target_chat_id="conv-1",
        ),
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=store,
        kernel=MagicMock(),
    )
    llm = LLMConfigPayload(
        default_model="test-model",
        providers=(
            LLMProviderPayload(
                name="test",
                base_url="http://127.0.0.1:4000",
                models=(LLMModelPayload(name="test-model"),),
            ),
        ),
    )
    config = LocalConfig(
        node=NodeConfig(node_id="node-a"),
        agents=(agent,),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=llm,
        source_path=tmp_path / "config.yaml",
    )

    def _mirror(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "agent-a",
                "display_name": "Agent A",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "default_model": None,
                "features": {},
                "custom_prompt": "You are Agent A.",
                "profile_version": 1,
            },
        )

    sync = IMAgentConfigSync(
        base_url="http://im.local",
        token=None,
        agent_catalog=catalog,
        session_binder=binder,
        local_config=config,
        client=httpx.Client(
            transport=httpx.MockTransport(_mirror),
            base_url="http://im.local",
            trust_env=False,
        ),
    )

    sync.reconcile_all_agents()

    assert catalog.require("agent-a").revision == 1
    binding = binder.lookup("web_relay:conv-1:agent-a")
    assert binding is not None
    assert binding.kernel_session_id == "session-before-restart"
