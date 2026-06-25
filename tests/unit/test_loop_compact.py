"""Tests for AgentLoop.run() internal compaction trigger.

Exit criteria from design.md:
1. loop 内 token 超限触发 compact
2. compact 后 iteration 继续
3. session history 不被修改
4. runtime 消费 summary msg 时正确写 compact_boundary
5. system prompt 在 compact 后不丢失
"""

from collections.abc import AsyncIterator

import pytest

from agent.core.agent.loop import AgentLoop
from agent.core.agent.prompting import build_system_prompt, estimate_llm_context_tokens
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState
from agent.core.agent.compaction.types import CompactionSettings
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)
from agent.core.types import Message


class _FakeLLMClient:
    """LLM client that yields assistant responses then stop."""

    def __init__(self, content: str = "pong") -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._content = content

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        response = LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=self._content),
            finish_reason="stop",
        )
        yield response.message
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


class _FakeSessionManager:
    """Session manager that returns synthetic entries for compaction planning."""

    def __init__(self, history_messages: tuple[Message, ...]) -> None:
        self._history = history_messages

    def list_entries(self, session_id: str):
        from agent.core.session.entries import (
            SessionEntry,
            SessionEntryKind,
            new_turn_appended_entry,
        )

        entries = []
        for msg in self._history:
            entries.append(
                new_turn_appended_entry(
                    session_id=session_id,
                    turn_id="turn_1",
                    role=msg.role,
                    content=msg.content,
                    message_id=msg.message_id,
                )
            )
        return tuple(entries)


class _FakeCompactionPlanner:
    """Planner that always returns a plan dropping all events."""

    def plan(self, *, events, reason):
        from agent.core.agent.compaction.types import CompactionPlan
        from agent.core.session.entries import SessionEntry, SessionEntryKind

        turn_events = tuple(
            e
            for e in events
            if isinstance(e, SessionEntry) and e.kind is SessionEntryKind.TURN_APPENDED
        )
        if not turn_events:
            return None
        return CompactionPlan(
            reason=reason,
            first_kept_event_id="",
            dropped_events=turn_events,
            kept_events=(),
        )


class _FakeCompactionSummarizer:
    """Summarizer that returns a fixed summary."""

    async def summarize(
        self, *, session_id, system_prompt, dropped_messages, model_override=None
    ):
        return "Compact summary: context was too long."


def _make_state(
    *,
    session_id: str = "sess-compact",
    user_text: str = "ping",
    history_messages: tuple[Message, ...] = (),
) -> AgentState:
    return AgentState(
        session_id=session_id,
        turn_id="turn-compact",
        turn_count=1,
        history_messages=history_messages,
        input_parts=(),
        user_text=user_text,
    )


async def _run_loop(loop: AgentLoop, state: AgentState):
    """Consume AgentLoop async generator and build TurnResult."""
    messages = []
    async for msg in loop.run(state):
        messages.append(msg)
    return build_turn_result(state.session_id, state.turn_id, messages)


# ---------------------------------------------------------------------------
# C1 tests (Red) — these will fail until implementation is added
# ---------------------------------------------------------------------------


async def test_loop_triggers_compact_when_token_threshold_exceeded() -> None:
    """Exit criterion 1: loop 内 token 超限触发 compact."""
    long_content = "x" * 800  # ~100 tokens
    history = tuple(
        Message(
            message_id=f"msg_{i}",
            role="user" if i % 2 == 0 else "assistant",
            content=long_content,
        )
        for i in range(10)
    )
    llm = _FakeLLMClient()
    loop = AgentLoop(
        llm_client=llm,
        model="test-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
        compaction_planner=_FakeCompactionPlanner(),
        compaction_summarizer=_FakeCompactionSummarizer(),
        session_manager=_FakeSessionManager(history),
    )
    state = _make_state(history_messages=history, user_text="trigger")

    # Collect raw messages from loop (not TurnResult which filters assistant-only)
    raw_messages = []
    async for msg in loop.run(state):
        raw_messages.append(msg)

    # Compact should have triggered: we should see a compact summary message
    compact_msgs = [
        m for m in raw_messages if getattr(m, "metadata", {}).get("is_compact_summary")
    ]
    assert len(compact_msgs) == 1, (
        f"Expected 1 compact summary, got {len(compact_msgs)}"
    )


async def test_loop_continues_iteration_after_compact() -> None:
    """Exit criterion 2: compact 后 iteration 继续."""
    long_content = "x" * 800
    history = tuple(
        Message(
            message_id=f"msg_{i}",
            role="user" if i % 2 == 0 else "assistant",
            content=long_content,
        )
        for i in range(10)
    )
    llm = _FakeLLMClient(content="after-compact")
    loop = AgentLoop(
        llm_client=llm,
        model="test-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
        compaction_planner=_FakeCompactionPlanner(),
        compaction_summarizer=_FakeCompactionSummarizer(),
        session_manager=_FakeSessionManager(history),
    )
    state = _make_state(history_messages=history, user_text="trigger")

    result = await _run_loop(loop, state)

    # After compact, the loop should still produce the assistant response
    assert result.completed is True
    assert result.messages[-1].content == "after-compact"


async def test_loop_compact_does_not_modify_session_history() -> None:
    """Exit criterion 3: session history 不被修改.

    The loop receives history_messages as input; compact should only
    modify the internal llm_messages, not the caller's history.
    """
    long_content = "x" * 800
    original_history = tuple(
        Message(
            message_id=f"msg_{i}",
            role="user" if i % 2 == 0 else "assistant",
            content=long_content,
        )
        for i in range(10)
    )
    llm = _FakeLLMClient()
    loop = AgentLoop(
        llm_client=llm,
        model="test-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
        compaction_planner=_FakeCompactionPlanner(),
        compaction_summarizer=_FakeCompactionSummarizer(),
        session_manager=_FakeSessionManager(original_history),
    )
    state = _make_state(history_messages=original_history, user_text="trigger")

    await _run_loop(loop, state)

    # state.history_messages should be unchanged
    assert state.history_messages == original_history
    assert len(state.history_messages) == 10


async def test_loop_preserves_system_prompt_after_compact() -> None:
    """Exit criterion 5: system prompt 在 compact 后不丢失.

    The LLM request after compact must still contain the system prompt.
    """
    long_content = "x" * 800
    history = tuple(
        Message(
            message_id=f"msg_{i}",
            role="user" if i % 2 == 0 else "assistant",
            content=long_content,
        )
        for i in range(10)
    )
    llm = _FakeLLMClient()
    system_prompt = "You are a helpful assistant."
    loop = AgentLoop(
        llm_client=llm,
        model="test-model",
        system_prompt=system_prompt,
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
        compaction_planner=_FakeCompactionPlanner(),
        compaction_summarizer=_FakeCompactionSummarizer(),
        session_manager=_FakeSessionManager(history),
    )
    state = _make_state(history_messages=history, user_text="trigger")

    await _run_loop(loop, state)

    # All LLM requests must have system prompt as first message
    for req in llm.requests:
        assert req.messages[0].role == "system"
        assert system_prompt in req.messages[0].content


async def test_loop_fires_on_compaction_callback_with_session_id() -> None:
    """compaction 触发后 on_compaction callback 被调用，携带正确 session_id。

    Verifies the closed loop: _maybe_compact success → _on_compaction_callback(session_id),
    which lets AgentRuntime._invalidate_memory_snapshot drop the stale cache entry so the
    next turn re-reads memory from disk.
    """
    long_content = "x" * 800
    session_id = "sess-callback-check"
    history = tuple(
        Message(
            message_id=f"msg_{i}",
            role="user" if i % 2 == 0 else "assistant",
            content=long_content,
        )
        for i in range(10)
    )
    llm = _FakeLLMClient()

    fired_with: list[str] = []

    def on_compaction(sid: str) -> None:
        fired_with.append(sid)

    loop = AgentLoop(
        llm_client=llm,
        model="test-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
        compaction_planner=_FakeCompactionPlanner(),
        compaction_summarizer=_FakeCompactionSummarizer(),
        session_manager=_FakeSessionManager(history),
        on_compaction=on_compaction,
    )
    state = _make_state(
        session_id=session_id, history_messages=history, user_text="trigger"
    )

    await _run_loop(loop, state)

    assert len(fired_with) == 1, f"Expected callback called once, got {fired_with}"
    assert fired_with[0] == session_id, (
        f"Expected session_id={session_id!r}, got {fired_with[0]!r}"
    )


# ---------------------------------------------------------------------------
# bugfix-412 #103: real-token-driven compaction trigger
# ---------------------------------------------------------------------------


def test_estimate_counts_tool_call_arguments() -> None:
    """estimate_llm_context_tokens must account for assistant tool_calls.

    Previously only msg.content was counted; tool_call name + arguments were
    omitted, badly undershooting tool-heavy turns.
    """
    no_calls = [LLMMessage(role="assistant", content="")]
    with_calls = [
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(
                    call_id="c1",
                    name="read_file",
                    arguments={
                        "path": "/some/very/long/path/to/a/source/file.py",
                        "limit": 2000,
                        "offset": 0,
                    },
                ),
            ),
        )
    ]

    assert estimate_llm_context_tokens(with_calls) > estimate_llm_context_tokens(
        no_calls
    )


def test_should_compact_prefers_real_prompt_tokens_over_estimate() -> None:
    """When a real prompt_tokens value is known, it drives the threshold check.

    The char estimate of these tiny messages is far below threshold, so the
    decision must follow real_prompt_tokens, not the estimate.
    """
    loop = AgentLoop(
        llm_client=_FakeLLMClient(),
        model="test-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=200_000, reserve_tokens=4096
        ),
    )
    tiny_msgs = [LLMMessage(role="user", content="short")]

    # No real value → tiny estimate → below threshold → no compaction.
    assert loop._should_compact(tiny_msgs, "") is False
    # Real value above threshold (195_904) → compact, despite tiny estimate.
    assert loop._should_compact(tiny_msgs, "", real_prompt_tokens=199_000) is True
    # Real value below threshold → no compaction.
    assert loop._should_compact(tiny_msgs, "", real_prompt_tokens=1_000) is False


class _RecordingFork:
    """Fork stub that records the model_override it receives (bugfix-429 fix-r1 #2)."""

    def __init__(self) -> None:
        self.model_overrides: list[str | None] = []

    async def execute(self, *, state, model_override=None, **kwargs):  # noqa: ANN001
        self.model_overrides.append(model_override)
        return build_turn_result(
            state.session_id,
            state.turn_id,
            [Message(message_id="m", role="assistant", content="a summary")],
        )


async def test_compaction_summarizer_forwards_run_model_to_fork() -> None:
    """bugfix-429 fix-r1 #2: the compaction summarizer must run the side-chain on
    the current run's model (passed as model_override), not the build-time default."""
    from agent.core.agent.compaction.summarizer import CompactionSummarizer

    fork = _RecordingFork()
    summarizer = CompactionSummarizer(fork=fork)

    await summarizer.summarize(
        session_id="sess_x",
        system_prompt="sys",
        dropped_messages=[Message(message_id="d", role="user", content="old")],
        model_override="agent-selected-model",
    )

    assert fork.model_overrides == ["agent-selected-model"]


def _init_per_model_window_registry() -> None:
    """注册一个带 context_window 的模型目录（feat-436）。conftest autouse 在下个测试前复原。"""
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )
    from agent.core.llm.model_registry import _reset_for_tests, init_model_registry

    _reset_for_tests()
    init_model_registry(
        LLMConfigPayload(
            default_model="big-window",
            providers=(
                LLMProviderPayload(
                    name="anthropic",
                    base_url=None,
                    models=(
                        LLMModelPayload(name="big-window", context_window=1_000_000),
                        LLMModelPayload(name="no-window"),
                    ),
                ),
            ),
        )
    )


def test_should_compact_threshold_moves_with_per_model_window() -> None:
    """feat-436: 同样 token 量下，大窗口模型不压缩、回退默认窗口的模型触发压缩。"""
    _init_per_model_window_registry()
    loop = AgentLoop(
        llm_client=_FakeLLMClient(),
        model="big-window",
        compaction_settings=CompactionSettings(enabled=True, reserve_tokens=20_480),
    )
    msgs = [LLMMessage(role="user", content="x")]
    tokens = 190_000  # < 1_000_000-20_480，但 > 200_000-20_480 (=179_520)

    # big-window（1M）：远未到阈值 → 不压缩
    assert loop._should_compact(msgs, "", tokens, active_model="big-window") is False
    # no-window（回退 CompactionSettings 默认 200k）：超过阈值 → 压缩
    assert loop._should_compact(msgs, "", tokens, active_model="no-window") is True


def test_should_compact_falls_back_to_default_window_when_registry_empty() -> None:
    """注册表未初始化时按全局默认窗口判定，不抛错（fork / 单测路径兼容）。"""
    from agent.core.llm.model_registry import _reset_for_tests

    _reset_for_tests()
    loop = AgentLoop(
        llm_client=_FakeLLMClient(),
        model="anything",
        compaction_settings=CompactionSettings(enabled=True, reserve_tokens=20_480),
    )
    msgs = [LLMMessage(role="user", content="x")]
    # 默认 200k - 20480 = 179_520 阈值
    assert loop._should_compact(msgs, "", 179_520, active_model="anything") is True
    assert loop._should_compact(msgs, "", 100_000, active_model="anything") is False


def test_compaction_reserve_tokens_default_is_20480() -> None:
    """feat-436: 全局 reserve 默认从 4096 提到 20480。"""
    assert CompactionSettings().reserve_tokens == 20_480
