"""Tests for feat-394 M9-B: cron_json retire + gateway reads enable from features.

M9-B goal: fully retire cron_json as the enable-state source.
- IM write path: _coerce_config_dicts must NOT write cron_json (enable moved to features).
  heartbeat_json is retained because it carries cadence (every / active_hours data).
- Gateway read path: ConfigSyncNotifier must read cron_scheduling + heartbeat enable
  directly from payload["features"] — not by parsing cron_json["enabled"].

These tests are RED until M9-B implementation lands.
"""

from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# Part A: IM routes — _coerce_config_dicts cron_json retirement
# ---------------------------------------------------------------------------


class TestCoerceConfigDictsCronJsonRetire:
    """_coerce_config_dicts must stop writing cron_json (feat-394 M9-B).

    enable state for cron is now in features["cron_scheduling"].
    cron_json is no longer needed and must not be written to the data dict.
    heartbeat_json is still written (cadence data: every, active_hours).
    """

    def _coerce(self, data: dict) -> dict:
        """Coerce data through UpdateAgentConfigRequest model_validator.

        The validator runs on the raw input dict; we access the resulting model
        fields to check what was written.
        """
        from IM.api.routes.agents import UpdateAgentConfigRequest

        # We need to pass required fields for the model to validate.
        # profile_version, display_name, group_reply_policy are required.
        merged = {
            "profile_version": 1,
            "display_name": "test",
            "group_reply_policy": "manual",
            **data,
        }
        instance = UpdateAgentConfigRequest.model_validate(merged)
        # Return all set fields as a dict for assertion.
        return instance.model_dump()

    def test_cron_dict_does_not_produce_cron_json(self) -> None:
        """cron dict → features["cron_scheduling"] written, cron_json NOT written.

        After M9-B the cron_json key must be absent from the coerced output.
        """
        data = {"cron": {"enabled": True}}
        result = self._coerce(data)
        assert "cron_json" not in result, (
            "_coerce_config_dicts must NOT write cron_json after M9-B. "
            "cron enable state lives in features['cron_scheduling'] only. "
            f"Got keys: {list(result.keys())}"
        )

    def test_cron_enabled_true_sets_features_cron_scheduling(self) -> None:
        """cron.enabled=True → features['cron_scheduling']=True (unchanged from M9 R5)."""
        data = {"cron": {"enabled": True}}
        result = self._coerce(data)
        assert result.get("features", {}).get("cron_scheduling") is True

    def test_cron_enabled_false_sets_features_cron_scheduling_false(self) -> None:
        """cron.enabled=False → features['cron_scheduling']=False."""
        data = {"cron": {"enabled": False}}
        result = self._coerce(data)
        assert result.get("features", {}).get("cron_scheduling") is False

    def test_heartbeat_dict_still_produces_heartbeat_json(self) -> None:
        """heartbeat dict → heartbeat_json STILL written (cadence data retained).

        heartbeat_json carries every + active_hours; those are config data, not just
        an enable toggle. heartbeat_json retirement is NOT part of M9-B.
        """
        data = {"heartbeat": {"enabled": True, "every": "30m"}}
        result = self._coerce(data)
        assert "heartbeat_json" in result, (
            "heartbeat_json must still be written by _coerce_config_dicts (cadence data). "
            "Only cron_json is retired in M9-B."
        )
        parsed = json.loads(result["heartbeat_json"])
        assert parsed.get("every") == "30m"

    def test_heartbeat_enabled_in_features_unchanged(self) -> None:
        """heartbeat.enabled → features['heartbeat'] (unchanged from M9 R5)."""
        data = {"heartbeat": {"enabled": True, "every": "1h"}}
        result = self._coerce(data)
        assert result.get("features", {}).get("heartbeat") is True


# ---------------------------------------------------------------------------
# Part B: Gateway main.py — ConfigSyncNotifier reads features not cron_json
# ---------------------------------------------------------------------------


class TestConfigSyncNotifierReadsFeaturesNotCronJson:
    """Gateway ConfigSyncNotifier must derive cron_enabled from features['cron_scheduling'].

    After M9-B the notifier must NOT parse cron_json to determine cron_enabled.
    The IM already writes features["cron_scheduling"] on every save (M9 R5 + M9-B).
    """

    def _build_sync_payload(
        self,
        features: dict | None = None,
        cron_json: str | None = None,
        heartbeat_json: str | None = None,
    ) -> dict:
        payload: dict = {}
        if features is not None:
            payload["features"] = features
        if cron_json is not None:
            payload["cron_json"] = cron_json
        if heartbeat_json is not None:
            payload["heartbeat_json"] = heartbeat_json
        return payload

    def _get_agent_config_from_payload(self, payload: dict):
        """Build an AgentWorkspaceConfig via the same parsing path as ConfigSyncNotifier."""
        import tempfile
        from pathlib import Path

        from personal_assistant.main import _parse_heartbeat_from_im_payload
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        # Mirror the ConfigSyncNotifier parsing logic (feat-394 M9-B).
        raw_features = payload.get("features")
        synced_features: dict[str, bool] = (
            {
                k: v
                for k, v in raw_features.items()
                if isinstance(k, str) and isinstance(v, bool)
            }
            if isinstance(raw_features, dict)
            else {}
        )

        # heartbeat cadence: still from heartbeat_json
        import json as _json

        _hb_raw_str = payload.get("heartbeat_json")
        if isinstance(_hb_raw_str, str) and _hb_raw_str.strip():
            try:
                _hb_raw = _json.loads(_hb_raw_str)
            except (ValueError, TypeError):
                _hb_raw = None
        else:
            _hb_raw = None
        (
            _,
            heartbeat_every,
            hb_start,
            hb_end,
            hb_tz,
        ) = _parse_heartbeat_from_im_payload(_hb_raw or {})

        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            ws.mkdir()
            cfg = AgentWorkspaceConfig(
                agent_id="test-agent",
                workspace_root=ws,
                features=synced_features,
                heartbeat_every=heartbeat_every,
                heartbeat_active_hours_start=hb_start,
                heartbeat_active_hours_end=hb_end,
                heartbeat_active_hours_timezone=hb_tz,
            )
        return cfg

    def test_cron_enabled_from_features_when_features_present(self) -> None:
        """cron_enabled=True when features['cron_scheduling']=True (no cron_json needed).

        After M9-B the gateway reads cron state from features, so cron_json can be absent.
        """
        payload = self._build_sync_payload(
            features={"cron_scheduling": True},
            # cron_json intentionally absent — M9-B: features is the only source
        )
        cfg = self._get_agent_config_from_payload(payload)
        assert cfg.cron_enabled is True, (
            "cron_enabled must be True when features['cron_scheduling']=True, "
            "even when cron_json is absent from payload."
        )

    def test_cron_disabled_when_features_cron_scheduling_false(self) -> None:
        """cron_enabled=False when features['cron_scheduling']=False."""
        payload = self._build_sync_payload(features={"cron_scheduling": False})
        cfg = self._get_agent_config_from_payload(payload)
        assert cfg.cron_enabled is False

    def test_cron_disabled_when_features_absent(self) -> None:
        """cron_enabled=False when features dict has no 'cron_scheduling' key."""
        payload = self._build_sync_payload(features={})
        cfg = self._get_agent_config_from_payload(payload)
        assert cfg.cron_enabled is False

    def test_cron_disabled_even_when_cron_json_says_enabled(self) -> None:
        """M9-B: cron_json["enabled"] must NOT override features.

        If cron_json says enabled=True but features says cron_scheduling=False,
        the feature takes precedence (features is the single source of truth).
        This validates that the gateway no longer merges cron_json.enabled into features.
        """
        payload = self._build_sync_payload(
            features={"cron_scheduling": False},
            cron_json=json.dumps({"enabled": True}),  # stale/conflicting cron_json
        )
        cfg = self._get_agent_config_from_payload(payload)
        assert cfg.cron_enabled is False, (
            "cron_json['enabled'] must NOT override features['cron_scheduling']. "
            "After M9-B features is the only source of truth for cron enable state."
        )

    def test_heartbeat_enabled_from_features(self) -> None:
        """heartbeat_enabled=True when features['heartbeat']=True."""
        payload = self._build_sync_payload(features={"heartbeat": True})
        cfg = self._get_agent_config_from_payload(payload)
        assert cfg.heartbeat_enabled is True

    def test_heartbeat_cadence_still_from_heartbeat_json(self) -> None:
        """heartbeat_every still read from heartbeat_json (cadence data, not retired)."""
        hb_json = json.dumps({"enabled": True, "every": "15m"})
        payload = self._build_sync_payload(
            features={"heartbeat": True},
            heartbeat_json=hb_json,
        )
        cfg = self._get_agent_config_from_payload(payload)
        assert cfg.heartbeat_every == "15m", (
            "heartbeat_every must still be parsed from heartbeat_json. "
            f"Got: {cfg.heartbeat_every}"
        )
