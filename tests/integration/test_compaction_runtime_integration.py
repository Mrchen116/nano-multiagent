from pathlib import Path

from agent.core.agent.compaction.types import CompactionReason, CompactionSettings
from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ModelError
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.entries import CompactionEntry
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


def test_compaction_entry_is_persisted_with_audit_anchor_and_replayable(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-baseline.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()

    first = manager.append_turn_message(
        session.session_id,
        turn_id="turn_1",
        role="user",
        content="old-question",
        message_id="msg_1",
    )
    second = manager.append_turn_message(
        session.session_id,
        turn_id="turn_1",
        role="assistant",
        content="old-answer",
        message_id="msg_2",
    )
    third = manager.append_turn_message(
        session.session_id,
        turn_id="turn_2",
        role="user",
        content="new-question",
        message_id="msg_3",
    )
    manager.append_compaction(
        session.session_id,
        first_kept_event_id=second.entry_id,
        summary="summary: old context compacted",
        data={"reason": "manual"},
    )

    loaded = store.load_session(session.session_id)
    assert loaded is not None
    compaction_entries = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert len(compaction_entries) == 1
    compaction = compaction_entries[0]
    assert compaction.first_kept_event_id == second.entry_id
    assert compaction.summary == "summary: old context compacted"
    assert compaction.data["reason"] == "manual"

    replayed = manager.list_turn_messages(session.session_id)
    assert [message.role for message in replayed] == ["system", "assistant", "user"]
    assert replayed[0].content == "summary: old context compacted"
    assert [message.content for message in replayed[1:]] == ["old-answer", "new-question"]
    assert first.entry_id != third.entry_id


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


class SummaryFailingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        if request.model == "summary-model":
            raise ModelError(
                "summary backend unavailable",
                details={"status_code": 503, "response": "summary service unavailable"},
            )
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="ack-after-fallback"),
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

    turn_events = [event for event in loaded.events if event.kind.value == "session.turn.appended"]
    first_kept_index = next(
        index
        for index, event in enumerate(turn_events)
        if event.entry_id == entry.first_kept_event_id
    )
    kept_contents = [event.data["content"] for event in turn_events[first_kept_index:]]
    replayed = manager.list_turn_messages(session.session_id)
    assert replayed[0].role == "system"
    assert replayed[0].content == entry.summary
    assert [message.content for message in replayed[1:]] == kept_contents


def test_session_compact_observe_hook_receives_manual_reason_event(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-manual-hook.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = ThresholdAwareLLMClient()
    observed_events: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_session_compact(event, ctx):
        del ctx
        observed_events.append(dict(event))

    hooks.on("session_compact", on_session_compact)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="main-model",
        hook_runner=HookRunner(registry=hooks),
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
    runtime.compact(session.session_id)

    assert observed_events
    assert any(
        event.get("session_id") == session.session_id
        and event.get("reason") == CompactionReason.MANUAL.value
        for event in observed_events
    )


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


def test_threshold_compaction_falls_back_when_summary_model_fails(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-summary-failure.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = SummaryFailingLLMClient()
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
    result = runtime.run(session.session_id, [{"type": "text", "text": "follow-up " * 20}], stream=False)

    assert result.messages[0].content == "ack-after-fallback"
    loaded = store.load_session(session.session_id)
    assert loaded is not None
    compactions = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.THRESHOLD.value
    assert "触发原因为 threshold" in compactions[-1].summary
