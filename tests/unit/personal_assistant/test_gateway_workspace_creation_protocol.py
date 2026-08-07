"""Gateway WebSocket protocol coverage for workspace creation drafts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


def _relay_adapter() -> WebRelayAdapter:
    adapter = WebRelayAdapter()
    adapter.start(lambda _message: None)
    return adapter


def test_agent_create_rejection_is_returned_as_structured_outcome(
    tmp_path: Path,
) -> None:
    """Return recoverable creation rejection without dropping the Gateway socket."""
    error = {
        "code": "workspace_confirmation_required",
        "detail": "Workspace target is an existing directory and requires confirmation.",
    }
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "agent.create",
                    "payload": {
                        "request_id": "create-1",
                        "agent": {
                            "agent_id": "draft-agent",
                            "workspace_root": "/srv/project",
                        },
                    },
                }
            ),
        ]
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=_relay_adapter(),
        sync_client=ConfigSyncClient(),
        agent_create_handler=lambda _payload: {"error": error},
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(_exercise())

    assert json.loads(socket.sent[-1]) == {
        "type": "agent.created",
        "payload": {
            "request_id": "create-1",
            "node_id": "n1",
            "agent": {},
            "error": error,
        },
    }


def test_node_preview_resolves_draft_workspace_on_gateway(
    tmp_path: Path,
) -> None:
    """Resolve the preview root on the selected node before calling the provider."""
    resolver_calls: list[tuple[str, str | None, str | None]] = []
    provider_roots: list[str] = []

    def _resolve(mode: str, agent_id: str | None, root: str | None) -> str:
        resolver_calls.append((mode, agent_id, root))
        return "/gateway/default/draft-agent"

    async def _preview(
        _agent_id: str,
        workspace_root: str,
        _features: dict[str, bool],
        _custom_prompt: str | None,
        _tool_ids: list[str],
        _scenario: str,
        _skill_ids: list[str],
    ) -> dict[str, object]:
        provider_roots.append(workspace_root)
        return {"prompt": "preview", "section_count": 1}

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "node.prompt.preview.request",
                    "payload": {
                        "request_id": "preview-1",
                        "workspace_mode": "default",
                        "agent_id_hint": "draft-agent",
                        "workspace_root": None,
                        "features": {},
                        "custom_prompt": None,
                        "tool_ids": [],
                        "skill_ids": [],
                        "scenario": "direct",
                    },
                }
            ),
        ]
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=_relay_adapter(),
        sync_client=ConfigSyncClient(),
        prompt_preview_provider=_preview,
        node_prompt_workspace_resolver=_resolve,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(_exercise())

    assert resolver_calls == [("default", "draft-agent", None)]
    assert provider_roots == ["/gateway/default/draft-agent"]
