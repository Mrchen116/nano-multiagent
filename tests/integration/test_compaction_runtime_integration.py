from pathlib import Path

from nano_multiagent.agent.compaction.types import CompactionReason, CompactionSettings
from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.errors import ModelError
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.session.entries import CompactionEntry, SessionEntryKind
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class ThresholdAwareLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        if request.model == "summary-model":
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(role="assistant", content="summary: older context"),
                finish_reason="stop",
            )
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="ack"),
            finish_reason="stop",
        )


class OverflowOnceLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._overflow_raised = False

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        if request.model == "summary-model":
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(role="assistant", content="summary: overflow rescue"),
                finish_reason="stop",
            )
        if not self._overflow_raised and len(request.messages) >= 4:
            self._overflow_raised = True
            raise ModelError(
                "context overflow",
                details={
                    "status_code": 400,
                    "response": "maximum context length exceeded",
                },
            )
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="retry-ok"),
            finish_reason="stop",
        )


def test_threshold_preflight_compacts_and_rebuilds_context(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-threshold.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = ThresholdAwareLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="main-model",
        compaction_settings=CompactionSettings(
            enabled=True,
            context_window=60,
            reserve_tokens=10,
            min_kept_messages=2,
            summary_model="summary-model",
        ),
    )

    runtime.run(session.session_id, [{"type": "text", "text": "hello " * 20}], stream=False)
    runtime.run(session.session_id, [{"type": "text", "text": "follow-up " * 20}], stream=False)

    loaded = store.load_session(session.session_id)
    assert loaded is not None
    compactions = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert compactions
    entry = compactions[-1]
    assert entry.data["reason"] == CompactionReason.THRESHOLD.value
    assert isinstance(entry.first_kept_event_id, str) and entry.first_kept_event_id

    main_requests = [request for request in llm_client.requests if request.model == "main-model"]
    assert len(main_requests) >= 2
    second_main_messages = main_requests[-1].messages
    assert second_main_messages[1].role == "system"
    assert "summary" in second_main_messages[1].content.lower()


def test_manual_compaction_writes_auditable_entry_and_replays_from_anchor(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-manual.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = ThresholdAwareLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="main-model",
        compaction_settings=CompactionSettings(
            enabled=True,
            context_window=200,
            reserve_tokens=40,
            min_kept_messages=2,
            summary_model="summary-model",
        ),
    )

    runtime.run(session.session_id, [{"type": "text", "text": "first user"}], stream=False)
    runtime.run(session.session_id, [{"type": "text", "text": "second user"}], stream=False)

    result = runtime.compact(session.session_id)

    assert result is not None
    assert result.reason is CompactionReason.MANUAL
    loaded = store.load_session(session.session_id)
    assert loaded is not None
    compactions = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert compactions
    entry = compactions[-1]
    assert entry.first_kept_event_id == result.first_kept_event_id

    turn_events = [event for event in loaded.events if event.kind is SessionEntryKind.TURN_APPENDED]
    kept_contents = [
        event.data["content"]
        for event in turn_events
        if event.entry_id >= entry.first_kept_event_id
    ]
    replayed = manager.list_turn_messages(session.session_id)
    assert replayed[0].role == "system"
    assert replayed[0].content == entry.summary
    assert [message.content for message in replayed[1:]] == kept_contents


def test_overflow_post_turn_check_compacts_then_retries(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-overflow.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = OverflowOnceLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="main-model",
        compaction_settings=CompactionSettings(
            enabled=True,
            context_window=200,
            reserve_tokens=40,
            min_kept_messages=2,
            summary_model="summary-model",
        ),
    )

    runtime.run(session.session_id, [{"type": "text", "text": "first turn"}], stream=False)
    result = runtime.run(session.session_id, [{"type": "text", "text": "second turn"}], stream=False)

    assert result.messages[0].content == "retry-ok"
    loaded = store.load_session(session.session_id)
    assert loaded is not None
    compactions = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.OVERFLOW.value

    main_calls = [request for request in llm_client.requests if request.model == "main-model"]
    assert len(main_calls) == 3
