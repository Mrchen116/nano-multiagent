"""Gateway lifecycle config parsing and persistence behavior."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from personal_assistant.config.local_store import (
    RuntimeConfigOwner,
    load_gateway_runtime_config,
    load_local_config,
    save_local_config,
)


def _write_config(tmp_path: Path, gateway_lines: list[str] | None = None) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "config.yaml"
    lines = [
        "node:",
        "  node_id: node-local",
        "agents:",
        "  - agent_id: assistant",
        f"    workspace_root: {workspace}",
    ]
    if gateway_lines is not None:
        lines.extend(["gateway:", *gateway_lines])
    lines.extend(
        [
            "llm:",
            "  default_model: test:model",
            "  providers:",
            "    - name: test",
            "      models:",
            "        - name: test:model",
        ]
    )
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def test_gateway_autostart_defaults_on_without_serializing_default(
    tmp_path: Path,
) -> None:
    config = load_local_config(_write_config(tmp_path))

    assert config.gateway.autostart is True
    assert config.gateway.environment == {}

    saved = tmp_path / "saved.yaml"
    save_local_config(config, saved)
    assert "gateway" not in yaml.safe_load(saved.read_text(encoding="utf-8"))


def test_gateway_autostart_and_environment_round_trip(tmp_path: Path) -> None:
    source = _write_config(
        tmp_path,
        [
            "  autostart: false",
            "  environment:",
            "    SEARXNG_URL: http://searxng.local:8888",
            '    EMPTY_VALUE: ""',
        ],
    )

    config = load_local_config(source)
    saved = tmp_path / "saved.yaml"
    save_local_config(config, saved)
    restored = load_local_config(saved)

    assert restored.gateway.autostart is False
    assert restored.gateway.environment == {
        "SEARXNG_URL": "http://searxng.local:8888",
        "EMPTY_VALUE": "",
    }


def test_runtime_config_owner_persist_preserves_gateway_fields(tmp_path: Path) -> None:
    source = _write_config(
        tmp_path,
        [
            "  autostart: false",
            "  environment:",
            "    SEARXNG_URL: http://searxng.local:8888",
        ],
    )
    owner = RuntimeConfigOwner(load_local_config(source))

    owner.persist(
        lambda config: replace(
            config, node=replace(config.node, node_id="updated-node")
        ),
        save_config=save_local_config,
    )

    restored = load_local_config(source)
    assert restored.node.node_id == "updated-node"
    assert restored.gateway.autostart is False
    assert restored.gateway.environment == {"SEARXNG_URL": "http://searxng.local:8888"}


def test_transient_im_url_is_not_written_by_later_runtime_config_save(
    tmp_path: Path,
) -> None:
    source = _write_config(tmp_path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    payload["im_service"] = {
        "url": "http://stable-im:8011",
        "token": "stable-token",
    }
    source.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    runtime_config = load_gateway_runtime_config(
        source,
        im_service_url_override="http://one-launch-im:8011",
    )
    owner = RuntimeConfigOwner(runtime_config)

    owner.persist(
        lambda config: replace(
            config, node=replace(config.node, node_id="updated-node")
        ),
        save_config=save_local_config,
    )

    restored = load_local_config(source)
    assert restored.node.node_id == "updated-node"
    assert restored.im_service is not None
    assert restored.im_service.url == "http://stable-im:8011"
    assert restored.im_service.token == "stable-token"


@pytest.mark.parametrize(
    ("gateway_lines", "message"),
    [
        (['  autostart: "yes"'], "gateway.autostart must be a boolean"),
        (["  environment: nope"], "gateway.environment must be a mapping"),
        (
            ["  environment:", "    SEARXNG_URL: 123"],
            "gateway.environment.SEARXNG_URL must be a string",
        ),
        (
            ["  environment:", '    "INVALID=KEY": value'],
            "gateway.environment keys cannot contain",
        ),
        (
            ["  environment:", '    VALID: "value\\0suffix"'],
            "gateway.environment.VALID cannot contain NUL",
        ),
    ],
)
def test_gateway_service_config_rejects_malformed_values(
    tmp_path: Path, gateway_lines: list[str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_local_config(_write_config(tmp_path, gateway_lines))
