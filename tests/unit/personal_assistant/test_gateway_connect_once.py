"""Unit tests for IMConnectionManager.connect_once token injection and ConfigSyncClient."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


def test_config_sync_client_records_latest_versions() -> None:
    seen: list[tuple[str, int]] = []
    client = ConfigSyncClient(fetcher=lambda agent_id, profile_version: seen.append((agent_id, profile_version)))

    request = client.handle_notification({"agent_id": "agent-a", "profile_version": 3})

    assert request.agent_id == "agent-a"
    assert client.latest_profile_version("agent-a") == 3
    assert seen == [("agent-a", 3)]


def test_connect_once_calls_token_getter_and_uses_returned_token(tmp_path: Path) -> None:
    """token_getter 返回值应被写入 Authorization 请求头，而非使用 config.token。"""
    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    socket = _FakeWebSocket(incoming=[
        json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
    ])

    async def _token_getter() -> str | None:
        return "dynamic-access-token"

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000", token="stale-token"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        token_getter=_token_getter,
        connect=lambda url, headers: _connect_fake(socket, connect_calls, url, headers),
    )

    asyncio.run(manager.connect_once())

    assert len(connect_calls) == 1
    _url, headers = connect_calls[0]
    # token_getter 优先于 config.token
    assert headers.get("Authorization") == "Bearer dynamic-access-token"


def test_connect_once_falls_back_to_config_token_when_no_token_getter(tmp_path: Path) -> None:
    """token_getter 未提供时使用 config.token（向后兼容）。"""
    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    socket = _FakeWebSocket(incoming=[
        json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
    ])

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000", token="config-token"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, connect_calls, url, headers),
    )

    asyncio.run(manager.connect_once())

    _url, headers = connect_calls[0]
    assert headers.get("Authorization") == "Bearer config-token"


def test_connect_once_skips_auth_header_when_token_getter_returns_none(tmp_path: Path) -> None:
    """token_getter 返回 None 时不发送 Authorization 头（config.token 也为 None）。"""
    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    socket = _FakeWebSocket(incoming=[
        json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
    ])

    async def _token_getter() -> str | None:
        return None

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000", token=None),
        reporter=reporter,
        relay_adapter=relay_adapter,
        token_getter=_token_getter,
        connect=lambda url, headers: _connect_fake(socket, connect_calls, url, headers),
    )

    asyncio.run(manager.connect_once())

    _url, headers = connect_calls[0]
    assert "Authorization" not in headers
