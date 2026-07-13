import asyncio
from pathlib import Path

import pytest

from agent.core.session.conversation import ConversationSession
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
from agent.core.types import TurnResult


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
