import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.context import HookContext
from agent.core.llm.interfaces import LLMGenerateResponse, LLMMessage, LLMToolCall
from agent.core.session.manager import SessionManager
from agent.core.types import Message, TurnResult
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore
from agent.platform.tools.loader import build_tool_registry

REPO_ROOT = Path(__file__).resolve().parents[2]


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0

    def create_session(self, *, title: str | None = None, metadata=None):  # noqa: ANN001
        del title, metadata
        self.created += 1
        return type("Session", (), {"session_id": f"sess_task_e2e_{self.created}"})()

    def run(self, session_id: str, parts, *, stream: bool = True, llm_session_id: str | None = None, run_id: str | None = None, controller=None) -> TurnResult:  # noqa: ANN001
        del parts, stream, llm_session_id
        return TurnResult(
            session_id=session_id,
            turn_id="turn_task_e2e",
            messages=(Message(message_id="msg_task_e2e", role="assistant", content="task-e2e-ok"),),
            completed=True,
            stop_reason="completed",
        )


class _TaskDelegatingPwdLLM:
    def generate(self, request):  # noqa: ANN001, ANN201
        last_message = request.messages[-1]
        if last_message.role == "user" and last_message.content == "delegate pwd":
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_task",
                            name="task",
                            arguments={
                                "run_in_background": False,
                                "load_skills": [],
                                "description": "delegate pwd",
                                "prompt": "subagent pwd",
                                "subagent_type": "oracle",
                            },
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            )
        if last_message.role == "user" and last_message.content == "subagent pwd":
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(call_id="call_pwd", name="bash", arguments={"command": "pwd"}),
                    ),
                ),
                finish_reason="tool_calls",
            )
        payload = json.loads(last_message.content)
        if last_message.role == "tool" and last_message.tool_call_id == "call_pwd":
            output = payload.get("output", {}) if isinstance(payload, dict) else {}
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(role="assistant", content=str(output.get("content", "")).strip()),
                finish_reason="stop",
            )
        if last_message.role == "tool" and last_message.tool_call_id == "call_task":
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(role="assistant", content=str(payload.get("output", "")).strip()),
                finish_reason="stop",
            )
        raise AssertionError(f"unexpected request flow: {last_message}")


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


def test_task_subagent_inherits_parent_workspace_root_for_real_pwd(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-root"
    workspace_root = tmp_path / "workspace-root"
    repo_root.mkdir()
    workspace_root.mkdir()

    store = SQLiteSessionStore(db_path=tmp_path / "task-workspace.sqlite3")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_TaskDelegatingPwdLLM(),
        model="mock-model",
        repo_root=repo_root,
    )
    tool_registry = build_tool_registry(repo_root=repo_root, runtime=runtime)
    app = create_app(
        auth_token="test-token",
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
        repo_root=REPO_ROOT,
    )
    client = TestClient(app)

    created = client.post(
        "/v1/sessions",
        json={"workspace_root": str(workspace_root)},
        headers=_auth_headers("req-task-workspace-create"),
    )
    assert created.status_code == 201
    parent_session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{parent_session_id}/messages",
        json={"parts": [{"type": "text", "text": "delegate pwd"}], "stream": False},
        headers=_auth_headers("req-task-workspace-message"),
    )

    assert response.status_code == 200
    content = str(response.json()["message"]["content"])
    assert str(workspace_root.resolve()) in content
    assert str(repo_root.resolve()) not in content

    sessions, _ = app.state.session_service.list_sessions(limit=10, offset=0)
    child_sessions = [session for session in sessions if session.session_id != parent_session_id]
    assert len(child_sessions) == 1
    assert child_sessions[0].metadata["workspace_root"] == str(workspace_root.resolve())
