"""M3: Session fork creates independent copy with re-stamped message history."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.types import Message


class _EchoLLMClient:
    """LLM client that echoes user text as assistant response."""

    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        last_user_text = request.messages[-1].content
        response = LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{last_user_text}"),
            finish_reason="stop",
        )
        yield response.message
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


def _make_runtime(tmp_path: Path) -> AgentRuntime:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    return AgentRuntime(
        session_manager=manager,
        llm_client=_EchoLLMClient(),
        model="mock-model",
        repo_root=tmp_path,
    )


async def test_fork_session_creates_independent_copy(tmp_path: Path) -> None:
    """Fork creates a new session with copied history; changes to source do not affect fork."""
    runtime = _make_runtime(tmp_path)
    source = runtime._session_manager.create_session(workspace_root=tmp_path)
    source_id = source.session_id

    # Run two turns to build history
    await runtime.run(source_id, [{"type": "text", "text": "hello"}], stream=False)
    await runtime.run(source_id, [{"type": "text", "text": "world"}], stream=False)

    source_history = runtime._session_histories[source_id]
    assert len(source_history) >= 2  # user + assistant messages

    forked = await runtime.fork_session(source_id)
    fork_id = forked.session_id

    # Fork must be a different session
    assert fork_id != source_id
    # Fork metadata must record origin
    assert forked.metadata.get("forked_from") == source_id

    # Fork history must exist and match source length
    fork_history = runtime._session_histories[fork_id]
    assert len(fork_history) == len(source_history)

    # Content must match
    for src_msg, fork_msg in zip(source_history, fork_history):
        assert src_msg.role == fork_msg.role
        assert src_msg.content == fork_msg.content
        assert src_msg.tool_call_id == fork_msg.tool_call_id

    # UUIDs must be re-stamped (not shared with source)
    source_uuids = {m.message_id for m in source_history}
    fork_uuids = {m.message_id for m in fork_history}
    assert not source_uuids & fork_uuids, "fork must not reuse source message UUIDs"

    # Parent chain must be recalculated correctly
    for msg in fork_history:
        if msg.parent_message_id is not None:
            assert msg.parent_message_id in fork_uuids, "parent_uuid must point within fork"

    # History independence: run another turn on source
    await runtime.run(source_id, [{"type": "text", "text": "extra"}], stream=False)
    assert len(runtime._session_histories[source_id]) > len(fork_history)
    assert len(runtime._session_histories[fork_id]) == len(fork_history)


async def test_fork_session_from_jsonl_only_source(tmp_path: Path) -> None:
    """Fork works when source session is not in runtime memory (cold fork)."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    runtime = _make_runtime(tmp_path)

    # Create and populate source via manager directly (bypass runtime memory)
    source = manager.create_session(workspace_root=tmp_path)
    source_id = source.session_id
    manager.append_turn_message(
        source_id,
        turn_id="t1",
        role="user",
        content="hello",
        message_id="msg_user_1",
    )
    manager.append_turn_message(
        source_id,
        turn_id="t1",
        role="assistant",
        content="hi there",
        message_id="msg_assistant_1",
    )
    manager.store.writer.flush()

    # Ensure source is NOT in runtime memory
    assert source_id not in runtime._session_histories

    forked = await runtime.fork_session(source_id)
    fork_id = forked.session_id

    # Fork history should be loaded and copied
    fork_history = runtime._session_histories[fork_id]
    assert len(fork_history) == 2
    assert fork_history[0].role == "user"
    assert fork_history[0].content == "hello"
    assert fork_history[1].role == "assistant"
    assert fork_history[1].content == "hi there"


async def test_fork_empty_session(tmp_path: Path) -> None:
    """Forking a session with no history creates an empty new session."""
    runtime = _make_runtime(tmp_path)
    source = runtime._session_manager.create_session(workspace_root=tmp_path)
    source_id = source.session_id

    forked = await runtime.fork_session(source_id)
    fork_id = forked.session_id

    assert fork_id != source_id
    assert runtime._session_histories[fork_id] == []


async def test_fork_session_persists_to_jsonl(tmp_path: Path) -> None:
    """Forked session history must be persisted to its own JSONL file."""
    runtime = _make_runtime(tmp_path)
    source = runtime._session_manager.create_session(workspace_root=tmp_path)
    source_id = source.session_id

    manager = runtime._session_manager
    manager.append_turn_message(
        source_id,
        turn_id="t1",
        role="user",
        content="persist me",
        message_id="msg_user_persist",
    )
    manager.store.writer.flush()

    forked = await runtime.fork_session(source_id)
    fork_id = forked.session_id

    # Load fork from JSONL and verify
    result = manager.load(fork_id)
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert result.messages[0].content == "persist me"
    assert result.messages[0].message_id != "msg_user_persist"  # re-stamped


async def test_fork_preserves_reasoning_content_and_signature(tmp_path: Path) -> None:
    """Forking must carry reasoning_content / reasoning_signature on assistant messages.

    Regression (bugfix-375): _fork_locked rebuilt each Message from a hand-listed
    subset of fields and dropped reasoning_content / reasoning_signature. A forked
    thinking-enabled session (e.g. kimi K2.6) lost its <thinking> blocks, so the
    fork's next turn was rejected upstream with "reasoning_content is missing" and
    the forked session became unusable. Same brittle "manual field-by-field
    reconstruction" anti-pattern fixed in _strip_fork_conversation; this is the
    fork-path instance.
    """
    from agent.core.ids import make_message_id

    runtime = _make_runtime(tmp_path)
    source = runtime._session_manager.create_session(workspace_root=tmp_path)
    sid = source.session_id

    # One turn to populate configs/paths/history the way fork_session expects.
    await runtime.run(sid, [{"type": "text", "text": "hi"}], stream=False)

    # Inject an assistant message carrying thinking reasoning + signature.
    hist = runtime._session_histories[sid]
    reasoning_msg = Message(
        message_id=make_message_id(),
        role="assistant",
        content="answer",
        parent_message_id=hist[-1].message_id,
        reasoning_content="step-by-step chain of thought",
        reasoning_signature="sig-deadbeef-4340",
    )
    hist.append(reasoning_msg)

    forked = await runtime.fork_session(sid)
    fork_history = runtime._session_histories[forked.session_id]

    carried = [m for m in fork_history if m.reasoning_content is not None]
    assert len(carried) == 1, "forked history must retain the reasoning-bearing message"
    assert carried[0].reasoning_content == "step-by-step chain of thought"
    assert carried[0].reasoning_signature == "sig-deadbeef-4340"
