"""M246: runtime 将多 parts 列表中每个 part 作为独立 user message 注入 LLM history。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Mapping

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.session.models import Session
from agent.platform.persistence.session.service import SessionService


class _FakeLLMClient:
    """Records calls and returns a simple text response."""

    def __init__(self, response_text: str = "ok") -> None:
        self.calls: list[LLMGenerateRequest] = []
        self._response_text = response_text

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.calls.append(request)
        yield LLMMessage(role="assistant", content=self._response_text)
        yield LLMMessage(role="assistant", content="", finish_reason="end_turn")


def _make_session_manager(
    tmp_path: Path, *, workspace_root: str | None = None
) -> tuple[SessionManager, str]:
    """Create a session manager via SessionService and return (manager, session_id)."""
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    root = Path(workspace_root) if workspace_root else tmp_path
    session = service.create_session(workspace_root=root)
    return service.manager, session.session_id


async def test_single_part_creates_single_user_message_in_llm_history(
    tmp_path: Path,
) -> None:
    """单条 part（向后兼容路径）→ LLM history 末尾只有一条 user message。"""
    manager, session_id = _make_session_manager(tmp_path)
    llm = _FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(session_id, [{"type": "text", "text": "hello"}])

    assert len(llm.calls) == 1
    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[-1].content == "hello"


async def test_multiple_parts_become_independent_user_messages_in_llm_history(
    tmp_path: Path,
) -> None:
    """多条 parts → LLM history 中每条 part 对应一条独立 user message（而非 \n join）。"""
    manager, session_id = _make_session_manager(tmp_path)
    llm = _FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(
        session_id,
        [
            {"type": "text", "text": "[alice] hello"},
            {"type": "text", "text": "[bob] world"},
            {"type": "text", "text": "[charlie] @agent go"},
        ],
    )

    assert len(llm.calls) == 1
    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    # 3 parts → 3 independent user messages
    assert len(user_messages) == 3
    assert user_messages[0].content == "[alice] hello"
    assert user_messages[1].content == "[bob] world"
    assert user_messages[2].content == "[charlie] @agent go"


async def test_two_parts_become_two_user_messages(tmp_path: Path) -> None:
    """2 parts → 2 user messages in LLM history。"""
    manager, session_id = _make_session_manager(tmp_path)
    llm = _FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(
        session_id,
        [
            {"type": "text", "text": "[user-1] buffered message"},
            {"type": "text", "text": "[user-2] @agent respond"},
        ],
    )

    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    assert len(user_messages) == 2
    assert user_messages[0].content == "[user-1] buffered message"
    assert user_messages[1].content == "[user-2] @agent respond"


async def test_multiple_parts_not_newline_joined(tmp_path: Path) -> None:
    """多 parts 不能被 \n join 成一条 user message，而是分开为独立条目。"""
    manager, session_id = _make_session_manager(tmp_path)
    llm = _FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(
        session_id,
        [
            {"type": "text", "text": "part one"},
            {"type": "text", "text": "part two"},
        ],
    )

    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    # Must NOT be joined as "part one\npart two"
    assert not any(m.content == "part one\npart two" for m in user_messages)
    # Must be separate
    assert any(m.content == "part one" for m in user_messages)
    assert any(m.content == "part two" for m in user_messages)


async def test_single_part_user_text_unchanged_after_multi_turn(tmp_path: Path) -> None:
    """多轮对话中，单 part 的 user text 行为与之前完全一致。"""
    manager, session_id = _make_session_manager(tmp_path)
    llm = _FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(session_id, [{"type": "text", "text": "turn one"}])
    await runtime.run(session_id, [{"type": "text", "text": "turn two"}])

    # First call: 1 user message
    call1_user = [m for m in llm.calls[0].messages if m.role == "user"]
    assert len(call1_user) == 1
    assert call1_user[0].content == "turn one"

    # Second call: history has 2 user messages + 1 assistant, plus current user
    call2_user = [m for m in llm.calls[1].messages if m.role == "user"]
    assert call2_user[-1].content == "turn two"
