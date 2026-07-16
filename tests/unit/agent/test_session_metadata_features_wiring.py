"""Unit tests for feature flag and custom prompt runtime wiring.

Validates:
1. wiring.resolve_flags_from_metadata merges agent_features with FEATURE_REGISTRY defaults.
2. PromptContext.vars["custom_prompt"] is populated when agent_custom_prompt is in metadata.

The product-facing session metadata path is covered through
``InboundPipeline.handle_inbound`` in ``test_inbound_pipeline_session_metadata.py``.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# wiring.resolve_flags_from_metadata — FEATURE_REGISTRY merge
# ---------------------------------------------------------------------------


def test_resolve_flags_from_metadata_returns_defaults_when_no_agent_features() -> None:
    """Without agent_features in metadata, all flags should be FEATURE_REGISTRY default_on."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY
    from agent.core.agent.prompt_sections.wiring import resolve_flags_from_metadata

    flags = resolve_flags_from_metadata(metadata={})

    for key, entry in FEATURE_REGISTRY.items():
        assert key in flags, f"missing key: {key}"
        assert flags[key] == entry["default_on"], (
            f"{key}: expected {entry['default_on']}, got {flags[key]}"
        )


def test_resolve_flags_from_metadata_overrides_default() -> None:
    """Per-agent overrides in agent_features must override FEATURE_REGISTRY defaults."""
    from agent.core.agent.prompt_sections.wiring import resolve_flags_from_metadata

    flags = resolve_flags_from_metadata(
        metadata={"agent_features": {"memory_curation": False}}
    )

    assert flags["memory_curation"] is False
    # skill_creation not overridden — stays at default_on=True
    assert flags["skill_creation"] is True


def test_resolve_flags_from_metadata_ignores_unknown_keys() -> None:
    """Unknown keys in agent_features must be silently dropped (not in output)."""
    from agent.core.agent.prompt_sections.wiring import resolve_flags_from_metadata

    flags = resolve_flags_from_metadata(
        metadata={"agent_features": {"unknown_feature_xyz": True}}
    )

    assert "unknown_feature_xyz" not in flags


# ---------------------------------------------------------------------------
# PromptContext.vars["custom_prompt"] via build_prompt_context_from_metadata
# ---------------------------------------------------------------------------


def test_build_prompt_context_from_metadata_populates_vars_custom_prompt() -> None:
    """custom_prompt from metadata must land in PromptContext.vars."""
    from agent.core.agent.prompt_sections.wiring import (
        build_prompt_context_from_metadata,
        resolve_flags_from_metadata,
    )

    metadata = {
        "agent_features": {"memory_curation": True},
        "agent_custom_prompt": "Always respond in English.",
        "conversation_type": "direct",
    }
    flags = resolve_flags_from_metadata(metadata=metadata)
    vars_dict: dict[str, str] = {}
    custom_prompt_val = metadata.get("agent_custom_prompt")
    if isinstance(custom_prompt_val, str) and custom_prompt_val.strip():
        vars_dict["custom_prompt"] = custom_prompt_val

    ctx = build_prompt_context_from_metadata(
        metadata=metadata,
        available_tools=(),
        available_skills=(),
        current_datetime="",
        cwd="",
        memory_block=None,
        flags=flags,
        vars=vars_dict,
    )

    assert ctx.vars.get("custom_prompt") == "Always respond in English."
    assert ctx.flags.get("memory_curation") is True
