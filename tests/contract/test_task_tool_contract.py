from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_task_tool_contract_is_exposed_by_tools_endpoint() -> None:
    app = create_app(auth_token="test-token")
    client = TestClient(app)

    response = client.get("/v1/tools", headers=_auth_headers("req-task-contract"))

    assert response.status_code == 200
    task_descriptor = next(item for item in response.json()["tools"] if item["name"] == "task")
    assert task_descriptor["input_schema"]["required"] == ["mode"]
    assert task_descriptor["input_schema"]["properties"]["mode"]["enum"] == ["blocking", "non_blocking"]
    assert "idempotency_key" in task_descriptor["input_schema"]["properties"]
    assert "timeout_seconds" in task_descriptor["input_schema"]["properties"]
    assert "category" in task_descriptor["input_schema"]["properties"]
    assert "subagent_type" in task_descriptor["input_schema"]["properties"]
    assert "/v1/tasks" not in {route.path for route in app.routes}
