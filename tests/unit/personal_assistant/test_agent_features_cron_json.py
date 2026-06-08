"""Features dict is the single enable source; heartbeat_json still carries cadence.

When cron_scheduling moved into the features dict, the IM write path stopped
emitting the legacy cron_json enable field and the gateway read path stopped
consulting it. heartbeat_json is retained because it carries cadence (every /
active_hours), not enable state.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


def _coerce_config_dicts(data: dict) -> dict:
    from IM.api.routes.agents import UpdateAgentConfigRequest

    merged = {
        "profile_version": 1,
        "display_name": "test",
        "group_reply_policy": "manual",
        **data,
    }
    return UpdateAgentConfigRequest.model_validate(merged).model_dump()


def _config_from_payload(payload: dict):
    """Build AgentWorkspaceConfig via the same parsing path as ConfigSyncNotifier."""
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.main import _parse_heartbeat_from_im_payload

    raw_features = payload.get("features")
    features = (
        {
            k: v
            for k, v in raw_features.items()
            if isinstance(k, str) and isinstance(v, bool)
        }
        if isinstance(raw_features, dict)
        else {}
    )
    hb_raw_str = payload.get("heartbeat_json")
    hb_raw = (
        json.loads(hb_raw_str)
        if isinstance(hb_raw_str, str) and hb_raw_str.strip()
        else {}
    )
    every, start, end, tz = _parse_heartbeat_from_im_payload(hb_raw or {})
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws"
        ws.mkdir()
        return AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=ws,
            features=features,
            heartbeat_every=every,
            heartbeat_active_hours_start=start,
            heartbeat_active_hours_end=end,
            heartbeat_active_hours_timezone=tz,
        )


def test_cron_enable_lives_in_features_not_cron_json() -> None:
    """The IM write path must not emit cron_json; cron enable lives in features."""
    result = _coerce_config_dicts({"cron": {"enabled": True}})
    assert result.get("cron_json") is None
    assert "cron_scheduling" not in (result.get("features") or {})


def test_heartbeat_dict_writes_heartbeat_json_cadence_only() -> None:
    """heartbeat dict produces heartbeat_json (cadence) and never features."""
    result = _coerce_config_dicts({"heartbeat": {"enabled": True, "every": "30m"}})
    assert json.loads(result["heartbeat_json"])["every"] == "30m"
    assert "heartbeat" not in (result.get("features") or {})


def test_gateway_reads_cron_enable_from_features() -> None:
    """cron_enabled tracks features['cron_scheduling'] and ignores stale cron_json."""
    assert (
        _config_from_payload({"features": {"cron_scheduling": True}}).cron_enabled
        is True
    )
    assert (
        _config_from_payload({"features": {"cron_scheduling": False}}).cron_enabled
        is False
    )
    assert _config_from_payload({"features": {}}).cron_enabled is False
    # A stale/conflicting cron_json must not override the features source of truth.
    conflicting = {
        "features": {"cron_scheduling": False},
        "cron_json": json.dumps({"enabled": True}),
    }
    assert _config_from_payload(conflicting).cron_enabled is False


def test_gateway_reads_heartbeat_cadence_from_heartbeat_json() -> None:
    """heartbeat_every is parsed from heartbeat_json, with enable coming from features."""
    cfg = _config_from_payload(
        {
            "features": {"heartbeat": True},
            "heartbeat_json": json.dumps({"every": "15m"}),
        }
    )
    assert cfg.heartbeat_enabled is True
    assert cfg.heartbeat_every == "15m"


def test_parse_heartbeat_payload_returns_cadence_without_enable() -> None:
    """_parse_heartbeat_from_im_payload yields (every, start, end, tz) — no enable."""
    from personal_assistant.main import _parse_heartbeat_from_im_payload

    every, start, end, tz = _parse_heartbeat_from_im_payload(
        {
            "enabled": False,
            "every": "15m",
            "active_hours": {"start": "09:00", "end": "17:00", "timezone": "UTC"},
        }
    )
    assert (every, start, end, tz) == ("15m", "09:00", "17:00", "UTC")
