from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.core.hooks.context import HookContext
from nano_multiagent.platform.http_api.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0

    def create_session(self):  # noqa: ANN001
        self.created += 1
        return type("Session", (), {"session_id": f"sess_task_e2e_{self.created}"})()

    def run(self, session_id: str, parts, *, stream: bool = True, llm_session_id: str | None = None, run_id: str | None = None) -> TurnResult:  # noqa: ANN001
        del parts, stream, llm_session_id
        return TurnResult(
            session_id=session_id,
            turn_id="turn_task_e2e",
            messages=(Message(message_id="msg_task_e2e", role="assistant", content="task-e2e-ok"),),
            completed=True,
            stop_reason="completed",
        )


def test_tools_listing_contains_task_without_task_http_endpoint(tmp_path) -> None:  # noqa: ANN001
    app = create_app(auth_token="test-token", runtime=_RuntimeStub(), repo_root=tmp_path)
    client = TestClient(app)

    response = client.get("/v1/tools", headers=_auth_headers("req-task-e2e"))

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["tools"]}
    assert "task" in names
    assert "/v1/tasks" not in {route.path for route in app.routes}

    result = app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "run e2e",
            "prompt": "run e2e",
            "subagent_type": "oracle",
        },
        hook_context=HookContext(session_id="sess_main_e2e", repo_root=tmp_path),
    )
    assert result["result"].startswith("Task completed in ")
    assert "Agent: oracle" in result["result"]
    assert "\n---\n\ntask-e2e-ok\n" in result["result"]
    assert "<task_metadata>\nsession_id: sess_task_e2e_1\n</task_metadata>" in result["result"]
