"""Project live Agent snapshots into complete Kernel session runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agent.sdk import PromptSlots, SessionRuntimeConfig

from personal_assistant.config.model_reasoning import ModelReasoningCatalog
from personal_assistant.gateway.agent_catalog import LiveAgentSnapshot
from personal_assistant.gateway.human_message_context import PaTimeContext
from personal_assistant.product import prompt_for, resolve_enabled_tools
from personal_assistant.config.skill_selection import (
    EXPLICIT_ALLOWLIST,
    effective_skills_selection_mode,
)


def _session_skills(config: object) -> list[str] | None:
    skills = tuple(getattr(config, "skills", ()))
    mode = effective_skills_selection_mode(
        getattr(config, "skills_selection_mode", None), skills
    )
    return list(skills) if mode == EXPLICIT_ALLOWLIST else None


@dataclass(frozen=True, slots=True)
class ProjectedAgentRuntime:
    """Carry a complete effective runtime and non-semantic profile provenance.

    Args:
        runtime: Every setting consumed by a future Kernel turn.
        profile_version: IM configuration generation for diagnostics only; it is
            intentionally excluded from runtime identity.
    """

    runtime: SessionRuntimeConfig
    profile_version: int | None


@dataclass(frozen=True, slots=True)
class AgentSessionCapabilities:
    """Compatibility projection for callers not yet migrated to full runtimes."""

    prompt: PromptSlots
    skills: list[str] | None
    enabled_tools: list[str]
    features: dict[str, bool] | None


def project_agent_runtime(
    agent: LiveAgentSnapshot,
    *,
    scenario: Mapping[str, object],
    resolved_model: str,
    reasoning_catalog: ModelReasoningCatalog | None = None,
    time_context: PaTimeContext | None = None,
    apply_saved_reasoning: bool = True,
) -> ProjectedAgentRuntime:
    """Project one captured Agent snapshot into all future-turn settings.

    Args:
        agent: Immutable Agent snapshot selected at admission.
        scenario: Routing facts used only while rendering product prompt slots.
        resolved_model: Product-resolved model for this exact admission.
        reasoning_catalog: Gateway model capability catalog used to resolve effort.
        time_context: Gateway-startup timezone snapshot for the stable PA prompt.
        apply_saved_reasoning: When False, use the candidate model's default
            effort instead of the Agent-saved intensity (fallback candidates).

    Returns:
        The raw SDK runtime and optional IM profile provenance.
    """

    config = agent.config
    selected_effort = config.reasoning_effort if apply_saved_reasoning else None
    reasoning_effort = (
        reasoning_catalog.resolve(resolved_model, selected_effort)
        if reasoning_catalog is not None
        else None
    )
    profile_version = scenario.get("config_profile_version")
    features = dict(config.features)
    features["include_session_created_datetime"] = False
    return ProjectedAgentRuntime(
        runtime=SessionRuntimeConfig(
            model=resolved_model,
            prompt=prompt_for(config, scenario=scenario, time_context=time_context),
            skills=_session_skills(config),
            enabled_tools=resolve_enabled_tools(config),
            features=features,
            reasoning_effort=reasoning_effort,
            workflow_size_guideline=(
                config.workflow_size_guideline
                if config.workflow_size_guideline_explicit
                or config.workflow_size_guideline != "medium"
                else None
            ),
        ),
        profile_version=profile_version if isinstance(profile_version, int) else None,
    )


def project_agent_session_capabilities(
    agent: LiveAgentSnapshot,
    *,
    scenario: Mapping[str, object],
    time_context: PaTimeContext | None = None,
) -> AgentSessionCapabilities:
    """Project the non-model subset for legacy callers during migration.

    Args:
        agent: Immutable Agent snapshot selected at admission.
        scenario: Routing facts used while rendering product prompt slots.
        time_context: Gateway-startup timezone snapshot for the stable PA prompt.

    Returns:
        Legacy capability projection with PA's internal runtime policy applied.
    """

    config = agent.config
    features = dict(config.features)
    features["include_session_created_datetime"] = False
    return AgentSessionCapabilities(
        prompt=prompt_for(config, scenario=scenario, time_context=time_context),
        skills=_session_skills(config),
        enabled_tools=resolve_enabled_tools(config),
        features=features,
    )


__all__ = [
    "AgentSessionCapabilities",
    "ProjectedAgentRuntime",
    "project_agent_runtime",
    "project_agent_session_capabilities",
]
