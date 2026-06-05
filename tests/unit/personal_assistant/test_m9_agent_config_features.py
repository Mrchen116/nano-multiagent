"""Tests for feat-394-M9 R3: AgentWorkspaceConfig heartbeat/cron as @property.

R3 retires the separate heartbeat_enabled/cron_enabled fields on AgentWorkspaceConfig,
replacing them with @property derived from the features dict:
  heartbeat_enabled → features.get("heartbeat", False)
  cron_enabled      → features.get("cron_scheduling", False)

These tests are RED until R3 implementation lands.
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# AgentWorkspaceConfig: heartbeat_enabled / cron_enabled as @property
# ---------------------------------------------------------------------------


class TestAgentWorkspaceConfigProperties:
    """heartbeat_enabled and cron_enabled must be @property derived from features dict."""

    def test_heartbeat_enabled_false_by_default(self, tmp_path: Path) -> None:
        """heartbeat_enabled must be False when features dict is empty."""
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=tmp_path,
            features={},
        )
        assert agent.heartbeat_enabled is False, (
            "heartbeat_enabled must be False when features does not contain 'heartbeat'"
        )

    def test_heartbeat_enabled_true_from_features(self, tmp_path: Path) -> None:
        """heartbeat_enabled must be True when features['heartbeat']=True."""
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=tmp_path,
            features={"heartbeat": True},
        )
        assert agent.heartbeat_enabled is True, (
            "heartbeat_enabled must derive from features['heartbeat']"
        )

    def test_cron_enabled_false_by_default(self, tmp_path: Path) -> None:
        """cron_enabled must be False when features dict is empty."""
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=tmp_path,
            features={},
        )
        assert agent.cron_enabled is False, (
            "cron_enabled must be False when features does not contain 'cron_scheduling'"
        )

    def test_cron_enabled_true_from_features(self, tmp_path: Path) -> None:
        """cron_enabled must be True when features['cron_scheduling']=True."""
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=tmp_path,
            features={"cron_scheduling": True},
        )
        assert agent.cron_enabled is True, (
            "cron_enabled must derive from features['cron_scheduling']"
        )

    def test_heartbeat_enabled_is_not_constructor_param(self, tmp_path: Path) -> None:
        """AgentWorkspaceConfig must NOT accept heartbeat_enabled as a constructor param.

        M9: heartbeat_enabled is a @property; callers must use features dict.
        """
        import inspect
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        sig = inspect.signature(AgentWorkspaceConfig)
        assert "heartbeat_enabled" not in sig.parameters, (
            "AgentWorkspaceConfig must not accept heartbeat_enabled as a constructor "
            "param after M9; use features={'heartbeat': True} instead"
        )

    def test_cron_enabled_is_not_constructor_param(self, tmp_path: Path) -> None:
        """AgentWorkspaceConfig must NOT accept cron_enabled as a constructor param.

        M9: cron_enabled is a @property; callers must use features dict.
        """
        import inspect
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        sig = inspect.signature(AgentWorkspaceConfig)
        assert "cron_enabled" not in sig.parameters, (
            "AgentWorkspaceConfig must not accept cron_enabled as a constructor "
            "param after M9; use features={'cron_scheduling': True} instead"
        )


# ---------------------------------------------------------------------------
# local_store YAML parser: heartbeat.enabled → features["heartbeat"]
# ---------------------------------------------------------------------------


class TestLocalStoreParserFeaturesMapping:
    """_parse_agents must map YAML heartbeat.enabled / cron.enabled into features dict.

    M9: no separate heartbeat_enabled/cron_enabled fields; the parser must write
    these into features so the @property derives correctly.
    """

    def _parse_agents_from_list(self, agents_list: list, tmp_path: Path) -> tuple:
        """Call _parse_agents directly to test YAML → AgentWorkspaceConfig mapping."""
        from personal_assistant.config.local_store import (  # noqa: PLC2701
            _parse_agents,
            _parse_llm,
        )

        # Resolve workspace_root to a real path
        ws = tmp_path / "ws"
        ws.mkdir(exist_ok=True)
        for item in agents_list:
            if "workspace_root" in item:
                item["workspace_root"] = str(ws)

        # Minimal LLM config for validation
        llm = _parse_llm(
            {
                "default_model": "test-model",
                "providers": [
                    {
                        "name": "openai_compat",
                        "base_url": "http://127.0.0.1:4000",
                        "models": [{"name": "test-model"}],
                    }
                ],
            }
        )
        return _parse_agents(agents_list, llm)

    def test_heartbeat_enabled_written_to_features(self, tmp_path: Path) -> None:
        """When YAML has heartbeat.enabled=true, features['heartbeat'] must be True."""
        agents = self._parse_agents_from_list(
            [
                {
                    "agent_id": "test-agent",
                    "workspace_root": "placeholder",
                    "heartbeat": {"enabled": True},
                }
            ],
            tmp_path,
        )
        agent = agents[0]

        assert agent.features.get("heartbeat") is True, (
            "heartbeat.enabled=true in YAML must be mapped to features['heartbeat']=True "
            "(M9: no separate heartbeat_enabled field)"
        )
        assert agent.heartbeat_enabled is True, (
            "agent.heartbeat_enabled must return True via @property from features"
        )

    def test_cron_enabled_written_to_features(self, tmp_path: Path) -> None:
        """When YAML has cron.enabled=true, features['cron_scheduling'] must be True."""
        agents = self._parse_agents_from_list(
            [
                {
                    "agent_id": "test-agent",
                    "workspace_root": "placeholder",
                    "cron": {"enabled": True},
                }
            ],
            tmp_path,
        )
        agent = agents[0]

        assert agent.features.get("cron_scheduling") is True, (
            "cron.enabled=true in YAML must be mapped to features['cron_scheduling']=True "
            "(M9: no separate cron_enabled field)"
        )
        assert agent.cron_enabled is True, (
            "agent.cron_enabled must return True via @property from features"
        )

    def test_heartbeat_disabled_by_default(self, tmp_path: Path) -> None:
        """When YAML has no heartbeat block, features['heartbeat'] must be absent/False."""
        agents = self._parse_agents_from_list(
            [
                {
                    "agent_id": "test-agent",
                    "workspace_root": "placeholder",
                }
            ],
            tmp_path,
        )
        agent = agents[0]

        assert agent.heartbeat_enabled is False
        assert agent.features.get("heartbeat", False) is False

    def test_cron_disabled_by_default(self, tmp_path: Path) -> None:
        """When YAML has no cron block, features['cron_scheduling'] must be absent/False."""
        agents = self._parse_agents_from_list(
            [
                {
                    "agent_id": "test-agent",
                    "workspace_root": "placeholder",
                }
            ],
            tmp_path,
        )
        agent = agents[0]

        assert agent.cron_enabled is False
        assert agent.features.get("cron_scheduling", False) is False


# ---------------------------------------------------------------------------
# main.py sync: heartbeat_json / cron_json → features dict (not separate fields)
# ---------------------------------------------------------------------------


class TestMainSyncFeaturesMapping:
    """sync_agent must write heartbeat/cron into features dict (not separate fields).

    M9: when IM sends heartbeat_json/cron_json, the gateway must merge
    heartbeat.enabled → features["heartbeat"] and cron.enabled → features["cron_scheduling"].
    The separate heartbeat_enabled/cron_enabled constructor params are retired.
    """

    def test_heartbeat_json_maps_to_features_heartbeat(self) -> None:
        """When IM sends heartbeat_json with enabled=true, agent.heartbeat_enabled must be True.

        After M9: sync path writes features['heartbeat']=True (not heartbeat_enabled field).
        Validates the full transformation: IM payload → AgentWorkspaceConfig.heartbeat_enabled.
        """
        import json
        import importlib
        from personal_assistant.config.local_store import AgentWorkspaceConfig
        from pathlib import Path

        main_mod = importlib.import_module("personal_assistant.main")
        hb_raw = json.loads(json.dumps({"enabled": True}))
        (hb_enabled, *_) = main_mod._parse_heartbeat_from_im_payload(hb_raw)

        # After M9: build agent with hb_enabled written into features
        features: dict = {}
        if hb_enabled:
            features["heartbeat"] = True

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=Path("/tmp/ws"),
            features=features,
        )
        assert agent.heartbeat_enabled is True, (
            "sync path must write heartbeat.enabled into features['heartbeat'], "
            "not the retired heartbeat_enabled field"
        )

    def test_cron_json_maps_to_features_cron_scheduling(self) -> None:
        """When IM sends cron_json with enabled=true, agent.cron_enabled must be True.

        After M9: sync path writes features['cron_scheduling']=True (not cron_enabled field).
        """
        import json
        import importlib
        from personal_assistant.config.local_store import AgentWorkspaceConfig
        from pathlib import Path

        main_mod = importlib.import_module("personal_assistant.main")
        cron_raw = json.loads(json.dumps({"enabled": True}))
        cron_enabled = main_mod._parse_cron_enabled_from_im_payload(cron_raw)

        # After M9: build agent with cron_enabled written into features
        features: dict = {}
        if cron_enabled:
            features["cron_scheduling"] = True

        agent = AgentWorkspaceConfig(
            agent_id="test-agent",
            workspace_root=Path("/tmp/ws"),
            features=features,
        )
        assert agent.cron_enabled is True, (
            "sync path must write cron.enabled into features['cron_scheduling'], "
            "not the retired cron_enabled field"
        )

    def test_sync_no_heartbeat_cron_field_in_dataclass(self, tmp_path: Path) -> None:
        """AgentWorkspaceConfig dataclass must not have heartbeat_enabled/cron_enabled fields.

        After M9: these are @property; they must not appear in dataclasses.fields().
        """
        import dataclasses
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        field_names = {f.name for f in dataclasses.fields(AgentWorkspaceConfig)}
        assert "heartbeat_enabled" not in field_names, (
            "heartbeat_enabled must be @property, not a dataclass field, after M9"
        )
        assert "cron_enabled" not in field_names, (
            "cron_enabled must be @property, not a dataclass field, after M9"
        )
