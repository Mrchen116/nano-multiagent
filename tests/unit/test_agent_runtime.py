from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.session.entries import SessionEntryKind
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


class FakeLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="runtime-pong"),
            finish_reason="stop",
        )


def test_runtime_run_appends_user_and_assistant_events() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    runtime = AgentRuntime(session_manager=manager, llm_client=FakeLLMClient(), model="mock-model")

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.session_id == session.session_id
    assert result.messages[0].role == "assistant"
    assert result.messages[0].content == "runtime-pong"
    created_event, user_event, assistant_event = [entry for _, entry in store.events]
    assert created_event.kind is SessionEntryKind.SESSION_CREATED
    assert user_event.kind is SessionEntryKind.TURN_APPENDED
    assert user_event.data["role"] == "user"
    assert user_event.data["content"] == "ping"
    assert assistant_event.kind is SessionEntryKind.TURN_APPENDED
    assert assistant_event.data["role"] == "assistant"
    assert assistant_event.data["content"] == "runtime-pong"


def test_runtime_builds_followup_context_from_session_events() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(session_manager=manager, llm_client=llm_client, model="mock-model")

    runtime.run(session.session_id, [{"type": "text", "text": "first"}], stream=False)
    runtime.run(session.session_id, [{"type": "text", "text": "second"}], stream=False)

    second_call_messages = llm_client.requests[-1].messages
    assert [message.role for message in second_call_messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert second_call_messages[1].content == "first"
    assert second_call_messages[2].content == "runtime-pong"
    assert second_call_messages[3].content == "second"
