import pytest
from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.app import create_app
from nano_multiagent.server.routes.session import _CONTEXT_BUDGET_MAX_TOKENS
from nano_multiagent.server.deps import APIError
from nano_multiagent.server.routes.session import _to_message_response


def test_to_message_response_uses_assistant_message_contract() -> None:
    result = TurnResult(
        session_id="sess_unit",
        turn_id="turn_unit",
        messages=(
            Message(message_id="msg_user", role="user", content="hello"),
            Message(message_id="msg_assistant", role="assistant", content="hi"),
        ),
        completed=True,
        stop_reason="completed",
    )

    payload = _to_message_response(result)

    assert payload["session_id"] == "sess_unit"
    assert payload["turn_id"] == "turn_unit"
    assert payload["message"]["message_id"] == "msg_assistant"
    assert payload["message"]["role"] == "assistant"
    assert payload["message"]["content"] == "hi"
    assert payload["completed"] is True
    assert payload["stop_reason"] == "completed"


def test_to_message_response_raises_when_no_assistant_message() -> None:
    result = TurnResult(
        session_id="sess_unit",
        turn_id="turn_unit",
        messages=(Message(message_id="msg_user", role="user", content="only-user"),),
    )

    with pytest.raises(APIError) as exc_info:
        _to_message_response(result)

    assert exc_info.value.code == "invalid_runtime_response"


def test_context_budget_caps_usage_and_ratio_for_long_history() -> None:
    client = TestClient(create_app(auth_token="test-token"))
    headers = {"Authorization": "Bearer test-token"}

    created = client.post("/v1/sessions", json={}, headers=headers)
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    manager = client.app.state.session_service.manager
    manager.append_turn_message(
        session_id,
        turn_id="turn_budget",
        role="user",
        content="x" * 1_000_000,
        message_id="msg_budget",
    )

    response = client.get(f"/v1/sessions/{session_id}/context-budget", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["max_tokens"] == _CONTEXT_BUDGET_MAX_TOKENS
    assert payload["used_tokens"] == _CONTEXT_BUDGET_MAX_TOKENS
    assert payload["remaining_tokens"] == 0
    assert payload["usage_ratio"] == 1.0
