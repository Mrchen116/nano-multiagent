import pytest
from fastapi.testclient import TestClient

from agent.core.types import Message, TokenUsage, TurnResult
from agent.platform.hooks.session_usage import (
    SessionUsageSnapshot,
    set_session_usage_snapshot_reader,
)
from agent.platform.http_api.app import create_app
from agent.platform.http_api.deps import APIError
from agent.platform.http_api.routes.session import _CONTEXT_BUDGET_MAX_TOKENS, _to_message_response


def test_server_session_shim_reexports_context_budget_constant() -> None:
    assert _CONTEXT_BUDGET_MAX_TOKENS > 0



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


def test_to_message_response_includes_usage_when_present() -> None:
    result = TurnResult(
        session_id="sess_unit",
        turn_id="turn_unit",
        messages=(Message(message_id="msg_assistant", role="assistant", content="hi"),),
        completed=True,
        stop_reason="completed",
        usage=TokenUsage(prompt_tokens=21, completion_tokens=8, total_tokens=29),
    )

    payload = _to_message_response(result)

    assert payload["usage"] == {
        "prompt_tokens": 21,
        "completion_tokens": 8,
        "total_tokens": 29,
    }


def test_to_message_response_raises_when_no_assistant_message() -> None:
    result = TurnResult(
        session_id="sess_unit",
        turn_id="turn_unit",
        messages=(Message(message_id="msg_user", role="user", content="only-user"),),
    )

    with pytest.raises(APIError) as exc_info:
        _to_message_response(result)

    assert exc_info.value.code == "invalid_runtime_response"


def test_context_budget_defaults_to_zero_without_exact_usage_snapshot() -> None:
    client = TestClient(create_app(auth_token="test-token"))
    headers = {"Authorization": "Bearer test-token"}

    created = client.post("/v1/sessions", json={}, headers=headers)
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.get(f"/v1/sessions/{session_id}/context-budget", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["max_tokens"] == _CONTEXT_BUDGET_MAX_TOKENS
    assert payload["used_tokens"] == 0
    assert payload["remaining_tokens"] == _CONTEXT_BUDGET_MAX_TOKENS
    assert payload["usage_ratio"] == 0.0


def test_context_budget_prefers_latest_provider_total_tokens_when_available() -> None:
    client = TestClient(create_app(auth_token="test-token"))
    headers = {"Authorization": "Bearer test-token"}

    created = client.post("/v1/sessions", json={}, headers=headers)
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    set_session_usage_snapshot_reader(
        registry=client.app.state.hook_registry,
        reader=lambda sid: (
            SessionUsageSnapshot(
                prompt_tokens=800,
                completion_tokens=80,
                total_tokens=880,
                last_prompt_tokens=4321,
                last_completion_tokens=40,
                last_total_tokens=12345,
                turn_count=2,
            )
            if sid == session_id
            else None
        )
    )

    response = client.get(f"/v1/sessions/{session_id}/context-budget", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["used_tokens"] == 12345
    assert payload["remaining_tokens"] == _CONTEXT_BUDGET_MAX_TOKENS - 12345
    assert payload["usage_ratio"] == 12345 / _CONTEXT_BUDGET_MAX_TOKENS
