import asyncio
from pathlib import Path

import pytest

from agent.core.errors import CompactionError
from agent.core.agent.runtime import AgentEngine
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.conversation import ConversationSession
from agent.core.session.directory import SessionDirectory
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.transcript import JsonlTranscript
from agent.core.session.types import (
    ConversationClosed,
    ExternalMessage,
    NewSession,
    PromptSlotSeed,
    PromptSlotText,
    SessionRef,
    TurnRequest,
)
from agent.core.types import Message, TokenUsage, ToolCall, TurnResult


class _BlockingEngine:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.histories: list[tuple[str, ...]] = []

    async def execute_turn(self, state, request: TurnRequest) -> TurnResult:
        self.calls += 1
        self.histories.append(tuple(message.content for message in state.history))
        self.started.set()
        await self.release.wait()
        return TurnResult(
            session_id=state.ref.session_id,
            turn_id=f"turn_{self.calls}",
            messages=(),
            completed=True,
            stop_reason="end_turn",
        )


class _EchoLLM:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        self.requests.append(request)
        yield LLMMessage(role="assistant", content="pong")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


class _PartialBlockingEngine(_BlockingEngine):
    async def execute_turn(self, state, request: TurnRequest) -> TurnResult:
        state.partial_turn_id = "turn_partial"
        state.partial_messages = [
            Message(message_id="msg_partial", role="assistant", content="partial")
        ]
        state.partial_tool_calls = (
            ToolCall(call_id="call_partial", name="read", arguments={}),
        )
        state.partial_usage = TokenUsage(
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )
        return await super().execute_turn(state, request)


class _FailureTrackerEngine:
    def __init__(self) -> None:
        self.trackers = []

    async def execute_turn(self, state, request: TurnRequest) -> TurnResult:
        tracker = state.automatic_compaction_failures
        self.trackers.append(tracker)
        failures = tracker.record_summary_failure()
        if failures >= 3:
            raise CompactionError(
                trigger="threshold",
                failure_kind="summary",
                consecutive_failures=failures,
            )
        return TurnResult(
            session_id=state.ref.session_id,
            turn_id=f"turn_{len(self.trackers)}",
            messages=(),
            completed=True,
            stop_reason="completed",
        )


def _conversation(
    tmp_path: Path,
    *,
    engine: _BlockingEngine | None = None,
    prompt_seed: PromptSlotSeed | None = None,
) -> tuple[ConversationSession, JsonlSessionFiles, _BlockingEngine]:
    files = JsonlSessionFiles(data_dir=tmp_path / "data")
    writer = JsonlWriter()
    ref = SessionRef(session_id="sess_conversation", workspace_root=tmp_path)
    transcript = JsonlTranscript.create(
        ref=ref,
        spec=NewSession(
            workspace_root=tmp_path,
            prompt_seed=prompt_seed or PromptSlotSeed(),
        ),
        files=files,
        writer=writer,
    )
    selected_engine = engine or _BlockingEngine()
    return (
        ConversationSession(
            ref=ref,
            transcript=transcript,
            engine=selected_engine,
        ),
        files,
        selected_engine,
    )


@pytest.mark.asyncio
async def test_turns_are_serialized_and_cold_load_rehydrates_prompt_seed(
    tmp_path: Path,
) -> None:
    seed = PromptSlotSeed(
        head=(PromptSlotText(name="pa.identity", text="You are Nano."),)
    )
    session, _files, engine = _conversation(tmp_path, prompt_seed=seed)

    first = asyncio.create_task(
        session.submit_turn(TurnRequest(parts=({"type": "text", "text": "one"},)))
    )
    await engine.started.wait()
    second = asyncio.create_task(
        session.submit_turn(TurnRequest(parts=({"type": "text", "text": "two"},)))
    )
    await asyncio.sleep(0)

    assert engine.calls == 1
    assert session.prompt_seed == seed
    engine.release.set()
    await asyncio.gather(first, second)
    assert engine.calls == 2


@pytest.mark.asyncio
async def test_external_append_can_commit_while_model_turn_is_active(
    tmp_path: Path,
) -> None:
    session, _files, engine = _conversation(tmp_path)
    active = asyncio.create_task(
        session.submit_turn(TurnRequest(parts=({"type": "text", "text": "run"},)))
    )
    await engine.started.wait()

    result = await asyncio.to_thread(
        session.append_external,
        ExternalMessage(
            role="user",
            content="scheduled awareness",
            message_id="msg_awareness",
        ),
    )

    assert result.created is True
    assert session.external_epoch == 1
    engine.release.set()
    await active
    assert [message.content for message in session.history_snapshot()] == [
        "scheduled awareness"
    ]


@pytest.mark.asyncio
async def test_active_external_append_preserves_partial_turn_snapshot(
    tmp_path: Path,
) -> None:
    engine = _PartialBlockingEngine()
    session, _files, _engine = _conversation(tmp_path, engine=engine)
    active = asyncio.create_task(
        session.submit_turn(TurnRequest(parts=({"type": "text", "text": "run"},)))
    )
    await engine.started.wait()
    before = session.partial_turn_result()
    assert before is not None

    await asyncio.to_thread(
        session.append_external,
        ExternalMessage(role="user", content="external", message_id="msg_external"),
    )

    after = session.partial_turn_result()
    assert after is not None
    assert [message.content for message in after.messages] == ["partial"]
    assert after.usage == TokenUsage(11, 7, 18)
    assert [tool.name for tool in after.tool_calls] == ["read"]
    engine.release.set()
    await active


@pytest.mark.asyncio
async def test_external_append_between_cold_load_and_publish_stays_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, _files, engine = _conversation(tmp_path)
    transcript = session._transcript  # type: ignore[attr-defined]
    original_load = transcript.load
    injected = False

    def _load_then_append():  # noqa: ANN202
        nonlocal injected
        loaded = original_load()
        if not injected:
            injected = True
            transcript.append_external(
                ExternalMessage(
                    role="user",
                    content="during-cold-load",
                    message_id="msg_during_load",
                )
            )
        return loaded

    monkeypatch.setattr(transcript, "load", _load_then_append)

    first = asyncio.create_task(
        session.submit_turn(TurnRequest(parts=({"type": "text", "text": "first"},)))
    )
    await engine.started.wait()
    engine.release.set()
    await first
    await session.submit_turn(TurnRequest(parts=({"type": "text", "text": "second"},)))

    assert "during-cold-load" in engine.histories[-1]


@pytest.mark.asyncio
async def test_automatic_compaction_failures_survive_payload_reload_and_eviction(
    tmp_path: Path,
) -> None:
    engine = _FailureTrackerEngine()
    session, _files, _selected = _conversation(tmp_path, engine=engine)

    await session.submit_turn(TurnRequest(parts=({"type": "text", "text": "one"},)))
    session.append_external(
        ExternalMessage(role="user", content="external", message_id="external-1")
    )
    await session.submit_turn(TurnRequest(parts=({"type": "text", "text": "two"},)))
    assert session.try_evict_payload() is True
    with pytest.raises(CompactionError):
        await session.submit_turn(
            TurnRequest(parts=({"type": "text", "text": "three"},))
        )

    assert engine.trackers[0] is engine.trackers[1] is engine.trackers[2]
    assert engine.trackers[-1].consecutive_failures == 3


@pytest.mark.asyncio
async def test_close_drains_admitted_turn_then_rejects_new_operations(
    tmp_path: Path,
) -> None:
    session, _files, engine = _conversation(tmp_path)
    active = asyncio.create_task(
        session.submit_turn(TurnRequest(parts=({"type": "text", "text": "run"},)))
    )
    await engine.started.wait()

    closing = asyncio.create_task(session.close())
    await asyncio.sleep(0.01)
    assert not closing.done()
    with pytest.raises(ConversationClosed):
        session.append_external(ExternalMessage(role="user", content="too late"))

    engine.release.set()
    await active
    await asyncio.wait_for(closing, timeout=1)
    with pytest.raises(ConversationClosed):
        await session.submit_turn(
            TurnRequest(parts=({"type": "text", "text": "closed"},))
        )


@pytest.mark.asyncio
async def test_real_engine_turn_persists_and_replays_followup_context(
    tmp_path: Path,
) -> None:
    files = JsonlSessionFiles(data_dir=tmp_path / "data")
    writer = JsonlWriter()
    ref = SessionRef(session_id="sess_engine", workspace_root=tmp_path)
    transcript = JsonlTranscript.create(
        ref=ref,
        spec=NewSession(workspace_root=tmp_path),
        files=files,
        writer=writer,
    )
    llm = _EchoLLM()
    session = ConversationSession(
        ref=ref,
        transcript=transcript,
        engine=AgentEngine(llm_client=llm, model="mock-model"),
    )

    first = await session.submit_turn(
        TurnRequest(parts=({"type": "text", "text": "first"},))
    )
    second = await session.submit_turn(
        TurnRequest(parts=({"type": "text", "text": "second"},))
    )

    assert first.messages[-1].content == "pong"
    assert second.messages[-1].content == "pong"
    assert [message.role for message in llm.requests[-1].messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert [message.content for message in transcript.load().messages] == [
        "first",
        "pong",
        "second",
        "pong",
    ]


@pytest.mark.asyncio
async def test_fork_restamps_history_and_preserves_internal_prompt_seed(
    tmp_path: Path,
) -> None:
    files = JsonlSessionFiles(data_dir=tmp_path / "data")
    writer = JsonlWriter()
    seed = PromptSlotSeed(
        body=(PromptSlotText(name="pa.guidance", text="Keep helping."),)
    )
    directory = SessionDirectory(
        files=files,
        writer=writer,
        conversation_factory=lambda ref, transcript: ConversationSession(
            ref=ref,
            transcript=transcript,
            engine=_BlockingEngine(),
        ),
    )
    source = directory.create(NewSession(workspace_root=tmp_path, prompt_seed=seed))
    source.append_external(
        ExternalMessage(role="user", content="question", message_id="msg_user")
    )
    source.append_external(
        ExternalMessage(role="assistant", content="answer", message_id="msg_assistant")
    )

    forked, mapping = await source.fork(up_to="msg_assistant")
    target = directory.open(
        SessionRef(session_id=forked.session_id, workspace_root=tmp_path)
    )
    loaded = await target.capture_fork(up_to=None)

    assert mapping.keys() == {"msg_user", "msg_assistant"}
    assert [message.content for message in loaded.messages] == ["question", "answer"]
    assert loaded.messages[0].message_id == mapping["msg_user"]
    assert loaded.messages[1].message_id == mapping["msg_assistant"]
    assert loaded.prompt_seed == seed
    assert all(not key.startswith("__nano_internal_") for key in forked.metadata)
