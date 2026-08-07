"""Local Gateway workspace provenance persistence behavior."""

from pathlib import Path

import yaml

from personal_assistant.config.local_store import load_local_config, save_local_config


def test_legacy_agent_workspace_source_is_inferred_and_persisted(
    tmp_path: Path,
) -> None:
    """Infer omitted roots as default and explicit roots as custom for legacy YAML."""
    custom = tmp_path / "custom"
    custom.mkdir()
    payload = {
        "node": {"node_id": "node-a"},
        "agents": [
            {"agent_id": "default-agent"},
            {"agent_id": "custom-agent", "workspace_root": str(custom)},
        ],
        "llm": {
            "default_model": "test-model",
            "providers": [
                {
                    "name": "test",
                    "base_url": "http://127.0.0.1:4000",
                    "models": [{"name": "test-model"}],
                }
            ],
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    loaded = load_local_config(config_path)

    sources = {item.agent_id: item.workspace_is_default for item in loaded.agents}
    assert sources == {"default-agent": True, "custom-agent": False}
    save_local_config(loaded, config_path)
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert {
        item["agent_id"]: item["workspace_is_default"] for item in saved["agents"]
    } == sources
