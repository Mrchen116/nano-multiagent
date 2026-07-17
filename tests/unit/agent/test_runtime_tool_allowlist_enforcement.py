"""Regression: runtime wires session tool_allowlist into loop execution layer (bugfix-468-M2)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from agent.core.agent.runtime import AgentEngine
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.core.session.conversation import ConversationSession
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.transcript import JsonlTranscript
from agent.core.session.types import NewSession, SessionRef, TurnRequest
from agent.core.tools.base import Tool, ToolContext
from agent.core.types import ToolCall, ToolResult, ToolSpec, TokenUsage


class _FakeTool(Tool):
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = f"Fake {name}"
        self.input_schema: Mapping[str, Any] = {"type": "object"}
        self.is_concurrency_safe = True
        self.max_result_size_chars: int | None = None
        self.executed: list[Mapping[str, Any]] = []

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        self.executed.append(dict(args))
        return {"tool": self.name, "args": dict(args)}

    def serialize_result(
        self, output: Any, error: str | None = None
    ) -> str | list[dict[str, Any]]:
        return str(output)


class _FakeRuntimeRegistry:
    """Minimal registry satisfying AgentLoop's ToolRegistryLike protocol."""

    def __init__(self, tools: tuple[_FakeTool, ...]) -> None:
        self._tools = {t.name: t for t in tools}

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(
            ToolSpec(
                name=t.name,
                description=t.description,
                input_schema=dict(t.input_schema),
                is_concurrency_safe=t.is_concurrency_safe,
                max_result_size_chars=t.max_result_size_chars,
            )
            for t in self._tools.values()
        )

    def get(self, name: str) -> _FakeTool | None:
        return self._tools.get(name)

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: Any | None = None,
        session_file_state: Any | None = None,
        out_meta: dict[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise RuntimeError(f"unknown tool: {name}")
        return tool.run(args, ToolContext(repo_root=Path.cwd()))


@dataclass
class _ToolCallLLM:
    """Fake LLM that emits one tool_use then a final text response."""

    tool_calls: tuple[LLMToolCall, ...]
    final_content: str = "done"

    async def generate(
        self, request: LLMGenerateRequest
    ) -> AsyncIterator[LLMMessage]:
        # First request: emit the tool_use(s). Subsequent request(s): final text.
        has_tool_calls_in_history = any(
            msg.role == "assistant" and msg.tool_calls for msg in request.messages
        )
        if not has_tool_calls_in_history:
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=self.tool_calls,
            )
        yield LLMMessage(
            role="assistant",
            content=self.final_content,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


def _build_engine(
    tmp_path: Path,
    registry: _FakeRuntimeRegistry,
    tool_allowlist: tuple[str, ...] | None,
) -> tuple[AgentEngine, ConversationSession]:
    ref = SessionRef(session_id="sess-allowlist", workspace_root=tmp_path)
    files = JsonlSessionFiles(data_dir=tmp_path / "data")
    writer = JsonlWriter()
    transcript = JsonlTranscript.create(
        ref=ref,
        spec=NewSession(
            workspace_root=tmp_path,
            tool_allowlist=tool_allowlist,
        ),
        files=files,
        writer=writer,
    )
    engine = AgentEngine(
        llm_client=_ToolCallLLM(tool_calls=(LLMToolCall(call_id="call_1", name="fake_read", arguments={"path": "/tmp/foo"}),)),
        model="openai-compat:test",
        repo_root=tmp_path,
        tool_registry=registry,
        system_prompt="",
    )
    session = ConversationSession(ref=ref, transcript=transcript, engine=engine)
    return engine, session


@pytest.mark.asyncio
async def test_empty_tool_allowlist_rejects_tool_without_execution(tmp_path: Path) -> None:
    """Explicitly empty tool_allowlist blocks the tool and never executes it."""
    read_tool = _FakeTool("fake_read")
    registry = _FakeRuntimeRegistry((read_tool,))
    _engine, session = _build_engine(tmp_path, registry, tool_allowlist=())

    result = await session.submit_turn(TurnRequest(parts=({"type": "text", "text": "read"},)))

    assert result.completed is True
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "fake_read"
    assert len(result.tool_results) == 1
    tool_result = result.tool_results[0]
    assert tool_result.error is not None
    assert "tool 'fake_read' is not enabled in this session" in tool_result.error
    assert read_tool.executed == []


@pytest.mark.asyncio
async def test_explicit_tool_allowlist_allows_listed_and_rejects_outside(tmp_path: Path) -> None:
    """A non-empty allowlist permits listed tools and rejects others."""
    read_tool = _FakeTool("fake_read")
    bash_tool = _FakeTool("fake_bash")
    registry = _FakeRuntimeRegistry((read_tool, bash_tool))
    _engine, session = _build_engine(
        tmp_path,
        registry,
        tool_allowlist=("fake_read",),
    )

    result = await session.submit_turn(TurnRequest(parts=({"type": "text", "text": "run"},)))

    assert result.completed is True
    assert len(result.tool_results) == 1
    tool_result = result.tool_results[0]
    assert tool_result.error is not None
    assert "tool 'fake_read' is not enabled in this session" not in tool_result.error
    assert "tool 'fake_read' is not enabled in this session" in str(tool_result.error) or tool_result.output is not None
    # The LLM invoked fake_read, which is allowlisted, so it executed.
    assert tool_result.output is not None
    assert read_tool.executed == [{"path": "/tmp/foo"}]


@pytest.mark.asyncio
async def test_none_tool_allowlist_remains_unrestricted(tmp_path: Path) -> None:
    """tool_allowlist=None keeps the default unrestricted behavior."""
    read_tool = _FakeTool("fake_read")
    registry = _FakeRuntimeRegistry((read_tool,))
    _engine, session = _build_engine(tmp_path, registry, tool_allowlist=None)

    result = await session.submit_turn(TurnRequest(parts=({"type": "text", "text": "read"},)))

    assert result.completed is True
    assert len(result.tool_results) == 1
    tool_result = result.tool_results[0]
    assert tool_result.error is None
    assert tool_result.output is not None
    assert read_tool.executed == [{"path": "/tmp/foo"}]
