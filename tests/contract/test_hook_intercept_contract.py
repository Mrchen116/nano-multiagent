from pathlib import Path

from fastapi.testclient import TestClient

from agent.platform.http_api.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_builtin_hook_modules_are_visible_in_hooks_query_contract(tmp_path: Path) -> None:
    client = TestClient(create_app(repo_root=tmp_path, auth_token="test-token"))

    response = client.get("/v1/hooks", headers=_auth_headers("req-hooks-builtin-contract"))

    assert response.status_code == 200
    hooks = response.json()["hooks"]
    builtin_hooks = [item for item in hooks if item["source"] == "builtin"]

    assert builtin_hooks
    critical_events = {item["event"] for item in builtin_hooks}
    assert {"session_shutdown", "run_timeout"} <= critical_events
