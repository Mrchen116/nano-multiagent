"""Regression coverage for legacy Gateway YAML prompt migration."""

from pathlib import Path

import pytest
import yaml

from personal_assistant.config.local_store import load_local_config, save_local_config


@pytest.mark.parametrize(
    ("legacy", "custom", "expected"),
    [
        ("   ", "Current custom", "Current custom"),
        ("Legacy role", "", "Legacy role"),
        (" Legacy role ", "Legacy role", "Legacy role"),
        ("Legacy role", "Current custom", "Legacy role\n\nCurrent custom"),
    ],
)
def test_legacy_system_prompt_migrates_to_one_canonical_custom_prompt(
    tmp_path: Path,
    legacy: str,
    custom: str,
    expected: str,
) -> None:
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
                        "system_prompt": legacy,
                        "custom_prompt": custom,
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
    agent = config.agents[0]
    assert agent.custom_prompt == expected
    assert not hasattr(agent, "system_prompt")

    save_local_config(config, config_path)
    saved_agent = yaml.safe_load(config_path.read_text(encoding="utf-8"))["agents"][0]
    assert saved_agent["custom_prompt"] == expected
    assert "system_prompt" not in saved_agent

    reloaded = load_local_config(config_path)
    assert reloaded.agents[0].custom_prompt == expected
