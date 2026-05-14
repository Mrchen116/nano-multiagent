from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.compaction.types import CompactionReason, CompactionResult
from agent.platform.http_api.app import create_app
from agent.platform.tools.base import ToolContext
from agent.platform.tools.registry import ToolRegistry


class _RuntimeWithCompact:
    def __init__(self) -> None:
        self.compact_calls: list[str] = []

    async def compact(self, session_id: str, *, workspace_root=None) -> CompactionResult:
        del workspace_root  # stateless-kernel signature; this stub ignores it
        self.compact_calls.append(session_id)
        return CompactionResult(
            reason=CompactionReason.MANUAL,
            entry_id="entry_manual",
            first_kept_event_id="evt_2",
            summary="manual compacted",
            dropped_event_ids=("evt_1",),
            kept_event_ids=("evt_2",),
        )


class _EchoTool:
    name = "echo"
    description = "Echo text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):  # noqa: ANN001
        del ctx
        return {"echo": args["text"]}


def test_app_wires_session_service() -> None:
    app = create_app()

    from pathlib import Path
    session = app.state.session_service.create_session(workspace_root=Path.cwd())

    assert session.session_id.startswith('sess_')
    assert session.status == 'active'


def test_session_routes_wire_tools_registry_and_manual_compact() -> None:
    runtime = _RuntimeWithCompact()
    registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    registry.register(_EchoTool())
    app = create_app(runtime=runtime, tool_registry=registry)
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token", "X-Request-Id": "req-session-flow-compact-tools"}

    created = client.post(
        "/v1/sessions",
        json={"workspace_root": "~/nano-assistant/workspace/session-flow-tools"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    tools_response = client.get(f"/v1/sessions/{session_id}/tools", headers=headers)
    assert tools_response.status_code == 200
    tools_payload = tools_response.json()
    assert tools_payload["session_id"] == session_id
    tool_names = {item["name"] for item in tools_payload["tools"]}
    assert "echo" in tool_names

    compact_response = client.post(f"/v1/sessions/{session_id}:compact", json={}, headers=headers)
    assert compact_response.status_code == 200
    compact_payload = compact_response.json()
    assert compact_payload["session_id"] == session_id
    assert compact_payload["compacted"] is True
    assert compact_payload["result"]["reason"] == "manual"
    assert runtime.compact_calls == [session_id]


def test_append_message_persists_history_once_per_idempotency_key() -> None:
    app = create_app()
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token", "X-Request-Id": "req-append-history-integration"}

    created = client.post(
        "/v1/sessions",
        json={"workspace_root": "~/nano-assistant/workspace/append-history"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    payload = {
        "role": "assistant",
        "content": "给你个冷笑话：为什么海盗数学不好？",
        "message_id": "msg_dm_joke",
        "turn_id": "turn_dm_joke",
        "metadata": {"source": "gateway", "conversation_id": "conv-direct-1"},
        "idempotency_key": "dispatch-sync-1",
    }
    first = client.post(f"/v1/sessions/{session_id}/messages:append", json=payload, headers=headers)
    second = client.post(f"/v1/sessions/{session_id}/messages:append", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["entry_id"] == second.json()["entry_id"]

    messages = app.state.session_service.manager.list_turn_messages(session_id)
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert messages[0].content == "给你个冷笑话：为什么海盗数学不好？"
    assert messages[0].metadata["source"] == "gateway"
    assert messages[0].metadata["idempotency_key"] == "dispatch-sync-1"


def test_http_workspace_root_threaded_to_session_jsonl_location(tmp_path: Path) -> None:
    """HTTP create + append with workspace_root must land JSONL under that workspace.

    bugfix-348 Option C: the kernel is stateless; the workspace_root carried on
    each request is what locates the session JSONL. This proves the field is
    actually threaded HTTP -> service -> store -> filesystem, not dropped.
    """
    workspace_root = tmp_path / "agent-workspace"
    workspace_root.mkdir()

    # Production-shape app: workspace-aware store (data_dir=None), no cwd fallback.
    from agent.core.session.jsonl_store import JsonlSessionStore

    app = create_app(session_store=JsonlSessionStore(data_dir=None))
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token", "X-Request-Id": "req-ws-thread"}

    created = client.post(
        "/v1/sessions",
        json={"workspace_root": str(workspace_root)},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    # The session_created line must land under the request's workspace_root,
    # NOT under the process cwd (the bugfix-348 bug).
    expected = workspace_root / ".nano" / "sessions" / f"{session_id}.jsonl"
    assert expected.exists(), f"session JSONL must be at {expected}"

    # append with workspace_root must hit the same file.
    append = client.post(
        f"/v1/sessions/{session_id}/messages:append",
        json={
            "role": "user",
            "content": "ping",
            "workspace_root": str(workspace_root),
        },
        headers=headers,
    )
    assert append.status_code == 200

    # get_session with workspace_root query param resolves the same session.
    fetched = client.get(
        f"/v1/sessions/{session_id}",
        params={"workspace_root": str(workspace_root)},
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == session_id

    # Without workspace_root, the stateless store cannot locate the session.
    missing = client.get(f"/v1/sessions/{session_id}", headers=headers)
    assert missing.status_code == 404
