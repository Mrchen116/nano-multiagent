"""Regression: AgentEngine exposes the parent turn's resolved tool names as a
public narrow window (feat-474 M1 R2), so the `agent` tool can build an explicit
child `tool_allowlist` without reaching into runtime private `_resolve_*` methods
when the parent session has no persisted `tool_allowlist` (``None`` case).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from agent.core.agent.runtime import AgentEngine
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage
from agent.core.session.conversation import ConversationSession
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.transcript import JsonlTranscript
from agent.core.session.types import NewSession, SessionRef, TurnRequest
from agent.core.types import ToolSpec, TokenUsage

_SESSION_ID = "sess-active-tools"


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = f"Fake {name}"
        self.input_schema: Mapping[str, Any] = {"type": "object"}
        self.is_concurrency_safe = True
        self.max_result_size_chars: int | None = None


class _StaticRegistry:
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

    async def execute(self, *args: Any, **kwargs: Any) -> Mapping[str, Any]:
        raise AssertionError("this test drives no tool calls")


class _ProbingLLM(LLMClient):
    """Reads the engine's active-run tool names from inside a real run.

    Probing from ``generate()`` (rather than a tool call) sidesteps the
    "probe tool itself gets disabled by the allowlist under test" problem —
    ``generate()`` always runs once per turn regardless of ``tool_allowlist``.
    """

    def __init__(self, engine_holder: dict[str, AgentEngine]) -> None:
        self._engine_holder = engine_holder
        self.captured: list[tuple[str, ...]] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        engine = self._engine_holder["engine"]
        self.captured.append(engine.resolve_active_enabled_tool_names(_SESSION_ID))
        yield LLMMessage(
            role="assistant",
            content="done",
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


def _run_probe_turn(
    tmp_path: Path,
    *,
    tool_allowlist: tuple[str, ...] | None,
) -> tuple[str, ...]:
    ref = SessionRef(session_id=_SESSION_ID, workspace_root=tmp_path)
    files = JsonlSessionFiles(data_dir=tmp_path / "data")
    writer = JsonlWriter()
    transcript = JsonlTranscript.create(
        ref=ref,
        spec=NewSession(workspace_root=tmp_path, tool_allowlist=tool_allowlist),
        files=files,
        writer=writer,
    )
    engine_holder: dict[str, AgentEngine] = {}
    llm = _ProbingLLM(engine_holder)
    engine = AgentEngine(
        llm_client=llm,
        model="openai-compat:test",
        repo_root=tmp_path,
        tool_registry=_StaticRegistry((_FakeTool("fake_read"), _FakeTool("fake_bash"))),
        system_prompt="",
    )
    engine_holder["engine"] = engine
    session = ConversationSession(ref=ref, transcript=transcript, engine=engine)

    result = asyncio.run(
        session.submit_turn(TurnRequest(parts=({"type": "text", "text": "go"},)))
    )
    assert result.completed is True
    assert len(llm.captured) == 1
    return llm.captured[0]


def test_none_allowlist_resolves_to_active_default_tool_names(tmp_path: Path) -> None:
    names = _run_probe_turn(tmp_path, tool_allowlist=None)
    assert set(names) == {"fake_read", "fake_bash"}


def test_explicit_allowlist_resolves_to_active_effective_tool_names(
    tmp_path: Path,
) -> None:
    names = _run_probe_turn(tmp_path, tool_allowlist=("fake_read",))
    assert names == ("fake_read",)


def test_empty_allowlist_resolves_to_empty_tuple(tmp_path: Path) -> None:
    names = _run_probe_turn(tmp_path, tool_allowlist=())
    assert names == ()


def test_call_outside_active_run_raises(tmp_path: Path) -> None:
    engine = AgentEngine(
        llm_client=_ProbingLLM({}),
        model="openai-compat:test",
        repo_root=tmp_path,
        tool_registry=_StaticRegistry(()),
        system_prompt="",
    )

    with pytest.raises(RuntimeError, match="active run"):
        engine.resolve_active_enabled_tool_names("no-such-session")
