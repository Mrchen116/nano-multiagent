"""Tests for feat-394-M3 R1: heartbeat_enabled/cron_enabled injected into PromptContext.vars.

CRITICAL-2 fix: inbound_pipeline._build_session_metadata must inject
heartbeat_enabled and cron_enabled into session metadata, and runtime.py
must read them into PromptContext.vars so prompt segment enabled_when gates work.

These tests are red until the R1 implementation lands.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.agent.prompt_sections.base import PromptContext
from agent.products.personal_assistant.prompt_sections import (
    _PA_HEARTBEAT,  # noqa: PLC2701
    _PA_CRON,  # noqa: PLC2701
    _PA_CRON_ROUTING,  # noqa: PLC2701
)


# ---------------------------------------------------------------------------
# Prompt segment enabled_when gates driven by vars
# ---------------------------------------------------------------------------


class TestHeartbeatCronVarsGate:
    """heartbeat/cron prompt segments must respond to vars injected from session metadata.

    feat-394 decision 5: heartbeat_enabled/cron_enabled must be passed from
    AgentWorkspaceConfig → session metadata → PromptContext.vars so segment
    enabled_when gates produce the correct output.
    """

    def _ctx_with_vars(self, **vars: str) -> PromptContext:
        return PromptContext(vars=dict(vars), scenario={})

    def test_heartbeat_segment_disabled_when_var_false(self) -> None:
        """_PA_HEARTBEAT must be disabled when vars['heartbeat_enabled'] == 'False'.

        Currently fails because the gate defaults to True and vars are never injected.
        """
        ctx = self._ctx_with_vars(heartbeat_enabled="False")
        # enabled_when returns False → segment is suppressed
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is False, (
            "_PA_HEARTBEAT must be disabled when heartbeat_enabled='False' in vars "
            "(CRITICAL-2: vars are not currently injected)"
        )

    def test_heartbeat_segment_enabled_when_var_true(self) -> None:
        """_PA_HEARTBEAT must be enabled when vars['heartbeat_enabled'] == 'True'."""
        ctx = self._ctx_with_vars(heartbeat_enabled="True")
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is True

    def test_cron_segment_enabled_when_var_true(self) -> None:
        """_PA_CRON must be enabled when vars['cron_enabled'] == 'True'.

        Currently fails because cron_enabled is never injected (defaults to False).
        """
        ctx = self._ctx_with_vars(cron_enabled="True")
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is True, (
            "_PA_CRON must be enabled when cron_enabled='True' in vars "
            "(CRITICAL-2: cron_enabled is never injected, so cron segment never renders)"
        )

    def test_cron_segment_disabled_when_var_false(self) -> None:
        """_PA_CRON must be disabled when vars['cron_enabled'] == 'False'."""
        ctx = self._ctx_with_vars(cron_enabled="False")
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is False

    def test_both_disabled_routing_segment_not_injected(self) -> None:
        """_PA_CRON_ROUTING must NOT be injected when both vars are 'False'.

        feat-394-M3 hotfix: _both_enabled used bare bool() which treats the string
        "False" as truthy. Must use the same string-safe parse as _heartbeat_enabled
        and _cron_enabled.
        """
        ctx = self._ctx_with_vars(heartbeat_enabled="False", cron_enabled="False")
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False, (
            "_PA_CRON_ROUTING must NOT be injected when both vars are 'False' "
            "(bool('False')==True bug in _both_enabled)"
        )

    def test_both_enabled_routing_segment_injected(self) -> None:
        """_PA_CRON_ROUTING must be injected when both vars are 'True'."""
        ctx = self._ctx_with_vars(heartbeat_enabled="True", cron_enabled="True")
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is True

    def test_only_heartbeat_routing_not_injected(self) -> None:
        """_PA_CRON_ROUTING must NOT be injected when only heartbeat is enabled."""
        ctx = self._ctx_with_vars(heartbeat_enabled="True", cron_enabled="False")
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False

    def test_only_cron_routing_not_injected(self) -> None:
        """_PA_CRON_ROUTING must NOT be injected when only cron is enabled."""
        ctx = self._ctx_with_vars(heartbeat_enabled="False", cron_enabled="True")
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False


# ---------------------------------------------------------------------------
# inbound_pipeline._build_session_metadata injects heartbeat/cron vars
# ---------------------------------------------------------------------------


class TestInboundPipelineVarsInjection:
    """_build_session_metadata must inject heartbeat_enabled/cron_enabled into metadata.

    feat-394-M3 CRITICAL-2 fix: these keys must appear in session_metadata so that
    runtime.py can read them into PromptContext.vars.
    """

    def _make_agent_config(
        self,
        tmp_path: Path,
        *,
        heartbeat_enabled: bool = False,
        cron_enabled: bool = False,
    ) -> "object":
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        return AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=tmp_path / "ws",
            heartbeat_enabled=heartbeat_enabled,
            cron_enabled=cron_enabled,
        )

    def test_session_metadata_contains_heartbeat_enabled(self, tmp_path: Path) -> None:
        """session_metadata must contain 'heartbeat_enabled' key when heartbeat is on.

        Currently fails because _build_session_metadata does not inject this key.
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

        # Call the real method (not the mock)
        metadata = InboundPipeline._build_session_metadata(
            pipeline, message, agent_id="test-agent"
        )

        assert metadata is not None
        assert "heartbeat_enabled" in metadata, (
            "session_metadata must contain 'heartbeat_enabled' key "
            "(CRITICAL-2: PromptContext.vars injection requires this key)"
        )
        assert metadata["heartbeat_enabled"] is True

    def test_session_metadata_contains_cron_enabled(self, tmp_path: Path) -> None:
        """session_metadata must contain 'cron_enabled' key when cron is on.

        Currently fails because _build_session_metadata does not inject this key.
        """
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
        assert "cron_enabled" in metadata, (
            "session_metadata must contain 'cron_enabled' key "
            "(CRITICAL-2: PromptContext.vars injection requires this key)"
        )
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
# runtime.py reads heartbeat_enabled/cron_enabled from hook_metadata into vars
# ---------------------------------------------------------------------------


class TestRuntimeVarsFromMetadata:
    """runtime.py build_prompt_context_from_metadata must propagate heartbeat/cron keys.

    feat-394-M3 CRITICAL-2 fix: runtime.py:408 vars dict currently only passes
    'custom_prompt'. It must also pass 'heartbeat_enabled' and 'cron_enabled'
    from hook_metadata.
    """

    def test_build_prompt_context_propagates_heartbeat_cron_vars(self) -> None:
        """build_prompt_context_from_metadata must include heartbeat/cron keys in vars.

        Currently fails because runtime.py only puts 'custom_prompt' in vars.
        """
        from agent.core.agent.prompt_sections.wiring import build_prompt_context_from_metadata

        metadata = {
            "custom_prompt": "",
            "heartbeat_enabled": True,
            "cron_enabled": False,
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
                "heartbeat_enabled": str(metadata.get("heartbeat_enabled", "")),
                "cron_enabled": str(metadata.get("cron_enabled", "")),
            },
        )

        assert ctx.vars.get("heartbeat_enabled") == "True", (
            "PromptContext.vars must contain heartbeat_enabled from hook_metadata"
        )
        assert ctx.vars.get("cron_enabled") == "False"
