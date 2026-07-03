"""Tests for Gateway Feishu botOpenId startup inference."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LLMConfigPayload,
    LLMModelPayload,
    LLMProviderPayload,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import (
    _autofill_feishu_bot_open_id,
    _build_feishu_owner_open_id_binder,
)


def _local_config(tmp_path: Path, channels: tuple[ChannelConfig, ...]) -> LocalConfig:
    return LocalConfig(
        node=NodeConfig(node_id="node-1", user_id="owner-im"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="plato",
                workspace_root=tmp_path / "workspace",
            ),
        ),
        channels=channels,
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://127.0.0.1:8011"),
        llm=LLMConfigPayload(
            default_model="test-model",
            providers=(
                LLMProviderPayload(
                    name="test",
                    base_url="http://127.0.0.1:4000",
                    models=(LLMModelPayload(name="test-model"),),
                ),
            ),
        ),
        source_path=tmp_path / "config.yaml",
    )


def test_autofill_feishu_bot_open_id_from_app_probe(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={"appId": "cli_a", "appSecret": "s_a"},
            ),
        ),
    )
    saved: list[LocalConfig] = []

    updated = _autofill_feishu_bot_open_id(
        config,
        save_config=lambda cfg, _path: saved.append(cfg),
        bot_identity_fetcher=lambda app_id, app_secret, domain: "ou_bot",
    )

    assert updated.channels[0].settings["botOpenId"] == "ou_bot"
    assert "ownerOpenId" not in updated.channels[0].settings
    assert saved == [updated]


def test_autofill_feishu_bot_open_id_preserves_owner_open_id(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "ownerOpenId": "ou_existing_owner",
                },
            ),
        ),
    )

    updated = _autofill_feishu_bot_open_id(
        config,
        save_config=lambda _cfg, _path: None,
        bot_identity_fetcher=lambda app_id, app_secret, domain: "ou_bot",
    )

    assert updated.channels[0].settings["ownerOpenId"] == "ou_existing_owner"
    assert updated.channels[0].settings["botOpenId"] == "ou_bot"


def test_feishu_owner_open_id_binder_persists_first_sender(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={"appId": "cli_a", "appSecret": "s_a"},
            ),
        ),
    )
    saved: list[LocalConfig] = []
    binder = _build_feishu_owner_open_id_binder(
        config,
        save_config=lambda cfg, _path: saved.append(cfg),
    )

    bound = binder("feishu:plato", "ou_first")

    assert bound == "ou_first"
    assert config.channels[0].settings["ownerOpenId"] == "ou_first"
    assert saved == [config]


def test_feishu_owner_open_id_binder_keeps_existing_owner(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "ownerOpenId": "ou_existing_owner",
                },
            ),
        ),
    )
    binder = _build_feishu_owner_open_id_binder(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist existing"),
    )

    bound = binder("feishu:plato", "ou_other")

    assert bound == "ou_existing_owner"
    assert config.channels[0].settings["ownerOpenId"] == "ou_existing_owner"


def test_autofill_feishu_bot_open_id_without_source_path_keeps_memory_update(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={"appId": "cli_a", "appSecret": "s_a"},
            ),
        ),
    )
    config = LocalConfig(
        node=config.node,
        agents=config.agents,
        channels=config.channels,
        kernel=config.kernel,
        heartbeat=config.heartbeat,
        im_service=config.im_service,
        llm=config.llm,
        source_path=None,  # type: ignore[arg-type]
    )

    updated = _autofill_feishu_bot_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("source_path is unavailable"),
        bot_identity_fetcher=lambda app_id, app_secret, domain: "ou_bot",
    )

    assert updated.channels[0].settings["botOpenId"] == "ou_bot"


def test_autofill_feishu_bot_open_id_uses_configured_domain(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "domain": "https://open.larksuite.com",
                },
            ),
        ),
    )
    seen: list[tuple[str, str, str]] = []

    def _fetch(app_id: str, app_secret: str, domain: str) -> str:
        seen.append((app_id, app_secret, domain))
        return "ou_bot"

    _autofill_feishu_bot_open_id(
        config,
        save_config=lambda _cfg, _path: None,
        bot_identity_fetcher=_fetch,
    )

    assert seen == [("cli_a", "s_a", "https://open.larksuite.com")]


def test_autofill_feishu_bot_open_id_degrades_when_probe_fails(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={"appId": "cli_a", "appSecret": "s_a"},
            ),
        ),
    )

    updated = _autofill_feishu_bot_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist on failure"),
        bot_identity_fetcher=lambda app_id, app_secret, domain: None,
    )

    assert "botOpenId" not in updated.channels[0].settings


def test_autofill_feishu_bot_open_id_skips_existing_bot_open_id(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "botOpenId": "ou_existing_bot",
                },
            ),
        ),
    )

    updated = _autofill_feishu_bot_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist existing"),
        bot_identity_fetcher=lambda app_id, app_secret, domain: pytest.fail(
            "probe must not run"
        ),
    )

    assert updated is config
    assert updated.channels[0].settings["botOpenId"] == "ou_existing_bot"


def test_autofill_feishu_bot_open_id_skips_missing_app_secret(
    tmp_path: Path,
) -> None:
    config = _local_config(
        tmp_path,
        (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={"appId": "cli_a"},
            ),
        ),
    )

    updated = _autofill_feishu_bot_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist"),
        bot_identity_fetcher=lambda app_id, app_secret, domain: pytest.fail(
            "probe must not run"
        ),
    )

    assert "botOpenId" not in updated.channels[0].settings
