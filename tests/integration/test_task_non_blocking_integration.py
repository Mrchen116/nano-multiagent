from pathlib import Path
from time import monotonic, sleep

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


class RecordingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"subagent:{request.messages[-1].content}"),
            finish_reason="stop",
        )


def test_task_blocking_uses_parent_session_as_llm_session_id(tmp_path: Path) -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    parent = manager.create_session()
    llm = RecordingLLMClient()
    runtime = AgentRuntime(session_manager=manager, llm_client=llm, model="mock-model")
    app = create_app(runtime=runtime, repo_root=tmp_path)

    result = app.state.tool_registry.execute(
        "task",
        {"mode": "blocking", "prompt": "hello", "subagent_type": "oracle"},
        hook_context=HookContext(session_id=parent.session_id, repo_root=tmp_path),
    )

    assert result["status"] == "completed"
    assert result["session_id"] != parent.session_id
    assert llm.requests[-1].session_id == parent.session_id


def test_task_non_blocking_receipt_is_traceable_via_session_events(tmp_path: Path) -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    parent = manager.create_session()
    llm = RecordingLLMClient()
    runtime = AgentRuntime(session_manager=manager, llm_client=llm, model="mock-model")
    app = create_app(runtime=runtime, repo_root=tmp_path)

    receipt = app.state.tool_registry.execute(
        "task",
        {
            "mode": "non_blocking",
            "prompt": "background job",
            "subagent_type": "oracle",
            "idempotency_key": "idem-int-1",
        },
        hook_context=HookContext(session_id=parent.session_id, repo_root=tmp_path),
    )

    assert receipt["mode"] == "non_blocking"
    assert receipt["status"] == "running"
    task_session_id = receipt["session_id"]
    assert task_session_id != parent.session_id

    deadline = monotonic() + 2.0
    while monotonic() < deadline:
        messages = manager.list_turn_messages(task_session_id)
        if any(message.role == "assistant" for message in messages):
            break
        sleep(0.02)
    else:
        raise AssertionError("background task did not append assistant turn before timeout")

    assert llm.requests[-1].session_id == parent.session_id
