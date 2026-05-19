import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.context import HookContext
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.types import Message, TurnResult
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.loader import build_tool_registry

REPO_ROOT = Path(__file__).resolve().parents[2]


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_completed_run(client: TestClient, run_id: str, request_id: str, *, timeout_seconds: float = 10.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers(request_id))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


class _RuntimeStub:
    def __init__(self, tmp_path: Path) -> None:
        self.created = 0
        from agent.core.session.jsonl_store import JsonlSessionStore, SessionConfig
        from agent.core.session.manager import SessionManager
        from datetime import UTC, datetime
        self._tmp_path = tmp_path
        self._SessionConfig = SessionConfig
        self._utc_now = lambda: datetime.now(UTC).isoformat()
        self._session_manager = SessionManager(store=JsonlSessionStore(data_dir=tmp_path / "stub-sessions"))

    async def create_session(self, **kwargs) -> object:  # noqa: ANN003
        workspace_root = kwargs.get("workspace_root") or self._tmp_path
        metadata = kwargs.get("metadata", {})
        parent_session_id = kwargs.get("parent_session_id")
        self.created += 1
        session_id = f"sess_task_e2e_{self.created}"
        from pathlib import Path as _Path
        config = self._SessionConfig(
            session_id=session_id,
            created_at=self._utc_now(),
            workspace_root=_Path(workspace_root) if workspace_root else self._tmp_path,
            metadata=metadata or {},
        )
        self._session_manager.store.create(session_id, config, parent_session_id=parent_session_id)
        return type("Session", (), {"session_id": session_id})()

    async def run(self, session_id: str, parts, **kwargs) -> TurnResult:  # noqa: ANN003
        del parts, kwargs
        return TurnResult(
            session_id=session_id,
            turn_id="turn_task_e2e",
            messages=(Message(message_id="msg_task_e2e", role="assistant", content="task-e2e-ok"),),
            completed=True,
            stop_reason="completed",
        )


class _TaskDelegatingPwdLLM:
    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:  # type: ignore[override]
        last_message = request.messages[-1]
        if last_message.role == "user" and last_message.content == "delegate pwd":
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="call_task",
                        name="agent",
                        arguments={
                            "run_in_background": False,
                            "load_skills": [],
                            "description": "delegate pwd",
                            "prompt": "subagent pwd",
                            "subagent_type": "oracle",
                        },
                    ),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
            return
        if last_message.role == "user" and last_message.content == "subagent pwd":
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(call_id="call_pwd", name="bash", arguments={"command": "pwd"}),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
            return
        if last_message.role == "tool" and last_message.tool_call_id == "call_pwd":
            # bash tool's serialize_result returns raw stdout, not JSON
            yield LLMMessage(role="assistant", content=str(last_message.content).strip(), finish_reason="stop")
            return
        if last_message.role == "tool" and last_message.tool_call_id == "call_task":
            # agent tool result is plain text (serialize_result formats it)
            yield LLMMessage(role="assistant", content=str(last_message.content).strip(), finish_reason="stop")
            return
        raise AssertionError(f"unexpected request flow: {last_message}")


def test_tools_listing_contains_agent_without_task_http_endpoint(tmp_path: Path) -> None:
    app = create_app(runtime=_RuntimeStub(tmp_path), repo_root=tmp_path)
    client = TestClient(app)

    response = client.get("/v1/tools", headers=_auth_headers("req-task-e2e"))

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["tools"]}
    assert "agent" in names
    assert "/v1/tasks" not in {route.path for route in app.routes}

    import asyncio
    result = asyncio.run(app.state.tool_registry.execute(
        "agent",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "run e2e",
            "prompt": "run e2e",
            "subagent_type": "oracle",
        },
        hook_context=HookContext(session_id="sess_main_e2e", repo_root=tmp_path),
    ))
    assert result.get("status") == "completed"
    assert result.get("content") == "task-e2e-ok"
    assert "agent_id" in result


def test_task_subagent_inherits_parent_workspace_root_for_real_pwd(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-root"
    workspace_root = tmp_path / "workspace-root"
    repo_root.mkdir()
    workspace_root.mkdir()

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=_TaskDelegatingPwdLLM(),
        model="mock-model",
        repo_root=repo_root,
    )
    tool_registry = build_tool_registry(repo_root=repo_root, runtime=runtime)
    app = create_app(
        session_store=service.manager._store,
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

    submitted = client.post(
        f"/v1/sessions/{parent_session_id}/messages",
        json={"parts": [{"type": "text", "text": "delegate pwd"}]},
        headers=_auth_headers("req-task-workspace-message"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    terminal = _wait_for_completed_run(client, run_id, "req-task-workspace-poll")
    assert terminal["status"] == "completed"
    content = str(terminal["output_text"])
    assert str(workspace_root.resolve()) in content
    assert str(repo_root.resolve()) not in content

    sessions, _ = app.state.session_service.list_sessions(limit=10, offset=0)
    child_sessions = [session for session in sessions if session.session_id != parent_session_id]
    assert len(child_sessions) == 1
    assert child_sessions[0].metadata["workspace_root"] == str(workspace_root.resolve())
