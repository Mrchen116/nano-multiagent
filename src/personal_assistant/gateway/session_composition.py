"""Project live Agent snapshots into Kernel session capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agent.sdk import PromptSlots

from personal_assistant.gateway.agent_catalog import LiveAgentSnapshot
from personal_assistant.product import prompt_for, resolve_enabled_tools


@dataclass(frozen=True, slots=True)
class AgentSessionCapabilities:
    """Hold the capability arguments shared by all Agent session scenarios.

    Args:
        prompt: Product prompt projected for the caller's scenario metadata.
        skills: Explicit skill subset, or ``None`` for default discovery.
        enabled_tools: Explicit tool whitelist; an empty list means no tools.
        features: Feature overrides, or ``None`` when no overrides are configured.
    """

    prompt: PromptSlots
    skills: list[str] | None
    enabled_tools: list[str]
    features: dict[str, bool] | None


def project_agent_session_capabilities(
    agent: LiveAgentSnapshot,
    *,
    scenario: Mapping[str, object],
) -> AgentSessionCapabilities:
    """Project one captured Agent revision into Kernel capability arguments.

    Args:
        agent: Immutable live Agent snapshot captured for this session operation.
        scenario: Per-session routing facts used only to render scenario-aware prompt slots.

    Returns:
        Capability arguments with identical restricted and empty semantics for
        foreground, heartbeat, and cron sessions.
    """

    config = agent.config
    return AgentSessionCapabilities(
        prompt=prompt_for(config, scenario=scenario),
        skills=list(config.skills) if config.skills else None,
        enabled_tools=resolve_enabled_tools(config),
        features=dict(config.features) if config.features else None,
    )


__all__ = ["AgentSessionCapabilities", "project_agent_session_capabilities"]
