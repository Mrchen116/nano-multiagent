import time
from dataclasses import dataclass
from pathlib import Path

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.server.app import create_app
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class _RecordingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="subagent-ok"),
            finish_reason="stop",
        )


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []

    def create_session(self) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_non_blocking_integration_{self.created}")

    def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        self.run_calls.append(
            {
                "session_id": session_id,
                "parts": parts,
                "stream": stream,
                "llm_session_id": llm_session_id,
            }
        )
        time.sleep(0.05)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_non_blocking_integration",
            messages=(Message(message_id="msg_non_blocking_integration", role="assistant", content="done"),),
            completed=True,
            stop_reason="completed",
        )

    def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None):  # noqa: ANN201
        del stream, llm_session_id
        return self.run(session_id, [{"type": "text", "text": "continue"}], stream=False)


def _wait_for(predicate, *, timeout_seconds: float = 0.6) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def test_task_blocking_passes_parent_session_id_to_subagent_llm(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "task-pass-through.sqlite3")
    llm_client = _RecordingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm_client,
        model="mock-model",
    )
    app = create_app(runtime=runtime, session_store=store, repo_root=tmp_path)

    result = app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": ["playwright"],
            "description": "delegate task",
            "prompt": "delegate this",
            "category": "research",
        },
        hook_context=HookContext(session_id="sess_main_header", repo_root=tmp_path),
    )

    assert result["status"] == "completed"
    assert result["session_id"] != "sess_main_header"
    assert llm_client.requests[0].session_id == "sess_main_header"


def test_task_non_blocking_executes_on_same_node_and_returns_receipt(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    app = create_app(runtime=runtime, repo_root=tmp_path)

    result = app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": True,
            "load_skills": [],
            "description": "delegate task",
            "prompt": "run async",
            "subagent_type": "oracle",
        },
        hook_context=HookContext(session_id="sess_main_non_blocking", repo_root=tmp_path),
    )

    assert result["mode"] == "non_blocking"
    assert result["run_in_background"] is True
    assert result["status"] == "queued"
    assert result["session_id"] == "sess_non_blocking_integration_1"
    _wait_for(lambda: len(runtime.run_calls) == 1)
