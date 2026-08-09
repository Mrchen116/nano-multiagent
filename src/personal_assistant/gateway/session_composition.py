"""Project live Agent snapshots into complete Kernel session runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agent.sdk import PromptSlots, SessionRuntimeConfig

from personal_assistant.config.model_reasoning import ModelReasoningCatalog
from personal_assistant.gateway.agent_catalog import LiveAgentSnapshot
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
) -> ProjectedAgentRuntime:
    """Project one captured Agent snapshot into all future-turn settings.

    Args:
        agent: Immutable Agent snapshot selected at admission.
        scenario: Routing facts used only while rendering product prompt slots.
        resolved_model: Product-resolved model for this exact admission.
        reasoning_catalog: Gateway model capability catalog used to resolve effort.

    Returns:
        The raw SDK runtime and optional IM profile provenance.
    """

    config = agent.config
    reasoning_effort = (
        reasoning_catalog.resolve(resolved_model, config.reasoning_effort)
        if reasoning_catalog is not None
        else None
    )
    profile_version = scenario.get("config_profile_version")
    return ProjectedAgentRuntime(
        runtime=SessionRuntimeConfig(
            model=resolved_model,
            prompt=prompt_for(config, scenario=scenario),
            skills=_session_skills(config),
            enabled_tools=resolve_enabled_tools(config),
            features=dict(config.features),
            reasoning_effort=reasoning_effort,
        ),
        profile_version=profile_version if isinstance(profile_version, int) else None,
    )


def project_agent_session_capabilities(
    agent: LiveAgentSnapshot,
    *,
    scenario: Mapping[str, object],
) -> AgentSessionCapabilities:
    """Project the non-model subset for legacy callers during migration."""

    config = agent.config
    return AgentSessionCapabilities(
        prompt=prompt_for(config, scenario=scenario),
        skills=_session_skills(config),
        enabled_tools=resolve_enabled_tools(config),
        features=dict(config.features),
    )


__all__ = [
    "AgentSessionCapabilities",
    "ProjectedAgentRuntime",
    "project_agent_runtime",
    "project_agent_session_capabilities",
]
