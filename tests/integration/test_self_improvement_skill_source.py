"""Integration coverage for automatic Skill Review creation provenance."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from agent.core.agent.context_fork import AgentContextFork, make_fork_conversation
from agent.core.hooks.context import HookContext
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.core.skills.registry import SkillRegistry
from agent.core.tools.base import (
    ToolContext,
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.core.tools.registry import ToolRegistry
from agent.platform.hooks.builtins import self_improvement
from agent.platform.tools.builtins.skill_manage import SkillManageTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


class _CreateSkillReviewClient:
    """Create one Skill in the review fork, then finish."""

    def __init__(self) -> None:
        self._round = 0

    def generate(
        self, request: LLMGenerateRequest
    ) -> AsyncIterator[LLMMessage]:
        """Return the scripted two-round Skill Review response."""

        _ = request
        self._round += 1
        round_no = self._round

        async def _stream() -> AsyncIterator[LLMMessage]:
            if round_no == 1:
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="create-auto-skill",
                            name="skill_manage",
                            arguments={
                                "action": "create",
                                "name": "auto-review-skill",
                                "scope": "agent",
                                "content": (
                                    "---\nname: auto-review-skill\n"
                                    "description: Created by an automatic review\n"
                                    "---\n\n# Instructions\n\nReuse the reviewed workflow.\n"
                                ),
                            },
                        ),
                    ),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
                return
            yield LLMMessage(role="assistant", content="review complete")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

        return _stream()


def _self_improvement_handler() -> Any:
    registered: dict[str, Any] = {}

    class _HookAPI:
        def on(
            self,
            event: str,
            handler: Any,
            *,
            priority: int = 100,
            timeout_ms: int = 1500,
            mode: str = "observe",
        ) -> None:
            _ = priority, timeout_ms, mode
            registered[event] = handler

    self_improvement.setup(_HookAPI())
    return registered["agent_end"]


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_threshold", [100, 1], ids=["skill-only", "combined"])
async def test_background_skill_review_create_records_f3_source(
    tmp_path: Path, memory_threshold: int
) -> None:
    """Persist F3 when a skill-only or combined background Review creates a Skill."""

    set_tool_safety_factory(ToolSafety)
    set_tool_safety_config_factory(ToolSafetyConfig)
    skill_root = tmp_path / "skills"
    skill_registry = SkillRegistry(search_roots=[skill_root])
    skill_tool = SkillManageTool(skill_root=skill_root, registry=skill_registry)
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    tool_registry.register(skill_tool)
    context_fork = AgentContextFork(
        llm_client=_CreateSkillReviewClient(),
        model="test-model",
        tool_registry=tool_registry,
        current_working_directory=tmp_path,
    )
    parent_ctx = HookContext(
        session_id=f"review-{memory_threshold}",
        repo_root=tmp_path,
        metadata={
            "self_evolution": {
                "enabled": True,
                "skill_creation": True,
                "memory_curation": True,
                "skill_nudge_interval": 1,
                "memory_nudge_interval": memory_threshold,
            }
        },
        session_event_publisher=lambda _event, _data: None,
    )
    fork_fn = make_fork_conversation(
        context_fork=context_fork,
        rendered_system_prompt="Review the completed conversation.",
        active_tools=tool_registry.list_specs(),
        messages_snapshot=[],
        session_id=parent_ctx.session_id,
        tool_allowlist=(),
        parent_hook_ctx=parent_ctx,
        model="test-model",
    )
    review_ctx = HookContext(
        session_id=parent_ctx.session_id,
        repo_root=tmp_path,
        metadata=parent_ctx.metadata,
        fork_conversation=fork_fn,
        session_event_publisher=lambda _event, _data: None,
    )

    await _self_improvement_handler()(
        {"tool_iterations": 1, "turn_count": 1}, review_ctx
    )

    usage = json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))
    assert usage["auto-review-skill"]["source"] == "F3"
