"""Regression coverage for retiring the hidden Gateway YAML prompt key."""

from pathlib import Path

import yaml

from personal_assistant.config.local_store import load_local_config, save_local_config


def test_retired_yaml_prompt_key_is_not_loaded_or_saved(tmp_path: Path) -> None:
    """A stale key must not become Custom Instructions or a runtime input."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "gateway.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "node": {"node_id": "node-1"},
                "agents": [
                    {
                        "agent_id": "agent-a",
                        "workspace_root": str(workspace),
                        "system_prompt": "discard this hidden role",
                        "custom_prompt": "visible instruction",
                    }
                ],
                "llm": {
                    "default_model": "provider:model",
                    "providers": [
                        {
                            "name": "provider",
                            "base_url": "http://127.0.0.1:4000",
                            "models": [{"name": "provider:model"}],
                        }
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    config = load_local_config(config_path)
    assert config.agents[0].custom_prompt == "visible instruction"

    save_local_config(config, config_path)
    saved_agent = yaml.safe_load(config_path.read_text(encoding="utf-8"))["agents"][0]
    assert saved_agent["custom_prompt"] == "visible instruction"
    assert "system_prompt" not in saved_agent
