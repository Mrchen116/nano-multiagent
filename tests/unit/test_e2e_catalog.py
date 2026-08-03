"""Critical-path e2e model-selection tests."""

from __future__ import annotations

import pytest

from scripts.e2e_catalog import select_e2e_model


def _config() -> dict[str, object]:
    return {
        "llm": {
            "default_model": "deepseek:deepseek-v4-flash",
            "providers": [
                {
                    "name": "anthropic",
                    "models": [
                        {"name": "deepseek:deepseek-v4-flash"},
                        {"name": "kimiCoding:kimi-for-coding"},
                    ],
                }
            ],
        },
        "agents": [
            {"agent_id": "preset-default", "default_model": None},
            {"agent_id": "preset-override", "default_model": "old:model"},
        ],
    }


def test_select_e2e_model_keeps_the_copied_config_default() -> None:
    """Without an override, critical paths use the configured default route."""
    config = _config()

    selected = select_e2e_model(config)

    assert selected == "deepseek:deepseek-v4-flash"
    assert config["llm"]["default_model"] == selected  # type: ignore[index]
    assert [agent["default_model"] for agent in config["agents"]] == [  # type: ignore[index]
        selected,
        selected,
    ]


def test_select_e2e_model_applies_a_registered_override() -> None:
    """An override changes the isolated config without inventing a catalog entry."""
    config = _config()

    selected = select_e2e_model(config, model="kimiCoding:kimi-for-coding")

    assert selected == "kimiCoding:kimi-for-coding"
    assert config["llm"]["default_model"] == selected  # type: ignore[index]
    assert [agent["default_model"] for agent in config["agents"]] == [  # type: ignore[index]
        selected,
        selected,
    ]
    models = config["llm"]["providers"][0]["models"]  # type: ignore[index]
    assert models == [
        {"name": "deepseek:deepseek-v4-flash"},
        {"name": "kimiCoding:kimi-for-coding"},
    ]


def test_select_e2e_model_rejects_an_unregistered_override() -> None:
    """A typo cannot silently route a real e2e run to an unrelated default."""
    with pytest.raises(ValueError, match="not registered"):
        select_e2e_model(_config(), model="missing:model")
