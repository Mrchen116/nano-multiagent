from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.app import create_app


class StubRuntime:
    def run(self, session_id: str, parts, *, stream: bool = True) -> TurnResult:  # noqa: ANN001
        del parts
        del stream
        return TurnResult(
            session_id=session_id,
            turn_id="turn_contract",
            messages=(Message(message_id="msg_contract", role="assistant", content="contract-ok"),),
            completed=True,
            stop_reason="completed",
        )


class MissingSessionRuntime:
    def run(self, session_id: str, parts, *, stream: bool = True) -> TurnResult:  # noqa: ANN001
        del parts
        del stream
        raise ValueError(f"session does not exist: {session_id}")


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_sync_message_contract_returns_final_response() -> None:
    client = TestClient(create_app(runtime=StubRuntime()))
    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-message-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}], "stream": False},
        headers=_auth_headers("req-message-sync"),
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-message-sync"
    payload = response.json()
    assert set(payload.keys()) == {"session_id", "turn_id", "message", "completed", "stop_reason"}
    assert payload["session_id"] == session_id
    assert payload["turn_id"] == "turn_contract"
    assert payload["completed"] is True
    assert payload["stop_reason"] == "completed"
    assert set(payload["message"].keys()) == {"message_id", "role", "content"}
    assert payload["message"]["role"] == "assistant"
    assert payload["message"]["content"] == "contract-ok"


def test_sync_message_not_found_uses_unified_error_with_trace_id() -> None:
    client = TestClient(create_app(runtime=MissingSessionRuntime()))

    response = client.post(
        "/v1/sessions/sess_missing/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-message-missing"),
    )

    assert response.status_code == 404
    payload = response.json()
    assert set(payload.keys()) == {"error"}
    assert set(payload["error"].keys()) == {"code", "message", "retryable", "trace_id"}
    assert payload["error"]["code"] == "session_not_found"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["trace_id"] == "req-message-missing"
    assert response.headers["x-request-id"] == "req-message-missing"
