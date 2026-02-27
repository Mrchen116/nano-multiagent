from time import monotonic, sleep

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.server.app import create_app
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.base import LoadedSession, SessionStore


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.snapshots: dict[str, dict[str, object]] = {}

    def append_event(self, session_id: str, entry: object) -> None:
        self.events.append((session_id, entry))

    def load_session(self, session_id: str) -> LoadedSession | None:
        session_events = tuple(entry for sid, entry in self.events if sid == session_id)
        if not session_events and session_id not in self.snapshots:
            return None
        return LoadedSession(
            session_id=session_id,
            events=session_events,
            snapshot=self.snapshots.get(session_id),
        )

    def save_snapshot(self, session_id: str, snapshot: dict[str, object]) -> None:
        self.snapshots[session_id] = snapshot


class EchoLLMClient:
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}"),
            finish_reason="stop",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_task_non_blocking_returns_immediately_and_does_not_block_parent_flow(tmp_path) -> None:  # noqa: ANN001
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    runtime = AgentRuntime(session_manager=manager, llm_client=EchoLLMClient(), model="mock-model")
    app = create_app(runtime=runtime, repo_root=tmp_path, auth_token="test-token")
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-task-nb-create"))
    assert created.status_code == 201
    parent_session_id = created.json()["session_id"]

    receipt = app.state.tool_registry.execute(
        "task",
        {
            "mode": "non_blocking",
            "prompt": "background e2e",
            "subagent_type": "oracle",
            "idempotency_key": "idem-e2e-1",
        },
        hook_context=HookContext(session_id=parent_session_id, repo_root=tmp_path),
    )
    assert receipt["status"] == "running"
    task_session_id = receipt["session_id"]

    parent_response = client.post(
        f"/v1/sessions/{parent_session_id}/messages",
        json={"parts": [{"type": "text", "text": "parent still runs"}], "stream": False},
        headers=_auth_headers("req-task-nb-parent"),
    )
    assert parent_response.status_code == 200
    assert parent_response.json()["message"]["content"] == "ack:parent still runs"

    deadline = monotonic() + 2.0
    while monotonic() < deadline:
        task_messages = manager.list_turn_messages(task_session_id)
        if any(message.role == "assistant" for message in task_messages):
            break
        sleep(0.02)
    else:
        raise AssertionError("non_blocking task did not finish before timeout")
