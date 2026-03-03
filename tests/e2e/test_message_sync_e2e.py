from fastapi.testclient import TestClient

from nano_multiagent.agent.compaction.types import CompactionReason, CompactionResult
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.app import create_app


class RecordingRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.compact_calls: list[str] = []

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None) -> TurnResult:  # noqa: ANN001
        self.calls.append({"session_id": session_id, "parts": parts, "stream": stream})
        return TurnResult(
            session_id=session_id,
            turn_id="turn_e2e",
            messages=(Message(message_id="msg_e2e", role="assistant", content="pong"),),
            completed=True,
            stop_reason="completed",
        )

    def compact(self, session_id: str) -> CompactionResult:
        self.compact_calls.append(session_id)
        return CompactionResult(
            reason=CompactionReason.MANUAL,
            entry_id="entry_e2e_compact",
            first_kept_event_id="evt_kept_1",
            summary="manual compact e2e",
            dropped_event_ids=("evt_drop_1",),
            kept_event_ids=("evt_kept_1",),
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_create_session_then_sync_message_e2e() -> None:
    runtime = RecordingRuntime()
    client = TestClient(create_app(runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-e2e-message-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}], "stream": False},
        headers=_auth_headers("req-e2e-message"),
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-e2e-message"
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["turn_id"] == "turn_e2e"
    assert payload["message"]["content"] == "pong"

    assert len(runtime.calls) == 1
    assert runtime.calls[0]["session_id"] == session_id
    assert runtime.calls[0]["parts"] == [{"type": "text", "text": "ping"}]
    assert runtime.calls[0]["stream"] is False


def test_session_tools_and_manual_compact_e2e() -> None:
    runtime = RecordingRuntime()
    client = TestClient(create_app(runtime=runtime))
    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-e2e-session-tools-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    tools_response = client.get(
        f"/v1/sessions/{session_id}/tools",
        headers=_auth_headers("req-e2e-session-tools"),
    )
    assert tools_response.status_code == 200
    tools_payload = tools_response.json()
    assert tools_payload["session_id"] == session_id
    names = {item["name"] for item in tools_payload["tools"]}
    assert {"read", "write", "edit", "bash"}.issubset(names)

    compact_response = client.post(
        f"/v1/sessions/{session_id}:compact",
        json={},
        headers=_auth_headers("req-e2e-session-compact"),
    )
    assert compact_response.status_code == 200
    compact_payload = compact_response.json()
    assert compact_payload["session_id"] == session_id
    assert compact_payload["compacted"] is True
    assert compact_payload["result"]["reason"] == "manual"
    assert runtime.compact_calls == [session_id]
