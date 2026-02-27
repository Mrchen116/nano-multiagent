from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_hooks_query_endpoints_expose_workspace_hooks(tmp_path: Path) -> None:
    hooks_dir = tmp_path / ".nano" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "sample_hook.py").write_text(
        """
def setup(hooks):
    def on_input(event, ctx):
        del ctx
        return {"action": "transform", "text": event["text"].upper()}
    hooks.on("input", on_input, priority=25, timeout_ms=700)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(create_app(repo_root=tmp_path, auth_token="test-token"))

    list_response = client.get("/v1/hooks", headers=_auth_headers("req-hooks-e2e-list"))
    assert list_response.status_code == 200
    assert list_response.headers["x-request-id"] == "req-hooks-e2e-list"

    hooks = list_response.json()["hooks"]
    assert hooks
    workspace_hook = next(item for item in hooks if item["source"] == "workspace")
    assert workspace_hook["event"] == "input"
    assert workspace_hook["priority"] == 25
    assert workspace_hook["timeout_ms"] == 700
    assert workspace_hook["file_path"].endswith("sample_hook.py")

    events_response = client.get("/v1/hooks/events", headers=_auth_headers("req-hooks-e2e-events"))
    assert events_response.status_code == 200
    by_name = {item["event"]: item for item in events_response.json()["events"]}
    assert by_name["input"]["mode"] == "intercept"
    assert "action" in by_name["input"]["return_contract"]
