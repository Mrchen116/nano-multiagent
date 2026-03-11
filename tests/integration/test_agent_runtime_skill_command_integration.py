from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.entries import SessionEntryKind
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}"),
            finish_reason="stop",
        )


def test_runtime_skill_command_rewrite_runs_through_normal_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "skill-command-runtime.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
    )

    result = runtime.run(
        session.session_id,
        [{"type": "text", "text": "/skill:doc polish this paragraph"}],
        stream=False,
    )

    rewritten = 'Use the "doc" skill for this request.\nUser input:\npolish this paragraph'
    assert llm.requests[-1].messages[-1].content == rewritten
    assert result.messages[0].content == f"ack:{rewritten}"

    loaded = store.load_session(session.session_id)
    assert loaded is not None
    turn_events = [event for event in loaded.events if event.kind is SessionEntryKind.TURN_APPENDED]
    assert len(turn_events) == 2
    assert turn_events[0].data["role"] == "user"
    assert turn_events[0].data["content"] == rewritten
    assert turn_events[1].data["role"] == "assistant"
