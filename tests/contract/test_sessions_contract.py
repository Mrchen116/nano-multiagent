from fastapi.testclient import TestClient

from nano_multiagent.platform.http_api.app import create_app


def _auth_headers(request_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": "Bearer test-token"}
    if request_id is not None:
        headers["X-Request-Id"] = request_id
    return headers


def test_create_session_contract() -> None:
    client = TestClient(create_app())

    response = client.post('/v1/sessions', json={}, headers=_auth_headers("req-create-contract"))

    assert response.status_code == 201
    assert response.headers["x-request-id"] == "req-create-contract"
    payload = response.json()
    assert set(payload.keys()) == {'session_id', 'status', 'created_at'}
    assert payload['session_id'].startswith('sess_')
    assert payload['status'] == 'active'
    assert isinstance(payload['created_at'], str)


def test_sessions_require_bearer_auth_and_use_unified_error_shape() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/sessions", headers={"X-Request-Id": "req-auth-missing"})

    assert response.status_code == 401
    payload = response.json()
    assert set(payload.keys()) == {"error"}
    assert set(payload["error"].keys()) == {"code", "message", "retryable", "trace_id"}
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["trace_id"] == "req-auth-missing"
    assert response.headers["x-request-id"] == "req-auth-missing"


def test_get_and_list_sessions_contract_with_minimal_pagination() -> None:
    client = TestClient(create_app())
    headers = _auth_headers("req-list-contract")

    first = client.post("/v1/sessions", json={}, headers=headers)
    second = client.post("/v1/sessions", json={}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    first_id = first.json()["session_id"]

    get_response = client.get(f"/v1/sessions/{first_id}", headers=headers)
    assert get_response.status_code == 200
    session_payload = get_response.json()
    assert set(session_payload.keys()) == {"session_id", "status", "created_at"}
    assert session_payload["session_id"] == first_id
    assert session_payload["status"] == "active"

    list_response = client.get("/v1/sessions?limit=1&offset=0", headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert set(list_payload.keys()) == {"items", "limit", "offset", "has_more"}
    assert list_payload["limit"] == 1
    assert list_payload["offset"] == 0
    assert isinstance(list_payload["has_more"], bool)
    assert isinstance(list_payload["items"], list)
    assert len(list_payload["items"]) == 1
    assert set(list_payload["items"][0].keys()) == {"session_id", "status", "created_at"}


def test_session_compact_tools_and_context_budget_contract() -> None:
    client = TestClient(create_app())
    headers = _auth_headers("req-session-compact-tools-contract")

    created = client.post("/v1/sessions", json={}, headers=headers)
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    tools_response = client.get(f"/v1/sessions/{session_id}/tools", headers=headers)
    assert tools_response.status_code == 200
    tools_payload = tools_response.json()
    assert set(tools_payload.keys()) == {"session_id", "tools"}
    assert tools_payload["session_id"] == session_id
    assert isinstance(tools_payload["tools"], list)
    assert tools_payload["tools"]
    assert set(tools_payload["tools"][0].keys()) == {"name", "description", "input_schema"}

    compact_response = client.post(f"/v1/sessions/{session_id}:compact", json={}, headers=headers)
    assert compact_response.status_code == 200
    compact_payload = compact_response.json()
    assert set(compact_payload.keys()) == {"session_id", "compacted", "result"}
    assert compact_payload["session_id"] == session_id
    assert isinstance(compact_payload["compacted"], bool)
    if compact_payload["compacted"] is False:
        assert compact_payload["result"] is None

    budget_response = client.get(f"/v1/sessions/{session_id}/context-budget", headers=headers)
    assert budget_response.status_code == 200
    budget_payload = budget_response.json()
    assert set(budget_payload.keys()) == {"session_id", "used_tokens", "max_tokens", "remaining_tokens", "usage_ratio"}
    assert budget_payload["session_id"] == session_id
    assert isinstance(budget_payload["used_tokens"], int)
    assert isinstance(budget_payload["max_tokens"], int)
    assert isinstance(budget_payload["remaining_tokens"], int)
    assert isinstance(budget_payload["usage_ratio"], float)


def test_session_compact_tools_and_context_budget_return_404_for_unknown_session() -> None:
    client = TestClient(create_app())
    headers = _auth_headers("req-session-compact-tools-404-contract")
    missing_session_id = "sess_missing_contract"

    tools_response = client.get(f"/v1/sessions/{missing_session_id}/tools", headers=headers)
    assert tools_response.status_code == 404
    tools_error = tools_response.json()["error"]
    assert tools_error["code"] == "session_not_found"

    compact_response = client.post(f"/v1/sessions/{missing_session_id}:compact", json={}, headers=headers)
    assert compact_response.status_code == 404
    compact_error = compact_response.json()["error"]
    assert compact_error["code"] == "session_not_found"

    budget_response = client.get(f"/v1/sessions/{missing_session_id}/context-budget", headers=headers)
    assert budget_response.status_code == 404
    budget_error = budget_response.json()["error"]
    assert budget_error["code"] == "session_not_found"
