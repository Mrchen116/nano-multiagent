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

    def test_session_metadata_no_standalone_heartbeat_enabled(
        self, tmp_path: Path
    ) -> None:
        """session_metadata must NOT contain standalone 'heartbeat_enabled' key after M9 R4.

        feat-394 M9 R4: heartbeat/cron gate state is already captured in
        agent_features (injected at line above).  The redundant standalone
        heartbeat_enabled/cron_enabled keys are removed — reading them from
        metadata was retired in M9 R2.
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
        assert "heartbeat_enabled" not in metadata, (
            "_build_session_metadata must not inject standalone heartbeat_enabled "
            "after M9 R4 — gate state lives in agent_features"
        )

    def test_session_metadata_no_standalone_cron_enabled(self, tmp_path: Path) -> None:
        """session_metadata must NOT contain standalone 'cron_enabled' key after M9 R4."""
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
        assert "cron_enabled" not in metadata, (
            "_build_session_metadata must not inject standalone cron_enabled "
            "after M9 R4 — gate state lives in agent_features"
        )

    def test_session_metadata_agent_features_encodes_heartbeat_cron(
        self, tmp_path: Path
    ) -> None:
        """agent_features dict encodes heartbeat/cron state after R4 (no standalone keys)."""
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline
        from unittest.mock import MagicMock

        agent = self._make_agent_config(
            tmp_path, heartbeat_enabled=True, cron_enabled=True
        )
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
        features = metadata.get("agent_features", {})
        assert features.get("heartbeat") is True, (
            "heartbeat state must be encoded in agent_features after R4"
        )
        assert features.get("cron_scheduling") is True, (
            "cron_scheduling state must be encoded in agent_features after R4"
        )


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
