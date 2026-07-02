"""Tests for Gateway Feishu ownerOpenId startup inference."""

from __future__ import annotations

from pathlib import Path
import subprocess

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
from personal_assistant.main import _autofill_feishu_owner_open_id


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


def test_autofill_feishu_owner_open_id_from_matching_lark_cli_auth(
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

    def _run(*_args, **_kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            args=["lark-cli"],
            returncode=0,
            stdout=(
                '{"appId":"cli_a","identities":'
                '{"user":{"openId":"ou_owner"},"bot":{"openId":"ou_bot"}}}'
            ),
            stderr="",
        )

    updated = _autofill_feishu_owner_open_id(
        config,
        save_config=lambda cfg, _path: saved.append(cfg),
        command_runner=_run,
    )

    assert updated.channels[0].settings["ownerOpenId"] == "ou_owner"
    assert saved == [updated]


def test_autofill_feishu_owner_open_id_without_source_path_keeps_memory_update(
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

    def _run(*_args, **_kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            args=["lark-cli"],
            returncode=0,
            stdout='{"appId":"cli_a","identities":{"user":{"openId":"ou_owner"}}}',
            stderr="",
        )

    updated = _autofill_feishu_owner_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("source_path is unavailable"),
        command_runner=_run,
    )

    assert updated.channels[0].settings["ownerOpenId"] == "ou_owner"


def test_autofill_feishu_owner_open_id_ignores_app_id_mismatch(
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

    def _run(*_args, **_kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            args=["lark-cli"],
            returncode=0,
            stdout='{"appId":"cli_other","identities":{"user":{"openId":"ou_owner"}}}',
            stderr="",
        )

    updated = _autofill_feishu_owner_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist mismatch"),
        command_runner=_run,
    )

    assert "ownerOpenId" not in updated.channels[0].settings


def test_autofill_feishu_owner_open_id_degrades_when_lark_cli_missing(
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

    def _run(*_args, **_kwargs):  # noqa: ANN001
        raise FileNotFoundError("lark-cli")

    updated = _autofill_feishu_owner_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist on failure"),
        command_runner=_run,
    )

    assert "ownerOpenId" not in updated.channels[0].settings


def test_autofill_feishu_owner_open_id_degrades_when_lark_cli_fails(
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

    def _run(*_args, **_kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            args=["lark-cli"],
            returncode=1,
            stdout="",
            stderr="not logged in",
        )

    updated = _autofill_feishu_owner_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist on failure"),
        command_runner=_run,
    )

    assert "ownerOpenId" not in updated.channels[0].settings


def test_autofill_feishu_owner_open_id_degrades_when_identity_shape_is_invalid(
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

    def _run(*_args, **_kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            args=["lark-cli"],
            returncode=0,
            stdout='{"appId":"cli_a","identities":[]}',
            stderr="",
        )

    updated = _autofill_feishu_owner_open_id(
        config,
        save_config=lambda _cfg, _path: pytest.fail("must not persist invalid shape"),
        command_runner=_run,
    )

    assert "ownerOpenId" not in updated.channels[0].settings
