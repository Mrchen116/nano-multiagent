"""SendMessageTool gateway dispatch and IMConnectionManager token auth tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_runtime_capabilities,
)
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager


class _FakeWebSocket:
    def __init__(self, incoming: list[str] | None = None) -> None:
        self.incoming = list(incoming or [])
        self.sent: list[str] = []
        self.closed = 0

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if not self.incoming:
            raise RuntimeError("socket closed")
        return self.incoming.pop(0)

    async def close(self) -> None:
        self.closed += 1


def _minimal_reporter(tmp_path: Path) -> UpstreamReporter:
    workspace = tmp_path / "agent-a"
    workspace.mkdir(exist_ok=True)
    agents = (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),)
    return UpstreamReporter(
        node=NodeConfig(node_id="n1"),
        agents=agents,
        send_frame=lambda _mt, _p: None,
        capabilities=build_runtime_capabilities(),
    )


async def _connect_fake(
    socket: _FakeWebSocket,
    connect_calls: list[tuple[str, dict[str, str]]],
    url: str,
    headers: dict[str, str],
) -> _FakeWebSocket:
    connect_calls.append((url, headers))
    return socket


def test_send_message_tool_dispatches_via_gateway_boundary() -> None:
    """SendMessageTool dispatches to gateway_dispatch_url from session_metadata (stateless HTTP)."""
    from unittest.mock import patch
    import httpx as _httpx

    from agent.products.personal_assistant.tools.send_message import SendMessageTool
    from agent.core.tools.base import (
        ToolContext,
        set_tool_safety_config_factory,
        set_tool_safety_factory,
    )

    seen_payloads: list[dict] = []

    def _mock_post(url: str, **kwargs) -> _httpx.Response:
        seen_payloads.append(kwargs.get("json", {}))
        return _httpx.Response(
            200, json={"ok": True}, request=_httpx.Request("POST", url)
        )

    tool = SendMessageTool()

    class _Safety:
        def __init__(self, *, repo_root, config) -> None:  # noqa: ANN001
            self.repo_root = repo_root
            self.config = config

    class _SafetyConfig:
        pass

    set_tool_safety_factory(_Safety)
    set_tool_safety_config_factory(_SafetyConfig)
    ctx = ToolContext.create(repo_root=Path("/tmp")).with_session(
        "sess-1",
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch"
        },
    )

    with patch("httpx.post", side_effect=_mock_post):
        result = tool.run({"text": "hello", "to": "agent-b"}, ctx)

    assert result["ok"] is True
    assert result["target"] == "agent-b"
    assert result["text"] == "hello"
    assert seen_payloads[0]["text"] == "hello"
    assert seen_payloads[0]["to"] == "agent-b"
    assert seen_payloads[0]["origin_kernel_session_id"] == "sess-1"
    assert seen_payloads[0]["source_agent_id"] is None
    assert isinstance(seen_payloads[0]["dispatch_request_id"], str)
    assert (
        seen_payloads[0]["from_session_id"]
        == f"sess-1|tool_call:{seen_payloads[0]['dispatch_request_id']}"
    )


def test_connect_once_calls_token_getter_and_uses_returned_token(
    tmp_path: Path,
) -> None:
    """token_getter 返回值应被写入 Authorization 请求头，而非使用 config.token。"""
    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
        ]
    )

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


def test_connect_once_falls_back_to_config_token_when_no_token_getter(
    tmp_path: Path,
) -> None:
    """token_getter 未提供时使用 config.token（向后兼容）。"""
    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
        ]
    )

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000", token="config-token"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, connect_calls, url, headers),
    )

    asyncio.run(manager.connect_once())

    _url, headers = connect_calls[0]
    assert headers.get("Authorization") == "Bearer config-token"


def test_connect_once_skips_auth_header_when_token_getter_returns_none(
    tmp_path: Path,
) -> None:
    """token_getter 返回 None 时不发送 Authorization 头（config.token 也为 None）。"""
    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
        ]
    )

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
