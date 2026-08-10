"""Integration coverage for post-terminal self-evolution Skill activation."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path

import pytest

from agent.core.llm.config import (
    LLMConfigPayload,
    LLMModelPayload,
    LLMProviderPayload,
)
from agent.core.llm.interfaces import LLMToolCall
from agent.sdk import LLMConfig, build_kernel
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    HeartbeatConfig,
    GatewayLifecycleConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import SessionBindingStore
from tests.helpers.self_evolution import (
    FOREGROUND_REPLY,
    SKILL_CONTENT,
    SKILL_NAME,
    SelfEvolutionLLM,
    allow_all,
    wait_for_terminal,
)


@pytest.mark.asyncio
async def test_post_terminal_skill_create_reaches_gateway_config_sync(
    tmp_path: Path,
) -> None:
    """A real late review refreshes Gateway config through its persistent owner."""
    review_gate = asyncio.Event()
    client = SelfEvolutionLLM(
        foreground_replies=(FOREGROUND_REPLY,),
        review_tool_call=LLMToolCall(
            call_id="late-skill-create-call",
            name="skill_manage",
            arguments={
                "action": "create",
                "name": SKILL_NAME,
                "scope": "agent",
                "content": SKILL_CONTENT,
            },
        ),
        review_gate=review_gate,
    )
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        can_use_tool=allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    agent_id = "agent-self-evolution"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-test"),
        agents=(
            AgentWorkspaceConfig(
                agent_id=agent_id,
                workspace_root=tmp_path,
                skills=(),
                skills_selection_mode="default_discovery",
                tool_allowlist=("skill_manage",),
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=LLMConfigPayload(
            default_model="test-model",
            providers=(
                LLMProviderPayload(
                    name="openai_compat",
                    base_url="http://127.0.0.1:1",
                    models=(LLMModelPayload(name="test-model"),),
                ),
            ),
        ),
        source_path=tmp_path / "gateway.yaml",
    )
    catalog = LiveAgentCatalog(local_config.agents)
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
    )
    config_sync = IMAgentConfigSync(
        base_url="http://im.invalid",
        token=None,
        agent_catalog=catalog,
        session_binder=binder,
        local_config=local_config,
    )
    skill_sync_completed = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle_skill_created(
        callback_agent_id: str, event: Mapping[str, object]
    ) -> None:
        config_sync.handle_skill_created(callback_agent_id, event)
        loop.call_soon_threadsafe(skill_sync_completed.set)

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        skill_created_handler=_handle_skill_created,
    )
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["skill_manage"],
            features={},
            metadata={
                "self_evolution": {
                    "enabled": True,
                    "skill_creation": True,
                    "memory_curation": False,
                    "skill_nudge_interval": 1,
                    "memory_nudge_interval": 100,
                }
            },
        )
        initial_revision = catalog.require(agent_id).revision
        run = kernel.submit(
            session_id=session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "Solve one complex task."}],
        )
        await asyncio.wait_for(wait_for_terminal(kernel, run.run_id), timeout=2)

        outcome = await manager.ensure_after_foreground_terminal(
            BackgroundSubscriptionRequest(
                session_id=session.session_id,
                after_sequence=run.start_sequence,
                reply_context=None,
                agent_id=agent_id,
            )
        )
        review_gate.set()
        await asyncio.wait_for(skill_sync_completed.wait(), timeout=5)

        assert outcome.value == "started"
        refreshed = catalog.require(agent_id)
        assert refreshed.revision > initial_revision
        assert refreshed.config.skills_selection_mode == "default_discovery"
        assert refreshed.config.skills == ()
        skill_path = tmp_path / ".nanoassistant" / "skills" / SKILL_NAME / "SKILL.md"
        assert skill_path.read_text(encoding="utf-8") == SKILL_CONTENT
    finally:
        review_gate.set()
        await manager.aclose(asyncio.get_running_loop().time() + 1)
        config_sync.close()
        await kernel.aclose()
