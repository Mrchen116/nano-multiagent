"""heartbeat/cron gate behavior tests.

Covers the inbound_pipeline session_metadata contract and verifies that vars
no longer control the segment gates (gate migrated from ctx.vars to ctx.flags
via FEATURE_REGISTRY).  Comprehensive flags gate tests live in
test_prompt_section_feature_flags.py.
"""

from __future__ import annotations

from pathlib import Path

# refactor-406-M2: products/ dissolved. The PA heartbeat/cron *gate* behavior (segments
# appear per feature flag) now lives in the PA factory prompt_for + is covered by
# test_prompt_section_feature_flags.py and the skeleton golden (pa_heartbeat_on /
# pa_cron_on cases). The old _PA_*.enabled_when PromptSection-gate tests are removed
# with the PromptSection objects; the inbound_pipeline / runtime / preview-provider
# tests below are products-independent and retained.


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

    def test_session_metadata_no_standalone_heartbeat_cron_keys(
        self, tmp_path: Path
    ) -> None:
        """session_metadata must NOT contain standalone heartbeat_enabled/cron_enabled keys.

        Gate state lives in agent_features; standalone keys were retired when the
        vars-injection path was removed.
        """
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
        assert "heartbeat_enabled" not in metadata, (
            "_build_session_metadata must not inject standalone heartbeat_enabled "
            "— gate state lives in agent_features"
        )
        assert "cron_enabled" not in metadata, (
            "_build_session_metadata must not inject standalone cron_enabled "
            "— gate state lives in agent_features"
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
