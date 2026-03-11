from pathlib import Path

import pytest

from personal_assistant.config.local_store import load_local_config


def test_load_local_config_defaults_workspace_root_to_user_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
            ]
        ),
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    expected_root = home_dir / "nano-assistant" / "workspace" / "assistant-a"
    assert config.agents[0].workspace_root == expected_root.resolve()
    assert expected_root.is_dir() is True


def test_load_local_config_keeps_explicit_workspace_root_requirement(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    explicit_root = tmp_path / "agents" / "assistant-a"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {explicit_root}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="workspace_root does not exist"):
        load_local_config(config_path)


def test_load_local_config_reads_yaml_and_applies_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
                "channels:",
                "  - name: web_relay",
            ]
        ),
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.node.node_id == "node-local"
    assert config.kernel.base_url == "http://127.0.0.1:8000"
    assert config.kernel.health_path == "/v1/health"
    assert config.kernel.startup_timeout_seconds == 15.0
    assert config.agents[0].workspace_root == workspace_root
    assert config.channels[0].enabled is True
    assert config.im_service is None


def test_load_local_config_rejects_missing_agents(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents: []",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="agents must contain at least one entry"):
        load_local_config(config_path)


def test_load_local_config_rejects_missing_workspace_root(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    missing_root = tmp_path / "agents" / "missing"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {missing_root}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="workspace_root does not exist"):
        load_local_config(config_path)
