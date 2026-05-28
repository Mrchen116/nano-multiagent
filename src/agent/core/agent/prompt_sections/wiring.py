"""Runtime wiring helpers: convert session metadata to PromptContext.

This module is the integration point between the runtime's hook_metadata
(which carries conversation_type / participants / run_origin / …) and the
prompt-section assembler (which consumes a frozen PromptContext).

Design (feat-379 decision 4):
  runtime._run_locked builds hook_metadata from session config; this helper
  converts that metadata dict into a PromptContext so the assembler can gate
  segments (e.g. pa.communication_context enabled_when=group) without the
  runtime or loop needing to know about individual segment names.

Design (feat-379-M2 decision 3):
  resolve_flags_from_metadata merges per-agent agent_features overrides with
  FEATURE_REGISTRY default_on values.  Unknown keys are silently dropped so
  legacy/future sessions with stale flag sets don't break production.

Pure core module: no imports from the platform or products layers.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from agent.core.agent.prompt_sections.base import PromptContext


def build_prompt_context_from_metadata(
    *,
    metadata: Mapping[str, Any],
    available_tools: Sequence,
    available_skills: Sequence,
    current_datetime: str,
    cwd: str,
    memory_block: str | None,
    user_profile_block: str | None = None,
    flags: Mapping[str, bool],
    vars: Mapping[str, str] | None = None,
) -> PromptContext:
    """Build a frozen PromptContext from a runtime metadata dict.

    Extracts the scenario-relevant fields from hook_metadata (conversation_type,
    agent_id, participants, participant_agent_ids, group_reply_policy, run_origin)
    and packages them into PromptContext.scenario so segment render functions
    can read them without knowing the raw metadata schema.

    Args:
        metadata: Hook metadata dict from runtime._run_locked (or session config).
        available_tools: Active ToolSpec tuple for this turn.
        available_skills: Active SkillMetadata tuple for this turn.
        current_datetime: Session-created-at ISO string.
        cwd: Current working directory string.
        memory_block: Pre-rendered MemoryStore snapshot or None.
        user_profile_block: Pre-rendered USER.md snapshot or None (decision 6).
        flags: Per-agent feature flags (key → bool).
        vars: Freeform string vars (e.g. "custom_prompt").

    Returns:
        Immutable PromptContext ready for assemble_system_prompt.
    """
    # Extract scenario fields; only include keys that are actually present so
    # segments can distinguish "key absent" from "key = None".
    scenario: dict[str, Any] = {}
    _copy_if_present(metadata, scenario, "conversation_type")
    _copy_if_present(metadata, scenario, "agent_id")
    _copy_if_present(metadata, scenario, "participants")
    _copy_if_present(metadata, scenario, "participant_agent_ids")
    _copy_if_present(metadata, scenario, "group_reply_policy")
    _copy_if_present(metadata, scenario, "run_origin")

    return PromptContext(
        available_tools=tuple(available_tools),
        available_skills=tuple(available_skills),
        current_datetime=current_datetime,
        cwd=cwd,
        memory_block=memory_block,
        user_profile_block=user_profile_block,
        flags=dict(flags),
        scenario=scenario,
        vars=dict(vars) if vars else {},
    )


def resolve_flags_from_metadata(
    *,
    metadata: Mapping[str, Any],
) -> dict[str, bool]:
    """Merge per-agent agent_features overrides with FEATURE_REGISTRY default_on values.

    Args:
        metadata: Session metadata dict that may contain ``agent_features``
            (dict[str, bool] set by Gateway for the owning agent).

    Returns:
        Merged flags dict: FEATURE_REGISTRY default_on values as baseline,
        with per-agent overrides applied on top.  Unknown keys (not in
        FEATURE_REGISTRY) in agent_features are silently dropped so stale
        or forward-compat flag sets never break production.

    Notes:
        Pure function (no side effects, no IO) — safe to call from any layer.
        Imported lazily from FEATURE_REGISTRY to keep this module pure core.
    """
    # Lazy import to avoid import-time overhead on every module load.
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY  # noqa: PLC0415

    # Start with registry defaults.
    flags: dict[str, bool] = {key: entry["default_on"] for key, entry in FEATURE_REGISTRY.items()}

    # Apply per-agent overrides; unknown keys are dropped (future-proof).
    raw_overrides = metadata.get("agent_features")
    if isinstance(raw_overrides, dict):
        for key, value in raw_overrides.items():
            if key in flags and isinstance(value, bool):
                flags[key] = value

    return flags


def _copy_if_present(src: Mapping[str, Any], dst: dict[str, Any], key: str) -> None:
    """Copy key from src to dst only when key is present in src."""
    if key in src:
        dst[key] = src[key]
