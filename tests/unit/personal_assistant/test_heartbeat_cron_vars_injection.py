"""Tests for heartbeat/cron gate behavior — updated for feat-394-M9.

History:
  M3 CRITICAL-2 fix (original): inbound_pipeline injected heartbeat_enabled/cron_enabled
    into session_metadata, runtime.py read them into PromptContext.vars, and gates read vars.
  M9 decision D: gate mechanism migrated from ctx.vars to ctx.flags (FEATURE_REGISTRY).
    vars injection in runtime.py retired; flags now drive the gates.

This file is updated in M9 to test the new flags-based behavior.
Comprehensive flags gate tests live in test_m9_feature_model_gate.py;
this file retains tests for the inbound_pipeline session_metadata contract
and verifies that vars no longer control the segment gates.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.agent.prompt_sections.base import PromptContext
from agent.core.types import ToolSpec
from agent.products.personal_assistant.prompt_sections import (
    _PA_HEARTBEAT,  # noqa: PLC2701
    _PA_CRON,  # noqa: PLC2701
    _PA_CRON_ROUTING,  # noqa: PLC2701
)


# ---------------------------------------------------------------------------
# Prompt segment gates after M9: driven by flags, not vars
# ---------------------------------------------------------------------------


class TestHeartbeatCronVarsGate:
    """After M9, heartbeat/cron gates must NOT respond to ctx.vars.

    Gates are now controlled by ctx.flags (FEATURE_REGISTRY decision D).
    vars injection in runtime.py was retired in M9.
    """

    def _ctx_with_vars(self, **vars: str) -> PromptContext:
        return PromptContext(vars=dict(vars), scenario={})

    def _ctx_with_flags(self, **flags: bool) -> PromptContext:
        return PromptContext(vars={}, scenario={}, flags=dict(flags))

    def _ctx_with_flags_and_tools(self, flags: dict, tools: list[str]) -> PromptContext:
        tool_specs = tuple(
            ToolSpec(name=t, description="", input_schema={}) for t in tools
        )
        return PromptContext(vars={}, scenario={}, flags=flags, available_tools=tool_specs)

    # M9: vars no longer enable heartbeat — only flags do
    def test_heartbeat_segment_disabled_by_default_no_flags(self) -> None:
        """_PA_HEARTBEAT must be disabled when ctx.flags has no 'heartbeat' key.

        M9: heartbeat is opt-in via FEATURE_REGISTRY default_on=False.
        """
        ctx = self._ctx_with_vars()
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is False

    def test_heartbeat_segment_vars_no_longer_enable(self) -> None:
        """vars['heartbeat_enabled']='True' must NOT enable _PA_HEARTBEAT after M9.

        Gate now requires ctx.flags['heartbeat']=True.
        """
        ctx = self._ctx_with_vars(heartbeat_enabled="True")
        assert _PA_HEARTBEAT.enabled_when is not None
        # M9: vars no longer activate the gate; False is expected
        assert _PA_HEARTBEAT.enabled_when(ctx) is False, (
            "_PA_HEARTBEAT must not be enabled by vars after M9 "
            "(gate moved to ctx.flags via FEATURE_REGISTRY)"
        )

    def test_heartbeat_segment_vars_false_still_disabled(self) -> None:
        """_PA_HEARTBEAT must be disabled when ctx.flags has no 'heartbeat' key."""
        ctx = self._ctx_with_vars(heartbeat_enabled="False")
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is False

    def test_heartbeat_segment_enabled_by_flag(self) -> None:
        """_PA_HEARTBEAT must be enabled when ctx.flags['heartbeat']=True."""
        ctx = self._ctx_with_flags(heartbeat=True)
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is True

    # M9: vars no longer enable cron — only flags + tool do
    def test_cron_segment_vars_no_longer_enable(self) -> None:
        """vars['cron_enabled']='True' must NOT enable _PA_CRON after M9."""
        ctx = self._ctx_with_vars(cron_enabled="True")
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is False, (
            "_PA_CRON must not be enabled by vars after M9 "
            "(gate moved to ctx.flags + has_tool via FEATURE_REGISTRY)"
        )

    def test_cron_segment_vars_false_still_disabled(self) -> None:
        """_PA_CRON must be disabled when ctx.vars['cron_enabled']='False'."""
        ctx = self._ctx_with_vars(cron_enabled="False")
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is False

    def test_cron_segment_enabled_by_flag_and_tool(self) -> None:
        """_PA_CRON must be enabled when cron_scheduling flag=True and cron tool present."""
        ctx = self._ctx_with_flags_and_tools({"cron_scheduling": True}, ["cron"])
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is True

    def test_both_disabled_routing_segment_not_injected(self) -> None:
        """_PA_CRON_ROUTING must NOT be injected when no flags are set."""
        ctx = self._ctx_with_vars(heartbeat_enabled="False", cron_enabled="False")
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False

    def test_both_enabled_routing_segment_injected_via_flags(self) -> None:
        """_PA_CRON_ROUTING must be enabled when both flags and cron tool present."""
        ctx = self._ctx_with_flags_and_tools(
            {"heartbeat": True, "cron_scheduling": True}, ["cron"]
        )
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is True

    def test_only_heartbeat_routing_not_injected(self) -> None:
        """_PA_CRON_ROUTING must NOT be injected when only heartbeat is enabled."""
        ctx = self._ctx_with_flags_and_tools(
            {"heartbeat": True, "cron_scheduling": False}, ["cron"]
        )
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False

    def test_only_cron_routing_not_injected(self) -> None:
        """_PA_CRON_ROUTING must NOT be injected when only cron is enabled."""
        ctx = self._ctx_with_flags_and_tools(
            {"heartbeat": False, "cron_scheduling": True}, ["cron"]
        )
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False


# ---------------------------------------------------------------------------
# inbound_pipeline._build_session_metadata — session_metadata contract
# ---------------------------------------------------------------------------


class TestInboundPipelineVarsInjection:
    """_build_session_metadata must inject agent_features into metadata.

    M3 original: injected heartbeat_enabled/cron_enabled into session_metadata.
    M9: agent_features dict (feat-379) is the primary feature contract.
    heartbeat_enabled/cron_enabled are still injected (R4 cleans them up) but
    are no longer read by runtime.py into vars — they have no effect on gates.
    """

    def _make_agent_config(
        self,
        tmp_path: Path,
        *,
        heartbeat_enabled: bool = False,
        cron_enabled: bool = False,
    ) -> "object":
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        # feat-394 M9: heartbeat_enabled/cron_enabled are now @property derived from
        # features dict; constructor params removed — build features dict instead.
        features: dict = {}
        if heartbeat_enabled:
            features["heartbeat"] = True
        if cron_enabled:
            features["cron_scheduling"] = True
        ws = tmp_path / "ws"
        ws.mkdir(exist_ok=True)
        return AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=ws,
            features=features,
        )

    def test_session_metadata_contains_agent_features(self, tmp_path: Path) -> None:
        """session_metadata must contain 'agent_features' key (feat-379 contract).

        This is the primary feature contract read by resolve_flags_from_metadata.
        """
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline
        from unittest.mock import MagicMock

        agent = self._make_agent_config(tmp_path)
        pipeline = MagicMock(spec=InboundPipeline)
        pipeline._agents = {"test-agent": agent}
        pipeline._gateway_internal_port = 9999

        message = MagicMock()
        message.metadata = {}
        message.is_group = False

        metadata = InboundPipeline._build_session_metadata(
            pipeline, message, agent_id="test-agent"
        )

        assert metadata is not None
        assert "agent_features" in metadata, (
            "session_metadata must contain 'agent_features' key "
            "(feat-379 contract: resolve_flags_from_metadata reads this key)"
        )

    def test_session_metadata_contains_heartbeat_enabled(self, tmp_path: Path) -> None:
        """session_metadata still contains 'heartbeat_enabled' key (R4 cleanup pending).

        Note: runtime.py no longer reads this into vars after M9.  The key
        is present but has no effect on prompt gates.  R4 will remove the injection.
        """
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline
        from unittest.mock import MagicMock

        agent = self._make_agent_config(tmp_path, heartbeat_enabled=True)
        pipeline = MagicMock(spec=InboundPipeline)
        pipeline._agents = {"test-agent": agent}
        pipeline._gateway_internal_port = 9999

        message = MagicMock()
        message.metadata = {}
        message.is_group = False

        metadata = InboundPipeline._build_session_metadata(
            pipeline, message, agent_id="test-agent"
        )

        assert metadata is not None
        assert "heartbeat_enabled" in metadata
        assert metadata["heartbeat_enabled"] is True

    def test_session_metadata_contains_cron_enabled(self, tmp_path: Path) -> None:
        """session_metadata still contains 'cron_enabled' key (R4 cleanup pending)."""
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline
        from unittest.mock import MagicMock

        agent = self._make_agent_config(tmp_path, cron_enabled=True)
        pipeline = MagicMock(spec=InboundPipeline)
        pipeline._agents = {"test-agent": agent}
        pipeline._gateway_internal_port = 9999

        message = MagicMock()
        message.metadata = {}
        message.is_group = False

        metadata = InboundPipeline._build_session_metadata(
            pipeline, message, agent_id="test-agent"
        )

        assert metadata is not None
        assert "cron_enabled" in metadata
        assert metadata["cron_enabled"] is True

    def test_session_metadata_heartbeat_cron_false_by_default(
        self, tmp_path: Path
    ) -> None:
        """heartbeat_enabled and cron_enabled must both be False when agent has defaults."""
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline
        from unittest.mock import MagicMock

        agent = self._make_agent_config(tmp_path)
        pipeline = MagicMock(spec=InboundPipeline)
        pipeline._agents = {"test-agent": agent}
        pipeline._gateway_internal_port = 9999

        message = MagicMock()
        message.metadata = {}
        message.is_group = False

        metadata = InboundPipeline._build_session_metadata(
            pipeline, message, agent_id="test-agent"
        )

        assert metadata is not None
        assert metadata.get("heartbeat_enabled") is False
        assert metadata.get("cron_enabled") is False


# ---------------------------------------------------------------------------
# runtime.py — vars no longer contain heartbeat/cron after M9
# ---------------------------------------------------------------------------


class TestRuntimeVarsFromMetadata:
    """After M9, runtime.py vars dict must NOT contain heartbeat_enabled/cron_enabled.

    Gate is now driven by ctx.flags (from resolve_flags_from_metadata → FEATURE_REGISTRY).
    The vars injection was retired in M9 — test_m9_feature_model_gate.py has the
    definitive assertion; this class adds a complementary behavioral check.
    """

    def test_runtime_vars_only_contain_custom_prompt(self) -> None:
        """build_prompt_context_from_metadata called with no heartbeat/cron vars must not contain them.

        After M9 runtime.py only injects custom_prompt into vars.
        """
        from agent.core.agent.prompt_sections.wiring import (
            build_prompt_context_from_metadata,
        )

        metadata = {
            "custom_prompt": "hello",
        }
        ctx = build_prompt_context_from_metadata(
            metadata=metadata,
            available_tools=[],
            available_skills=[],
            current_datetime="2026-06-02T00:00:00Z",
            cwd="/tmp",
            flags={},
            vars={
                "custom_prompt": str(metadata.get("custom_prompt", "")),
            },
        )

        # After M9 runtime.py does not inject heartbeat/cron into vars
        assert "heartbeat_enabled" not in ctx.vars, (
            "PromptContext.vars must NOT contain heartbeat_enabled after M9 "
            "(gate moved to ctx.flags)"
        )
        assert "cron_enabled" not in ctx.vars, (
            "PromptContext.vars must NOT contain cron_enabled after M9 "
            "(gate moved to ctx.flags)"
        )
        # custom_prompt is still in vars
        assert ctx.vars.get("custom_prompt") == "hello"


# ---------------------------------------------------------------------------
# feat-394-M9 R2: assemble_prompt_preview uses features dict, not vars
# ---------------------------------------------------------------------------


class TestAssemblePromptPreviewFeaturesGate:
    """assemble_prompt_preview must use features dict (not heartbeat/cron_enabled params).

    feat-394-M9: heartbeat/cron gates driven by ctx.flags via features dict.
    Old heartbeat_enabled/cron_enabled params retired from assemble_prompt_preview.
    """

    def test_prompt_preview_heartbeat_disabled_by_default_features(self) -> None:
        """assemble_prompt_preview with features={} must exclude heartbeat segment.

        FEATURE_REGISTRY.heartbeat default_on=False; no heartbeat unless features
        explicitly sets {'heartbeat': True}.
        """
        from agent.core.agent.prompt_sections.wiring import (
            build_prompt_context_from_metadata,
            resolve_flags_from_metadata,
        )

        flags = resolve_flags_from_metadata(metadata={"agent_features": {}})
        ctx = build_prompt_context_from_metadata(
            metadata={"conversation_type": "direct"},
            available_tools=[],
            available_skills=[],
            current_datetime=None,
            cwd="/tmp",
            flags=flags,
            vars={"custom_prompt": ""},
        )
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is False, (
            "heartbeat segment must be disabled by default (default_on=False)"
        )

    def test_prompt_preview_heartbeat_enabled_via_features(self) -> None:
        """assemble_prompt_preview with features={'heartbeat': True} must include heartbeat."""
        from agent.core.agent.prompt_sections.wiring import (
            build_prompt_context_from_metadata,
            resolve_flags_from_metadata,
        )

        flags = resolve_flags_from_metadata(
            metadata={"agent_features": {"heartbeat": True}}
        )
        ctx = build_prompt_context_from_metadata(
            metadata={"conversation_type": "direct"},
            available_tools=[],
            available_skills=[],
            current_datetime=None,
            cwd="/tmp",
            flags=flags,
            vars={"custom_prompt": ""},
        )
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is True, (
            "heartbeat segment must be enabled when features={'heartbeat': True}"
        )

    def test_prompt_preview_cron_enabled_via_features_and_tool(self) -> None:
        """assemble_prompt_preview with features={'cron_scheduling': True} + cron tool must include cron."""
        from agent.core.agent.prompt_sections.wiring import (
            build_prompt_context_from_metadata,
            resolve_flags_from_metadata,
        )

        flags = resolve_flags_from_metadata(
            metadata={"agent_features": {"cron_scheduling": True}}
        )
        cron_tool = ToolSpec(name="cron", description="", input_schema={})
        ctx = build_prompt_context_from_metadata(
            metadata={"conversation_type": "direct"},
            available_tools=(cron_tool,),
            available_skills=[],
            current_datetime=None,
            cwd="/tmp",
            flags=flags,
            vars={"custom_prompt": ""},
        )
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is True, (
            "cron segment must be enabled when features={'cron_scheduling': True} "
            "and cron tool is present"
        )

    def test_make_prompt_preview_provider_no_heartbeat_cron_params(
        self, tmp_path: Path
    ) -> None:
        """_make_prompt_preview_provider must NOT accept heartbeat_enabled/cron_enabled.

        M9: these params are retired; callers use features dict instead.
        """
        import inspect
        from personal_assistant.main import _make_prompt_preview_provider

        class _FakeKernel:
            def assemble_prompt_preview(self, **kwargs) -> dict:
                return {"prompt": "preview", "section_count": 1}

        provider = _make_prompt_preview_provider(_FakeKernel())
        sig = inspect.signature(provider)
        assert "heartbeat_enabled" not in sig.parameters, (
            "_make_prompt_preview_provider must not accept heartbeat_enabled after M9"
        )
        assert "cron_enabled" not in sig.parameters, (
            "_make_prompt_preview_provider must not accept cron_enabled after M9"
        )
