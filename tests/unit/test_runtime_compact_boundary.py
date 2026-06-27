"""Tests for runtime compact_boundary writing when consuming compact summary msg.

Exit criterion 4: runtime 消费 summary msg 时正确写 compact_boundary.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.agent.compaction.types import CompactionSettings
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
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


def _make_workspace_session(manager: SessionManager, tmp_path: Path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(exist_ok=True)
    return manager.create_session(workspace_root=workspace_root.resolve())


async def test_runtime_writes_compact_boundary_when_consuming_summary_msg(
    tmp_path: Path,
) -> None:
    """Exit criterion 4: runtime 消费 summary msg 时正确写 compact_boundary."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)

    # Pre-populate session with enough history to trigger compact
    long_content = "x" * 800
    for i in range(10):
        msg = Message(
            message_id=f"pre_msg_{i}",
            role="user" if i % 2 == 0 else "assistant",
            content=long_content,
        )
        manager.append_turn_message(
            session.session_id,
            turn_id="turn_pre",
            role=msg.role,
            content=msg.content,
            message_id=msg.message_id,
        )
    manager.writer.flush()

    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=_FakeLLMClient(content="after-compact"),
        model="mock-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
    )
    # Replace loop's planner/summarizer with fakes
    runtime._loop = AgentRuntime(
        session_manager=manager,
        llm_client=_FakeLLMClient(content="after-compact"),
        model="mock-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
    )._loop
    # Manually inject fakes into the loop
    from agent.core.agent.loop import AgentLoop

    loop = AgentLoop(
        llm_client=_FakeLLMClient(content="after-compact"),
        model="mock-model",
        compaction_settings=CompactionSettings(
            enabled=True, context_window=100, reserve_tokens=10
        ),
        compaction_planner=_FakeCompactionPlanner(),
        compaction_summarizer=_FakeCompactionSummarizer(),
        session_manager=manager,
    )
    runtime._loop = loop

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "trigger"}], stream=False
    )
    manager.writer.flush()

    # Check JSONL entries for compact_boundary
    entries = manager.list_entries(session.session_id)
    # list_entries converts compact_boundary lines into CompactionEntry objects
    from agent.core.session.entries import CompactionEntry

    compact_boundaries = [e for e in entries if isinstance(e, CompactionEntry)]
    assert len(compact_boundaries) == 1, (
        f"Expected 1 compact_boundary, got {len(compact_boundaries)}"
    )
    boundary = compact_boundaries[0]
    assert boundary.data.get("reason") == "threshold"
