"""AgentWorkspaceConfig: heartbeat_enabled/cron_enabled are @property, not fields.

After feat-394 M9, enable state lives in the features dict; the gateway's YAML
parser and the IM sync path both write into features (not direct fields).
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# @property API contract: must not be constructor params; must derive from features
# ---------------------------------------------------------------------------


class TestAgentWorkspaceConfigProperties:
    """heartbeat_enabled and cron_enabled must be @property derived from features dict."""

    def test_heartbeat_enabled_is_not_constructor_param(self, tmp_path: Path) -> None:
        """AgentWorkspaceConfig must NOT accept heartbeat_enabled as a constructor param."""
        import inspect
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        sig = inspect.signature(AgentWorkspaceConfig)
        assert "heartbeat_enabled" not in sig.parameters, (
            "AgentWorkspaceConfig must not accept heartbeat_enabled as a constructor "
            "param after M9; use features={'heartbeat': True} instead"
        )

    def test_cron_enabled_is_not_constructor_param(self, tmp_path: Path) -> None:
        """AgentWorkspaceConfig must NOT accept cron_enabled as a constructor param."""
        import inspect
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        sig = inspect.signature(AgentWorkspaceConfig)
        assert "cron_enabled" not in sig.parameters, (
            "AgentWorkspaceConfig must not accept cron_enabled as a constructor "
            "param after M9; use features={'cron_scheduling': True} instead"
        )

    def test_sync_no_heartbeat_cron_field_in_dataclass(self, tmp_path: Path) -> None:
        """AgentWorkspaceConfig dataclass must not have heartbeat_enabled/cron_enabled fields."""
        import dataclasses
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        field_names = {f.name for f in dataclasses.fields(AgentWorkspaceConfig)}
        assert "heartbeat_enabled" not in field_names, (
            "heartbeat_enabled must be @property, not a dataclass field, after M9"
        )
        assert "cron_enabled" not in field_names, (
            "cron_enabled must be @property, not a dataclass field, after M9"
        )


# ---------------------------------------------------------------------------
# local_store YAML parser: heartbeat.enabled / cron.enabled → features dict
# ---------------------------------------------------------------------------


class TestLocalStoreParserFeaturesMapping:
    """_parse_agents must map YAML heartbeat.enabled / cron.enabled into features dict."""

    def _parse_agents_from_list(self, agents_list: list, tmp_path: Path) -> tuple:
        """Call _parse_agents directly to test YAML → AgentWorkspaceConfig mapping."""
        from personal_assistant.config.local_store import (  # noqa: PLC2701
            _parse_agents,
            _parse_llm,
        )

        ws = tmp_path / "ws"
        ws.mkdir(exist_ok=True)
        for item in agents_list:
            if "workspace_root" in item:
                item["workspace_root"] = str(ws)

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

        assert agent.features.get("heartbeat") is True
        assert agent.heartbeat_enabled is True

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

        assert agent.features.get("cron_scheduling") is True
        assert agent.cron_enabled is True

    def test_heartbeat_disabled_by_default(self, tmp_path: Path) -> None:
        """When YAML has no heartbeat block, heartbeat_enabled must be False."""
        agents = self._parse_agents_from_list(
            [{"agent_id": "test-agent", "workspace_root": "placeholder"}],
            tmp_path,
        )
        assert agents[0].heartbeat_enabled is False

    def test_cron_disabled_by_default(self, tmp_path: Path) -> None:
        """When YAML has no cron block, cron_enabled must be False."""
        agents = self._parse_agents_from_list(
            [{"agent_id": "test-agent", "workspace_root": "placeholder"}],
            tmp_path,
        )
        assert agents[0].cron_enabled is False
