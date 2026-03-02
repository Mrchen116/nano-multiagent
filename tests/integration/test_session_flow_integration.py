from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.compaction.types import CompactionReason, CompactionResult
from nano_multiagent.server.app import create_app
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.registry import ToolRegistry


class _RuntimeWithCompact:
    def __init__(self) -> None:
        self.compact_calls: list[str] = []

    def compact(self, session_id: str) -> CompactionResult:
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

    session = app.state.session_service.create_session()

    assert session.session_id.startswith('sess_')
    assert session.status == 'active'


def test_session_routes_wire_tools_registry_and_manual_compact() -> None:
    runtime = _RuntimeWithCompact()
    registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    registry.register(_EchoTool())
    app = create_app(runtime=runtime, tool_registry=registry, auth_token="test-token")
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token", "X-Request-Id": "req-session-flow-compact-tools"}

    created = client.post("/v1/sessions", json={}, headers=headers)
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
