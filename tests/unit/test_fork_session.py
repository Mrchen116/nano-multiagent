"""M3: Session fork creates independent copy with re-stamped message history."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
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
            assert msg.parent_message_id in fork_uuids, (
                "parent_uuid must point within fork"
            )

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


def _append_chain_turn(
    manager: SessionManager,
    session_id: str,
    *,
    role: str,
    content: str,
    message_id: str,
    parent_uuid: str | None,
) -> str:
    """Append one linear turn (parent → this) and return its uuid."""
    manager.append_turn_message(
        session_id,
        turn_id="t",
        role=role,
        content=content,
        message_id=message_id,
        parent_uuid=parent_uuid,
    )
    return message_id


# ---------------------------------------------------------------------------
# feat-445-M1 R2: fork_session(up_to=M) — 分支 ≡ 源在 M 的视图（含源当时压缩态）
# ---------------------------------------------------------------------------


async def test_fork_up_to_uncompacted_keeps_all_turns_through_M(tmp_path: Path) -> None:
    """③ 源未压缩 → 分支 = 到 M 为止的全部 turn（M 之后不带）。"""
    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id

    p = _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    p = _append_chain_turn(
        manager, src, role="assistant", content="a1", message_id="a1", parent_uuid=p
    )
    p = _append_chain_turn(
        manager, src, role="user", content="u2", message_id="u2", parent_uuid=p
    )
    p = _append_chain_turn(
        manager, src, role="assistant", content="a2", message_id="a2", parent_uuid=p
    )
    _append_chain_turn(
        manager, src, role="user", content="u3", message_id="u3", parent_uuid=p
    )
    manager.store.writer.flush()

    forked = await runtime.fork_session(src, up_to="a1")
    hist = runtime._session_histories[forked.session_id]

    assert [m.content for m in hist] == ["u1", "a1"], (
        f"fork to a1 must keep exactly [u1, a1] (M 之后不带), got {[m.content for m in hist]}"
    )


async def test_fork_up_to_after_boundary_is_summary_plus_kept(tmp_path: Path) -> None:
    """① 源已压缩、fork boundary 后消息 → 分支 = summary + boundary..M（不还原 compact 前全量）。"""
    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id

    # Pre-compaction turns
    p = _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    p = _append_chain_turn(
        manager, src, role="assistant", content="a1", message_id="a1", parent_uuid=p
    )
    p = _append_chain_turn(
        manager, src, role="user", content="u2", message_id="u2", parent_uuid=p
    )
    p = _append_chain_turn(
        manager, src, role="assistant", content="a2", message_id="a2", parent_uuid=p
    )
    # Compact: boundary + summary turn (parent = first_kept_event_id = a2)
    manager.append_compaction(src, first_kept_event_id="a2", summary="SUMMARY")
    manager.store.writer.flush()
    # The summary turn's uuid is generated internally; recover it from the file to chain onward.
    result_full = manager.load(src)
    summary_uuid = next(
        m.message_id for m in result_full.messages if m.content == "SUMMARY"
    )
    # Post-compaction turns chain off the summary
    p = _append_chain_turn(
        manager,
        src,
        role="user",
        content="u3",
        message_id="u3",
        parent_uuid=summary_uuid,
    )
    p = _append_chain_turn(
        manager, src, role="assistant", content="a3", message_id="a3", parent_uuid=p
    )
    p = _append_chain_turn(
        manager, src, role="user", content="u4", message_id="u4", parent_uuid=p
    )
    _append_chain_turn(
        manager, src, role="assistant", content="a4", message_id="a4", parent_uuid=p
    )
    manager.store.writer.flush()

    forked = await runtime.fork_session(src, up_to="a3")
    hist = runtime._session_histories[forked.session_id]

    # M=a3 is after the boundary → view = summary + (boundary..a3); pre-boundary u1/a1/u2/a2 NOT restored.
    assert [m.content for m in hist] == ["SUMMARY", "u3", "a3"], (
        f"fork to a3 (after boundary) must be summary+boundary..M, got {[m.content for m in hist]}"
    )


async def test_fork_up_to_before_boundary_ignores_later_boundary(
    tmp_path: Path,
) -> None:
    """② 源已压缩、fork boundary 前老消息 → 只应用 M 之前的 boundary（此处无）→ 到 M 全部 turn。"""
    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id

    p = _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    p = _append_chain_turn(
        manager, src, role="assistant", content="a1", message_id="a1", parent_uuid=p
    )
    p = _append_chain_turn(
        manager, src, role="user", content="u2", message_id="u2", parent_uuid=p
    )
    p = _append_chain_turn(
        manager, src, role="assistant", content="a2", message_id="a2", parent_uuid=p
    )
    manager.append_compaction(src, first_kept_event_id="a2", summary="SUMMARY")
    manager.store.writer.flush()
    summary_uuid = next(
        m.message_id for m in manager.load(src).messages if m.content == "SUMMARY"
    )
    _append_chain_turn(
        manager,
        src,
        role="user",
        content="u3",
        message_id="u3",
        parent_uuid=summary_uuid,
    )
    manager.store.writer.flush()

    # Fork to a1, which lies BEFORE the boundary → the boundary (written after a1) is
    # truncated away → view = all turns up to a1, no summary.
    forked = await runtime.fork_session(src, up_to="a1")
    hist = runtime._session_histories[forked.session_id]

    assert [m.content for m in hist] == ["u1", "a1"], (
        f"fork to a1 (before boundary) must ignore the later boundary, got {[m.content for m in hist]}"
    )
    assert all(m.content != "SUMMARY" for m in hist), (
        "must not pull in a boundary after M"
    )


async def test_fork_up_to_unknown_message_id_raises(tmp_path: Path) -> None:
    """up_to 指向不存在的消息 → 大声失败，绝不静默回落（§0.2）。"""
    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id
    _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    manager.store.writer.flush()

    with pytest.raises(Exception):
        await runtime.fork_session(src, up_to="nonexistent-msg-id")


async def test_fork_up_to_new_session_independent_and_restamped(tmp_path: Path) -> None:
    """up_to fork 出的会话与源独立、UUID re-stamp、内容保真。"""
    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id
    p = _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    _append_chain_turn(
        manager, src, role="assistant", content="a1", message_id="a1", parent_uuid=p
    )
    manager.store.writer.flush()

    forked = await runtime.fork_session(src, up_to="a1")
    fork_id = forked.session_id
    assert fork_id != src
    assert forked.metadata.get("forked_from") == src

    # Persisted to its own JSONL, re-stamped (not source uuids)
    reloaded = manager.load(fork_id)
    assert [m.content for m in reloaded.messages] == ["u1", "a1"]
    assert all(m.message_id not in {"u1", "a1"} for m in reloaded.messages), (
        "must re-stamp"
    )


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


# ---------------------------------------------------------------------------
# feat-445-M2 R1: fork up_to 不阻塞事件循环 + 不长持 source_lock + role 守卫
# ---------------------------------------------------------------------------


async def test_fork_up_to_uses_async_flush_not_blocking(tmp_path: Path) -> None:
    """#1: up_to fork 前置 flush 必须用 async 版——绝不在事件循环线程上跑阻塞 flush()。

    flush_async 内部经 executor 工作线程调 flush（不阻塞 loop），那是允许的；本测专测
    「loop 线程上是否出现阻塞 flush」——回退到直接 flush() 会命中 loop 线程 → 红。
    """
    import asyncio
    import threading

    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id
    p = _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    _append_chain_turn(
        manager, src, role="assistant", content="a1", message_id="a1", parent_uuid=p
    )
    manager.store.writer.flush()  # real, get a1 on disk before we spy

    loop_thread = threading.get_ident()
    flush_async_calls = {"n": 0}
    sync_on_loop = {"n": 0}
    orig_flush = manager.store.writer.flush
    orig_async = manager.store.writer.flush_async

    def spy_flush(*a, **k):
        if threading.get_ident() == loop_thread:
            sync_on_loop["n"] += 1  # a blocking flush on the event-loop thread = bad
        return orig_flush(*a, **k)

    async def spy_async(*a, **k):
        flush_async_calls["n"] += 1
        return await orig_async(*a, **k)

    manager.store.writer.flush = spy_flush  # type: ignore[method-assign]
    manager.store.writer.flush_async = spy_async  # type: ignore[method-assign]

    await asyncio.wait_for(runtime.fork_session(src, up_to="a1"), timeout=3.0)
    assert sync_on_loop["n"] == 0, (
        "up_to fork must not block the event loop with sync flush()"
    )
    assert flush_async_calls["n"] >= 1, "up_to fork must flush via flush_async()"


async def test_fork_up_to_does_not_block_on_busy_source_lock(tmp_path: Path) -> None:
    """#2: 源 session 锁被活跃 run 持有时，up_to fork 仍须及时完成（该路径数据全来自磁盘，
    不依赖源内存、不写源 → 锁对它无正确性意义，绝不能阻塞在锁上 → 否则 agent 忙时 fork 必超时）。"""
    import asyncio

    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id
    p = _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    _append_chain_turn(
        manager, src, role="assistant", content="a1", message_id="a1", parent_uuid=p
    )
    manager.store.writer.flush()

    # Simulate a busy source session: an active run holds its lock the whole time.
    runtime._session_locks[src] = asyncio.Lock()
    async with runtime._session_locks[src]:
        forked = await asyncio.wait_for(
            runtime.fork_session(src, up_to="a1"), timeout=3.0
        )
    assert forked.session_id != src
    assert [m.content for m in runtime._session_histories[forked.session_id]] == [
        "u1",
        "a1",
    ]


async def test_fork_up_to_non_assistant_message_rejected(tmp_path: Path) -> None:
    """防御: up_to 命中非 assistant turn（如 user 消息）须显式报错，不静默 fork 错位。"""
    runtime = _make_runtime(tmp_path)
    manager = runtime._session_manager
    src = manager.create_session(workspace_root=tmp_path).session_id
    p = _append_chain_turn(
        manager, src, role="user", content="u1", message_id="u1", parent_uuid=None
    )
    _append_chain_turn(
        manager, src, role="assistant", content="a1", message_id="a1", parent_uuid=p
    )
    manager.store.writer.flush()

    with pytest.raises(Exception):
        await runtime.fork_session(src, up_to="u1")
