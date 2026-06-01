"""Unit tests for feat-379-M2 R6: session metadata features/custom_prompt wiring.

Validates:
1. inbound_pipeline._build_session_metadata injects agent_features + agent_custom_prompt.
2. wiring.resolve_flags_from_metadata merges agent_features with FEATURE_REGISTRY defaults.
3. PromptContext.vars["custom_prompt"] is populated when agent_custom_prompt is in metadata.
"""

from __future__ import annotations

from typing import Any, Mapping


# ---------------------------------------------------------------------------
# inbound_pipeline._build_session_metadata — agent_features injection
# ---------------------------------------------------------------------------


def _make_pipeline(*, agent_features: dict[str, bool], custom_prompt: str | None):
    """Build a minimal InboundPipeline stub to test _build_session_metadata."""
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    agent = AgentWorkspaceConfig(
        agent_id="test-agent",
        workspace_root="/workspace/test-agent",
        features=agent_features,
        custom_prompt=custom_prompt,
    )

    class _FakeKernelClient:
        def create_session(self, **kwargs: Any) -> dict:
            return {"session_id": "sess-1"}

    class _FakeSessionStore:
        def get(self, key: str) -> None:
            return None

        def bind(self, **kwargs: Any) -> object:
            from dataclasses import dataclass

            @dataclass
            class _Binding:
                kernel_session_id: str = "sess-1"

            return _Binding()

    pipeline = InboundPipeline.__new__(InboundPipeline)
    pipeline._agents = {"test-agent": agent}
    pipeline._default_agent_id = "test-agent"
    pipeline._session_store = _FakeSessionStore()
    pipeline._kernel_client = _FakeKernelClient()
    pipeline._gateway_internal_port = 9999
    return pipeline


class _MinimalMessage:
    """Minimal InboundMessage stub for pipeline tests."""

    is_group = False
    external_chat_id = None
    metadata: dict[str, Any] = {}

    def __init__(self, metadata: dict | None = None) -> None:
        self.metadata = metadata or {}


def test_build_session_metadata_injects_agent_features() -> None:
    """_build_session_metadata must include agent_features from AgentWorkspaceConfig."""
    pipeline = _make_pipeline(
        agent_features={"memory_curation": False, "skill_creation": True},
        custom_prompt=None,
    )
    msg = _MinimalMessage()
    meta = pipeline._build_session_metadata(msg, agent_id="test-agent")

    assert meta is not None
    assert "agent_features" in meta
    assert meta["agent_features"] == {"memory_curation": False, "skill_creation": True}


def test_build_session_metadata_empty_features_still_injected() -> None:
    """agent_features must always be in metadata even when empty (runtime merges defaults)."""
    pipeline = _make_pipeline(agent_features={}, custom_prompt=None)
    msg = _MinimalMessage()
    meta = pipeline._build_session_metadata(msg, agent_id="test-agent")

    assert meta is not None
    assert "agent_features" in meta
    assert meta["agent_features"] == {}


def test_build_session_metadata_injects_custom_prompt_when_set() -> None:
    """agent_custom_prompt must be in metadata when agent.custom_prompt is non-empty."""
    pipeline = _make_pipeline(
        agent_features={}, custom_prompt="Be concise and precise."
    )
    msg = _MinimalMessage()
    meta = pipeline._build_session_metadata(msg, agent_id="test-agent")

    assert meta is not None
    assert "agent_custom_prompt" in meta
    assert meta["agent_custom_prompt"] == "Be concise and precise."


def test_build_session_metadata_omits_custom_prompt_when_none() -> None:
    """agent_custom_prompt must NOT be in metadata when agent.custom_prompt is None."""
    pipeline = _make_pipeline(agent_features={}, custom_prompt=None)
    msg = _MinimalMessage()
    meta = pipeline._build_session_metadata(msg, agent_id="test-agent")

    assert meta is not None
    assert "agent_custom_prompt" not in meta


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
