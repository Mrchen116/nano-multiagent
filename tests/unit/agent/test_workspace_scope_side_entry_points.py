"""Workspace scope regressions for non-main turn entry points."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.core.session.types import SessionRef
from tests.unit.agent._workspace_scope_support import (
    allow_all,
    kernel,
    run_turn_and_collect,
    write_scope_config,
    write_skill,
)


class _EntryPointScopeLLM:
    """Drive slash-skill and child-agent entry points through real turns."""

    def __init__(self) -> None:
        self.user_texts: list[str] = []

    def generate(self, request: Any):  # noqa: ANN201
        user_text = next(
            (
                str(message.content)
                for message in reversed(request.messages)
                if getattr(message, "role", None) == "user"
            ),
            "",
        )
        self.user_texts.append(user_text)
        if getattr(request.messages[-1], "role", None) == "tool":
            return self._stop()
        if user_text.startswith("launch child"):
            return self._launch_child()
        if user_text.startswith("child scope"):
            return self._run_child_extension()
        return self._stop()

    async def _launch_child(self):
        yield LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(
                    call_id="launch-child",
                    name="agent",
                    arguments={
                        "description": "Run scoped child",
                        "prompt": "child scope",
                        "run_in_background": False,
                    },
                ),
            ),
            finish_reason=None,
        )
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")

    async def _run_child_extension(self):
        yield LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(
                    call_id="child-extension",
                    name="scope_probe_child",
                    arguments={},
                ),
            ),
            finish_reason=None,
        )
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")

    async def _stop(self):
        yield LLMMessage(role="assistant", content="done", finish_reason="stop")


class _CompactionSummary:
    async def summarize(self, **_kwargs: object) -> str:
        return "scope compaction summary"


@pytest.mark.asyncio
async def test_scope_is_preserved_by_slash_skill_subagent_and_compaction(
    tmp_path: Path,
) -> None:
    """Every side entry point keeps the originating custom workspace scope."""

    workspace_a = tmp_path / "skills-a"
    workspace_b = tmp_path / "skills-b"
    child_workspace = tmp_path / "child"
    write_skill(
        workspace_a,
        ".consumer",
        name="scope-a",
        marker="scope-a skill content",
    )
    write_skill(
        workspace_b,
        ".consumer",
        name="scope-b",
        marker="scope-b skill content",
    )
    write_scope_config(child_workspace, ".consumer", marker="child")
    llm = _EntryPointScopeLLM()
    live_kernel = kernel(
        tmp_path,
        workspace_config_dirname=".consumer",
        can_use_tool=allow_all,
        _llm_client_override=llm,
    )
    try:
        session_a, session_b, parent = await asyncio.gather(
            live_kernel.create_session(workspace_root=workspace_a),
            live_kernel.create_session(workspace_root=workspace_b),
            live_kernel.create_session(workspace_root=child_workspace),
        )
        slash_events_a, slash_events_b = await asyncio.gather(
            run_turn_and_collect(
                live_kernel, session_a.session_id, workspace_a, "/skill:scope-a"
            ),
            run_turn_and_collect(
                live_kernel, session_b.session_id, workspace_b, "/skill:scope-b"
            ),
        )
        parent_events = await run_turn_and_collect(
            live_kernel, parent.session_id, child_workspace, "launch child"
        )

        live_kernel._c.engine_services._compaction_summarizer = _CompactionSummary()  # noqa: SLF001
        compacted = await live_kernel.compact(
            session_a.session_id,
            workspace_root=workspace_a,
            idempotency_key="scope-compaction",
        )
        transcript_a = live_kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session_a.session_id, workspace_root=workspace_a)
        )._transcript  # noqa: SLF001
        transcript_b = live_kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session_b.session_id, workspace_root=workspace_b)
        )._transcript  # noqa: SLF001
        messages_a = [str(message.content) for message in transcript_a.load().messages]
        messages_b = [str(message.content) for message in transcript_b.load().messages]
        child_ref = live_kernel._c.directory.find_by_metadata(  # noqa: SLF001
            workspace_root=child_workspace,
            parent_session_id=parent.session_id,
            query={"kind": "subagent"},
        )
        assert child_ref is not None
        child_messages = [
            (message.role, str(message.content))
            for message in live_kernel._c.directory.open(child_ref)
            ._transcript.load()
            .messages  # noqa: SLF001
        ]
    finally:
        live_kernel.close()

    assert compacted is not None
    slash_a_results = [
        event for event in slash_events_a if event.get("event") == "tool_end"
    ]
    slash_b_results = [
        event for event in slash_events_b if event.get("event") == "tool_end"
    ]
    assert any(event.get("name") == "skill_view" for event in slash_a_results)
    assert any(event.get("name") == "skill_view" for event in slash_b_results)
    assert any(
        "system-reminder" in content and "scope-a skill content" in content
        for content in messages_a
    )
    assert not any(
        "system-reminder" in content and "scope-b skill content" in content
        for content in messages_a
    )
    assert any("scope-b skill content" in content for content in messages_b)
    assert not any("scope-a skill content" in content for content in messages_b)
    assert any(
        event.get("event") == "tool_end" and event.get("name") == "agent"
        for event in parent_events
    )
    assert any(
        role == "tool" and "tool-child" in content for role, content in child_messages
    )
    assert "child scope-hook-child" in llm.user_texts
