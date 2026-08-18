"""Shared fixtures for Gateway config-operation tests."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    LLMConfigPayload,
    LLMModelPayload,
    LLMProviderPayload,
    LocalConfig,
    RuntimeConfigOwner,
)
from personal_assistant.config.model_reasoning import (
    ModelReasoningCapability,
    ModelReasoningCatalog,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.config_apply_receipts import ConfigApplyReceiptStore


def _llm() -> LLMConfigPayload:
    return LLMConfigPayload(
        default_model="test:model",
        providers=(
            LLMProviderPayload(
                name="openai_compat",
                base_url="http://127.0.0.1:1",
                models=(
                    LLMModelPayload(
                        name="test:model",
                        reasoning=ModelReasoningCapability(
                            kind="selectable",
                            default="high",
                            levels=("low", "high", "max"),
                        ),
                    ),
                ),
            ),
        ),
    )


def _agent_payload(agent: AgentWorkspaceConfig) -> dict[str, object]:
    return {
        "agent_id": agent.agent_id,
        "display_name": agent.title or agent.agent_id,
        "skills": list(agent.skills),
        "tool_allowlist": list(agent.tool_allowlist),
        "group_reply_policy": agent.group_reply_policy or "manual",
        "default_model": agent.default_model,
        "model_fallbacks": list(agent.model_fallbacks),
        "reasoning_effort": agent.reasoning_effort,
        "workspace_root": str(agent.workspace_root),
        "features": dict(agent.features),
        "custom_prompt": agent.custom_prompt,
        "heartbeat_json": None,
    }


def _sync(
    config: LocalConfig,
    *,
    receipts: ConfigApplyReceiptStore,
    phase_hook=None,
) -> IMAgentConfigSync:
    return IMAgentConfigSync(
        base_url="http://im.invalid",
        token=None,
        agent_catalog=LiveAgentCatalog(config.agents),
        session_binder=object(),  # type: ignore[arg-type]
        local_config=config,
        config_owner=RuntimeConfigOwner(config),
        workspace_root_factory=lambda agent_id: (
            config.source_path.parent / "workspaces" / agent_id
        ),
        reasoning_catalog=ModelReasoningCatalog(config.llm),
        operation_receipts=receipts,
        operation_phase_hook=phase_hook,
    )
