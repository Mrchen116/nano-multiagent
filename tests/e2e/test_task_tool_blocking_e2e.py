from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_tools_listing_contains_task_without_task_http_endpoint() -> None:
    app = create_app(auth_token="test-token")
    client = TestClient(app)

    response = client.get("/v1/tools", headers=_auth_headers("req-task-e2e"))

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["tools"]}
    assert "task" in names
    assert "/v1/tasks" not in {route.path for route in app.routes}
