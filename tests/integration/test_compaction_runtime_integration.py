from pathlib import Path

from agent.core.agent.compaction.types import CompactionReason, CompactionSettings
from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ModelError
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
from agent.core.session.entries import CompactionEntry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService


async def test_compaction_entry_is_persisted_with_audit_anchor_and_replayable(
    tmp_path: Path,
) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)

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
        first_kept_event_id="",
        summary="summary: old context compacted",
        data={"reason": "manual"},
    )
    manager.store.writer.flush()

    compaction_entries = [
        event
        for event in manager.list_entries(session.session_id)
        if isinstance(event, CompactionEntry)
    ]
    assert len(compaction_entries) == 1
    compaction = compaction_entries[0]
    assert compaction.first_kept_event_id == ""
    assert compaction.summary == "summary: old context compacted"
    assert compaction.data["reason"] == "manual"

    replayed = manager.list_turn_messages(session.session_id)
    # Full-compact design: no kept tail, summary is a user message.
    assert len(replayed) == 1
    assert replayed[0].role == "user"
    assert "summary: old context compacted" in replayed[0].content
    assert first.entry_id != third.entry_id


class ThresholdAwareLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        self.requests.append(request)
        if request.model == "summary-model":
            yield LLMMessage(role="assistant", content="summary: older context")
        else:
            yield LLMMessage(role="assistant", content="ack")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


class OverflowOnceLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._overflow_raised = False

    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        self.requests.append(request)
        if request.model == "summary-model":
            yield LLMMessage(role="assistant", content="summary: overflow rescue")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return
        if not self._overflow_raised and len(request.messages) >= 4:
            self._overflow_raised = True
            raise ModelError(
                "context overflow",
                details={
                    "status_code": 400,
                    "response": "maximum context length exceeded",
                },
            )
        yield LLMMessage(role="assistant", content="retry-ok")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


class SummaryFailingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        self.requests.append(request)
        if _is_compaction_request(request):
            raise ModelError(
                "summary backend unavailable",
                details={"status_code": 503, "response": "summary service unavailable"},
            )
        yield LLMMessage(role="assistant", content="ack-after-fallback")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


def _is_compaction_request(request: LLMGenerateRequest) -> bool:
    return any("Do NOT call any tools" in (m.content or "") for m in request.messages)


async def test_threshold_preflight_compacts_and_rebuilds_context(
    tmp_path: Path,
) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "hello " * 20}], stream=False
    )
    await runtime.run(
        session.session_id, [{"type": "text", "text": "follow-up " * 20}], stream=False
    )

    compactions = [
        event
        for event in manager.list_entries(session.session_id)
        if isinstance(event, CompactionEntry)
    ]
    assert compactions
    entry = compactions[-1]
    assert entry.data["reason"] == CompactionReason.THRESHOLD.value
    assert isinstance(entry.first_kept_event_id, str)

    main_requests = [
        request for request in llm_client.requests if request.model == "main-model"
    ]
    assert len(main_requests) >= 2
    second_main_messages = main_requests[-1].messages
    # Summary is now a user message, not system.
    # Find the first user message after the system prompt.
    user_messages = [m for m in second_main_messages if m.role == "user"]
    assert user_messages
    assert (
        "summary" in user_messages[0].content.lower()
        or "continue" in user_messages[0].content.lower()
    )


async def test_manual_compaction_writes_auditable_entry_and_replays_from_anchor(
    tmp_path: Path,
) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "first user"}], stream=False
    )
    await runtime.run(
        session.session_id, [{"type": "text", "text": "second user"}], stream=False
    )

    result = await runtime.compact(session.session_id)

    assert result is not None
    assert result.reason is CompactionReason.MANUAL
    compactions = [
        event
        for event in manager.list_entries(session.session_id)
        if isinstance(event, CompactionEntry)
    ]
    assert compactions
    entry = compactions[-1]
    assert entry.first_kept_event_id == result.first_kept_event_id == ""

    # Full-compact design: no kept tail, replayed is just summary user message.
    replayed = manager.list_turn_messages(session.session_id)
    assert replayed[0].role == "user"
    assert entry.summary in replayed[0].content


async def test_session_compact_observe_hook_receives_manual_reason_event(
    tmp_path: Path,
) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "first user"}], stream=False
    )
    await runtime.run(
        session.session_id, [{"type": "text", "text": "second user"}], stream=False
    )
    await runtime.compact(session.session_id)

    assert observed_events
    assert any(
        event.get("session_id") == session.session_id
        and event.get("reason") == CompactionReason.MANUAL.value
        for event in observed_events
    )


async def test_overflow_post_turn_check_compacts_then_retries(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "first turn"}], stream=False
    )
    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "second turn"}], stream=False
    )

    assert result.messages[0].content == "retry-ok"
    compactions = [
        event
        for event in manager.list_entries(session.session_id)
        if isinstance(event, CompactionEntry)
    ]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.OVERFLOW.value

    main_calls = [
        request for request in llm_client.requests if request.model == "main-model"
    ]
    # 1st turn + 2nd turn (overflow) + retry = 3; summary uses summary-model separately
    assert len(main_calls) == 3


def _workspace_aware_service(tmp_path: Path) -> SessionService:
    """Build a SessionService in production workspace-aware mode (``data_dir=None``).

    bugfix-437: the original crash only reproduces here — the ``data_dir``
    scaffolding used by every other test in this file lets ``_resolve_base``
    return the flat dir and ignore ``workspace_root``, so the compaction read /
    persist paths that forget to pass ``workspace_root`` never fail under test.
    """

    store = JsonlSessionStore(data_dir=None, workspace_config_dirname=".nano")
    return SessionService(store=store)


async def test_threshold_compaction_workspace_aware_does_not_crash(
    tmp_path: Path,
) -> None:
    # bugfix-437 regression (decision 1): threshold pre-compaction reads history
    # via loop._maybe_compact -> list_entries. In data_dir=None mode that read
    # must carry workspace_root or the store raises SessionNotFoundError and the
    # run dies mid-reply.
    service = _workspace_aware_service(tmp_path)
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
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

    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "hello " * 20}],
        stream=False,
        workspace_root=tmp_path,
    )
    result = await runtime.run(
        session.session_id,
        [{"type": "text", "text": "follow-up " * 20}],
        stream=False,
        workspace_root=tmp_path,
    )

    # Run completed (no crash), and compaction landed on disk + replays.
    assert result.messages[0].content == "ack"
    compactions = [
        event
        for event in manager.list_entries(
            session.session_id, workspace_root=tmp_path
        )
        if isinstance(event, CompactionEntry)
    ]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.THRESHOLD.value
    replayed = manager.list_turn_messages(
        session.session_id, workspace_root=tmp_path
    )
    assert replayed
    assert any("summary" in (m.content or "").lower() for m in replayed)


async def test_threshold_compaction_falls_back_when_summary_model_fails(
    tmp_path: Path,
) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "hello " * 20}], stream=False
    )
    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "follow-up " * 20}], stream=False
    )

    assert result.messages[0].content == "ack-after-fallback"
    compactions = [
        event
        for event in manager.list_entries(session.session_id)
        if isinstance(event, CompactionEntry)
    ]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.THRESHOLD.value
    # Summary model fails in this test → CompactionSummarizer falls back to _fallback_summary().
    assert "Session continuity maintained" in compactions[-1].summary
