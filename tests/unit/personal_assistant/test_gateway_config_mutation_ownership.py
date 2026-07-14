"""Regression tests for narrow Gateway config mutation ownership."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    IMServiceConfig,
    load_local_config,
    save_local_config,
)
from personal_assistant.main import (
    _IMConfigSyncClient,
    _build_feishu_owner_open_id_binder,
    _make_token_getter,
)

from ._main_helpers import make_minimal_config


class _RefreshingAuthClient:
    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        assert refresh_token == "refresh-old"
        return "access-new", "refresh-new"

    async def login(self, *, username: str, password: str) -> tuple[str, str]:
        raise AssertionError("refresh should succeed")


@pytest.mark.asyncio
async def test_token_refresh_preserves_agent_added_after_getter_creation(
    tmp_path: Path,
) -> None:
    base = make_minimal_config(tmp_path)
    config = replace(
        base,
        gateway=replace(base.gateway, poll_interval_seconds=0.01),
        im_service=IMServiceConfig(
            url="http://im.local",
            token="access-old",
            refresh_token="refresh-old",
        ),
    )
    save_local_config(config, config.source_path)
    stale = load_local_config(config.source_path)
    token_getter = _make_token_getter(
        im_service=stale.im_service,
        local_config=stale,
        auth_client=_RefreshingAuthClient(),
    )
    (tmp_path / "agent-b").mkdir()
    latest = replace(
        stale,
        agents=(
            *stale.agents,
            AgentWorkspaceConfig(
                agent_id="agent-b",
                workspace_root=tmp_path / "agent-b",
            ),
        ),
    )
    save_local_config(latest, latest.source_path)

    assert await token_getter() == "access-new"

    persisted = load_local_config(config.source_path)
    assert [agent.agent_id for agent in persisted.agents] == ["agent-a", "agent-b"]
    assert persisted.im_service is not None
    assert persisted.im_service.token == "access-new"
    assert persisted.im_service.refresh_token == "refresh-new"


def test_agent_sync_preserves_token_refreshed_after_client_creation(
    tmp_path: Path,
) -> None:
    base = make_minimal_config(tmp_path)
    config = replace(
        base,
        gateway=replace(base.gateway, poll_interval_seconds=0.01),
        im_service=IMServiceConfig(
            url="http://im.local",
            token="access-old",
            refresh_token="refresh-old",
        ),
    )
    save_local_config(config, config.source_path)
    stale = load_local_config(config.source_path)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token="access-old",
        pipeline=object(),  # type: ignore[arg-type]
        local_config=stale,
    )
    latest = replace(
        stale,
        im_service=replace(
            stale.im_service,
            token="access-new",
            refresh_token="refresh-new",
        ),
    )
    save_local_config(latest, latest.source_path)

    (tmp_path / "agent-b").mkdir()
    sync._persist_agent_config(  # noqa: SLF001
        AgentWorkspaceConfig(
            agent_id="agent-b",
            workspace_root=tmp_path / "agent-b",
        )
    )

    persisted = load_local_config(config.source_path)
    assert [agent.agent_id for agent in persisted.agents] == ["agent-a", "agent-b"]
    assert persisted.im_service is not None
    assert persisted.im_service.token == "access-new"
    assert persisted.im_service.refresh_token == "refresh-new"


def test_feishu_owner_bind_preserves_token_refreshed_after_binder_creation(
    tmp_path: Path,
) -> None:
    base = make_minimal_config(tmp_path)
    config = replace(
        base,
        gateway=replace(base.gateway, poll_interval_seconds=0.01),
        channels=(
            ChannelConfig(
                name="feishu:agent-a",
                enabled=True,
                settings={"appId": "cli_test", "appSecret": "secret"},
            ),
        ),
        im_service=IMServiceConfig(
            url="http://im.local",
            token="access-old",
            refresh_token="refresh-old",
        ),
    )
    save_local_config(config, config.source_path)
    stale = load_local_config(config.source_path)
    binder = _build_feishu_owner_open_id_binder(stale)
    latest = replace(
        stale,
        im_service=replace(
            stale.im_service,
            token="access-new",
            refresh_token="refresh-new",
        ),
    )
    save_local_config(latest, latest.source_path)

    assert binder("feishu:agent-a", "ou_first") == "ou_first"

    persisted = load_local_config(config.source_path)
    assert persisted.im_service is not None
    assert persisted.im_service.token == "access-new"
    assert persisted.im_service.refresh_token == "refresh-new"
    assert persisted.channels[0].settings["ownerOpenId"] == "ou_first"
