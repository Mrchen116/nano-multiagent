"""Tests for feat-394 M9-E: full dead-code rip-out of cron_json read paths.

M9-B retired the cron_json *write* path; M9-E completes the rip-out:
- main.py: no _parse_cron_enabled_from_im_payload; _parse_heartbeat_from_im_payload
  returns (every, start, end, tz) 4-tuple (no enabled); enable fold removed.
- IM domain/models: AgentProfile has no cron_json field.
- IM repositories: update_profile / SELECT / _row_to_profile carry no cron_json.
- IM config_service: update_profile call carries no cron_json param.
- IM routes/agents: UpdateAgentConfigRequest / AgentConfigResponse carry no cron_json.
- heartbeat_json: still persisted (cadence data), but its enable fallback removed from
  preview endpoint (effective_hb reads features["heartbeat"] only).

These tests are RED until M9-E implementation lands.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path


# ---------------------------------------------------------------------------
# Part A: main.py — _parse_cron_enabled_from_im_payload deleted
# ---------------------------------------------------------------------------


class TestMainDeadCodeRemoval:
    """main.py dead code gates."""

    def test_parse_cron_enabled_function_deleted(self) -> None:
        """_parse_cron_enabled_from_im_payload must not exist after M9-E.

        The function is dead: enable now comes from payload["features"]["cron_scheduling"].
        """
        import importlib

        main_mod = importlib.import_module("personal_assistant.main")
        assert not hasattr(main_mod, "_parse_cron_enabled_from_im_payload"), (
            "_parse_cron_enabled_from_im_payload still present; "
            "must be deleted in M9-E (enable comes from features, not cron parsing)"
        )

    def test_parse_heartbeat_returns_4_tuple_no_enabled(self) -> None:
        """_parse_heartbeat_from_im_payload returns (every, start, end, tz) — no enabled.

        After M9-E the function carries cadence data only; enable comes from features.
        Return type is tuple[str|None, str|None, str|None, str|None].
        """
        import importlib

        main_mod = importlib.import_module("personal_assistant.main")
        fn = main_mod._parse_heartbeat_from_im_payload

        result = fn({"enabled": True, "every": "10m"})
        assert len(result) == 4, (
            f"_parse_heartbeat_from_im_payload must return 4-tuple (every, start, end, tz); "
            f"got {len(result)}-tuple"
        )
        every, start, end, tz = result
        assert every == "10m"
        assert start is None
        assert end is None
        assert tz is None

    def test_parse_heartbeat_empty_returns_4_none(self) -> None:
        """Empty raw → (None, None, None, None)."""
        import importlib

        main_mod = importlib.import_module("personal_assistant.main")
        result = main_mod._parse_heartbeat_from_im_payload({})
        assert len(result) == 4
        assert all(v is None for v in result), (
            f"empty heartbeat raw must return 4×None; got {result}"
        )

    def test_parse_heartbeat_non_dict_returns_4_none(self) -> None:
        """Non-dict raw → (None, None, None, None) (not 5-tuple with False first)."""
        import importlib

        main_mod = importlib.import_module("personal_assistant.main")
        result = main_mod._parse_heartbeat_from_im_payload(None)
        assert len(result) == 4
        assert all(v is None for v in result)


# ---------------------------------------------------------------------------
# Part B: IM domain model — cron_json field removed
# ---------------------------------------------------------------------------


class TestAgentProfileNoCronJson:
    """AgentProfile domain model must not carry cron_json after M9-E."""

    def test_agent_profile_has_no_cron_json_field(self) -> None:
        """AgentProfile dataclass must not have cron_json after M9-E.

        cron enable state is in features["cron_scheduling"]; the raw JSON column
        is dead storage with no read path.
        """
        from IM.domain.models import AgentProfile

        field_names = {f.name for f in dataclasses.fields(AgentProfile)}
        assert "cron_json" not in field_names, (
            "AgentProfile still has cron_json field; must be removed in M9-E"
        )

    def test_agent_profile_still_has_heartbeat_json_field(self) -> None:
        """AgentProfile must still carry heartbeat_json (cadence data: every/active_hours)."""
        from IM.domain.models import AgentProfile

        field_names = {f.name for f in dataclasses.fields(AgentProfile)}
        assert "heartbeat_json" in field_names, (
            "AgentProfile lost heartbeat_json; must be retained for cadence (every/active_hours)"
        )


# ---------------------------------------------------------------------------
# Part C: IM repositories — update_profile has no cron_json param
# ---------------------------------------------------------------------------


class TestRepositoryNoCronJson:
    """AgentProfileRepository.update_profile must not accept cron_json after M9-E."""

    def test_update_profile_signature_no_cron_json(self) -> None:
        """update_profile must not have cron_json parameter."""
        from IM.infra.repositories import AgentProfileRepository

        sig = inspect.signature(AgentProfileRepository.update_profile)
        assert "cron_json" not in sig.parameters, (
            "update_profile still accepts cron_json; must be removed in M9-E"
        )

    def test_update_profile_signature_keeps_heartbeat_json(self) -> None:
        """update_profile must still accept heartbeat_json (cadence)."""
        from IM.infra.repositories import AgentProfileRepository

        sig = inspect.signature(AgentProfileRepository.update_profile)
        assert "heartbeat_json" in sig.parameters, (
            "update_profile lost heartbeat_json; must be retained for cadence"
        )


# ---------------------------------------------------------------------------
# Part D: IM config_service — update_profile call has no cron_json param
# ---------------------------------------------------------------------------


class TestConfigServiceNoCronJson:
    """AgentConfigService.update_profile_config must not accept cron_json."""

    def test_update_profile_config_signature_no_cron_json(self) -> None:
        """update_profile_config must not have cron_json parameter."""
        from IM.application.config_service import AgentConfigService

        sig = inspect.signature(AgentConfigService.update_profile_config)
        assert "cron_json" not in sig.parameters, (
            "AgentConfigService.update_profile_config still accepts cron_json; "
            "must be removed in M9-E"
        )

    def test_update_profile_config_signature_keeps_heartbeat_json(self) -> None:
        """update_profile_config must still accept heartbeat_json (cadence)."""
        from IM.application.config_service import AgentConfigService

        sig = inspect.signature(AgentConfigService.update_profile_config)
        assert "heartbeat_json" in sig.parameters, (
            "update_profile_config lost heartbeat_json; must be retained for cadence"
        )


# ---------------------------------------------------------------------------
# Part E: IM routes/agents — request/response models have no cron_json
# ---------------------------------------------------------------------------


class TestRouteModelsNoCronJson:
    """UpdateAgentConfigRequest and AgentConfigResponse must not carry cron_json."""

    def test_update_request_has_no_cron_json_field(self) -> None:
        """UpdateAgentConfigRequest must not have cron_json after M9-E."""
        from IM.api.routes.agents import UpdateAgentConfigRequest

        fields = UpdateAgentConfigRequest.model_fields
        assert "cron_json" not in fields, (
            "UpdateAgentConfigRequest still has cron_json field; must be removed in M9-E"
        )

    def test_update_request_still_has_heartbeat_json_field(self) -> None:
        """UpdateAgentConfigRequest must still have heartbeat_json (cadence)."""
        from IM.api.routes.agents import UpdateAgentConfigRequest

        fields = UpdateAgentConfigRequest.model_fields
        assert "heartbeat_json" in fields, (
            "UpdateAgentConfigRequest lost heartbeat_json; must be retained for cadence"
        )

    def test_agent_config_response_has_no_cron_json(self) -> None:
        """AgentConfigResponse must not carry cron_json after M9-E."""
        from IM.api.routes.agents import AgentConfigResponse

        fields = AgentConfigResponse.model_fields
        assert "cron_json" not in fields, (
            "AgentConfigResponse still has cron_json field; must be removed in M9-E"
        )

    def test_agent_config_response_still_has_heartbeat_json(self) -> None:
        """AgentConfigResponse must still carry heartbeat_json (cadence)."""
        from IM.api.routes.agents import AgentConfigResponse

        fields = AgentConfigResponse.model_fields
        assert "heartbeat_json" in fields, (
            "AgentConfigResponse lost heartbeat_json; must be retained for cadence"
        )


# ---------------------------------------------------------------------------
# Part F: round-trip smoke — enable still works via features after rip-out
# ---------------------------------------------------------------------------


class TestEnableRoundTripAfterRipOut:
    """Enable propagation must still work via features after cron_json rip-out."""

    def test_sync_enable_via_features_not_cron_json(self) -> None:
        """sync path reads cron_scheduling from features dict, not from cron_json parsing.

        This validates that after cron_json rip-out the enable path still works:
        payload["features"]["cron_scheduling"] = True → agent.cron_enabled = True.
        """
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=Path("/tmp/ws"),
            features={"cron_scheduling": True},
        )
        assert agent.cron_enabled is True, (
            "cron_enabled must be True when features['cron_scheduling']=True"
        )

    def test_sync_heartbeat_enable_via_features(self) -> None:
        """Heartbeat enable via features dict still works after rip-out."""
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=Path("/tmp/ws"),
            features={"heartbeat": True},
        )
        assert agent.heartbeat_enabled is True

    def test_heartbeat_cadence_still_parsed_from_heartbeat_json(self) -> None:
        """_parse_heartbeat_from_im_payload still parses every/active_hours (cadence).

        heartbeat_json carries cadence data; the function is retained for that purpose.
        """
        import importlib

        main_mod = importlib.import_module("personal_assistant.main")
        raw = {"enabled": False, "every": "15m", "active_hours": {"start": "09:00", "end": "17:00", "timezone": "UTC"}}
        every, start, end, tz = main_mod._parse_heartbeat_from_im_payload(raw)
        assert every == "15m"
        assert start == "09:00"
        assert end == "17:00"
        assert tz == "UTC"
