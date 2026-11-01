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


def test_bootstrap_tracks_product_default_tools_and_keeps_explicit_choices(tmp_path):
    """A newly catalogued default reaches every seeded agent without a YAML edit."""
    import json
    import httpx
    import yaml
    from scripts.e2e_catalog import sync_default_tools

    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({"agents": [{"agent_id": "p"}, {"agent_id": "q"}]}))
    saved = {}

    def respond(request):
        if request.url.path == "/im/v1/agents":
            return httpx.Response(200, json=[{"agent_id": "p"}, {"agent_id": "q"}])
        agent_id = request.url.path.split("/")[4]
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(
                200,
                json={
                    "tools": [
                        {"name": "read", "default_on": True},
                        {"name": "future-default", "default_on": True},
                        {"name": "explicit", "default_on": False},
                        {"name": "optional", "default_on": False},
                        {"name": "feature-tool", "default_on": False},
                    ],
                    "fixed_tools": ["inbox"],
                    "features": [
                        {"key": "active", "requires": {"tools": ["feature-tool"]}},
                        {"key": "off", "requires": {"tools": ["optional"]}},
                    ],
                },
            )
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "profile_version": 7,
                    "display_name": "Named test agent",
                    "group_reply_policy": "mention_only",
                    "custom_prompt": "Preserve this fixture's role.",
                    "default_model": "fixture:model",
                    "tool_allowlist": ["explicit", "retired"],
                    "features": {"active": True, "off": False},
                },
            )
        saved[agent_id] = json.loads(request.content)
        return httpx.Response(200, json=saved[agent_id])

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(respond)
    ) as client:
        sync_default_tools(client, path)
    assert set(saved) == {"p", "q"}
    for config in saved.values():
        assert set(config["tool_allowlist"]) == {
            "read",
            "future-default",
            "explicit",
            "feature-tool",
            "inbox",
        }
        assert config["profile_version"] == 7
        assert config["display_name"] == "Named test agent"
        assert config["group_reply_policy"] == "mention_only"
        assert config["custom_prompt"] == "Preserve this fixture's role."
        assert config["default_model"] == "fixture:model"
    assert yaml.safe_load(path.read_text()) == {
        "agents": [{"agent_id": "p"}, {"agent_id": "q"}]
    }


def test_explicit_config_is_not_replaced_by_product_defaults(tmp_path):
    """A scenario-specific allowlist remains an intentional restriction."""
    import httpx
    from scripts.e2e_catalog import sync_default_tools

    def unexpected(_request):
        pytest.fail("An explicit configuration must not be changed")

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(unexpected)
    ) as client:
        sync_default_tools(client, tmp_path / "not-read.yaml", explicit_config=True)
