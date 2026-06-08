"""Tests for feat-394-M9 R3: cron_json retire and features sole-source gate.

Covers the regression guards for M9-B (cron_json retired, features dict is the
single source of truth for enable) and M9-E (enable round-trip via features).
These were rescued from the one-time migration artifact files during test cleanup.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# feat-394 防回归: cron_json 退役 + features 唯一真源（来自 M9-B）
# ---------------------------------------------------------------------------


def _coerce_config_dicts(data: dict) -> dict:
    """Helper: run UpdateAgentConfigRequest model_validator on input dict."""
    from IM.api.routes.agents import UpdateAgentConfigRequest

    merged = {
        "profile_version": 1,
        "display_name": "test",
        "group_reply_policy": "manual",
        **data,
    }
    instance = UpdateAgentConfigRequest.model_validate(merged)
    return instance.model_dump()


def test_cron_dict_does_not_produce_cron_json() -> None:
    """_coerce_config_dicts must NOT write cron_json after M9-B (enable moved to features)."""
    result = _coerce_config_dicts({"cron": {"enabled": True}})
    assert result.get("cron_json") is None, (
        "_coerce_config_dicts must not write cron_json; enable lives in features['cron_scheduling']"
    )


def test_cron_block_is_ignored_features_is_sole_source() -> None:
    """Legacy cron block must not inject features['cron_scheduling'] (features is sole source)."""
    result = _coerce_config_dicts({"cron": {"enabled": True}})
    assert "cron_scheduling" not in (result.get("features") or {}), (
        "cron block must not write features; features field is the only cron-enable source"
    )


def test_heartbeat_dict_still_produces_heartbeat_json() -> None:
    """heartbeat dict must still produce heartbeat_json (cadence data retained after M9-B)."""
    import json

    result = _coerce_config_dicts({"heartbeat": {"enabled": True, "every": "30m"}})
    assert "heartbeat_json" in result and result["heartbeat_json"] is not None, (
        "heartbeat_json must still be written by _coerce_config_dicts (carries cadence data)"
    )
    parsed = json.loads(result["heartbeat_json"])
    assert parsed.get("every") == "30m"


def test_heartbeat_block_does_not_touch_features() -> None:
    """heartbeat block must only write heartbeat_json, not inject features['heartbeat']."""
    result = _coerce_config_dicts({"heartbeat": {"every": "1h"}})
    assert "heartbeat" not in (result.get("features") or {}), (
        "heartbeat block must not write features['heartbeat']; features is the enable sole source"
    )


# ---------------------------------------------------------------------------
# feat-394 防回归: gateway reads features not cron_json (来自 M9-B ConfigSyncNotifier)
# ---------------------------------------------------------------------------


def _get_agent_config_from_payload(payload: dict):
    """Build AgentWorkspaceConfig via the same parsing path as ConfigSyncNotifier."""
    import json as _json
    import tempfile
    from pathlib import Path

    from personal_assistant.main import _parse_heartbeat_from_im_payload
    from personal_assistant.config.local_store import AgentWorkspaceConfig

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

    _hb_raw_str = payload.get("heartbeat_json")
    if isinstance(_hb_raw_str, str) and _hb_raw_str.strip():
        try:
            _hb_raw = _json.loads(_hb_raw_str)
        except (ValueError, TypeError):
            _hb_raw = None
    else:
        _hb_raw = None
    heartbeat_every, hb_start, hb_end, hb_tz = _parse_heartbeat_from_im_payload(
        _hb_raw or {}
    )

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


def test_cron_enabled_from_features_when_features_present() -> None:
    """cron_enabled=True when features['cron_scheduling']=True (no cron_json needed)."""
    cfg = _get_agent_config_from_payload({"features": {"cron_scheduling": True}})
    assert cfg.cron_enabled is True


def test_cron_disabled_when_features_cron_scheduling_false() -> None:
    """cron_enabled=False when features['cron_scheduling']=False."""
    cfg = _get_agent_config_from_payload({"features": {"cron_scheduling": False}})
    assert cfg.cron_enabled is False


def test_cron_disabled_when_features_absent() -> None:
    """cron_enabled=False when features dict has no 'cron_scheduling' key."""
    cfg = _get_agent_config_from_payload({"features": {}})
    assert cfg.cron_enabled is False


def test_cron_disabled_even_when_cron_json_says_enabled() -> None:
    """cron_json['enabled'] must NOT override features (features is single source of truth)."""
    import json

    cfg = _get_agent_config_from_payload(
        {
            "features": {"cron_scheduling": False},
            "cron_json": json.dumps({"enabled": True}),  # stale/conflicting cron_json
        }
    )
    assert cfg.cron_enabled is False, (
        "cron_json['enabled'] must not override features['cron_scheduling'] after M9-B"
    )


def test_heartbeat_cadence_still_from_heartbeat_json() -> None:
    """heartbeat_every must still be parsed from heartbeat_json (cadence data, not retired)."""
    import json

    hb_json = json.dumps({"enabled": True, "every": "15m"})
    cfg = _get_agent_config_from_payload(
        {
            "features": {"heartbeat": True},
            "heartbeat_json": hb_json,
        }
    )
    assert cfg.heartbeat_every == "15m"


# ---------------------------------------------------------------------------
# feat-394 防回归: enable round-trip via features（来自 M9-E）
# ---------------------------------------------------------------------------


def test_sync_enable_via_features_not_cron_json(tmp_path) -> None:
    """cron_enabled=True when features['cron_scheduling']=True (cron_json not needed)."""
    from personal_assistant.config.local_store import AgentWorkspaceConfig

    agent = AgentWorkspaceConfig(
        agent_id="test-agent",
        workspace_root=tmp_path,
        features={"cron_scheduling": True},
    )
    assert agent.cron_enabled is True


def test_sync_heartbeat_enable_via_features(tmp_path) -> None:
    """heartbeat_enabled=True when features['heartbeat']=True."""
    from personal_assistant.config.local_store import AgentWorkspaceConfig

    agent = AgentWorkspaceConfig(
        agent_id="test-agent",
        workspace_root=tmp_path,
        features={"heartbeat": True},
    )
    assert agent.heartbeat_enabled is True


def test_heartbeat_cadence_parsed_from_heartbeat_json_payload() -> None:
    """_parse_heartbeat_from_im_payload returns cadence 4-tuple (no enabled)."""
    import importlib

    main_mod = importlib.import_module("personal_assistant.main")
    raw = {
        "enabled": False,
        "every": "15m",
        "active_hours": {"start": "09:00", "end": "17:00", "timezone": "UTC"},
    }
    every, start, end, tz = main_mod._parse_heartbeat_from_im_payload(raw)
    assert every == "15m"
    assert start == "09:00"
    assert end == "17:00"
    assert tz == "UTC"
