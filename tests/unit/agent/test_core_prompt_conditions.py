"""Behavioral conditions for capability-dependent core prompt sections."""

from __future__ import annotations

import pytest

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.agent.prompt_sections.core_sections import (
    CORE_BACKGROUND_TASKS,
    CORE_MEMORY_GUIDANCE,
    CORE_SKILLS_GUIDANCE,
)
from agent.core.types import ToolSpec


def _tools(*names: str) -> tuple[ToolSpec, ...]:
    return tuple(
        ToolSpec(name=name, description=f"{name} description", input_schema={})
        for name in names
    )


@pytest.mark.parametrize(
    "tool_names, flags, expected",
    [
        (("memory",), {}, True),
        (("memory",), {"memory_curation": True}, True),
        (("memory",), {"memory_curation": False}, False),
        (("read",), {"memory_curation": True}, False),
    ],
)
def test_memory_guidance_requires_the_tool_and_enabled_feature(
    tool_names: tuple[str, ...], flags: dict[str, bool], expected: bool
) -> None:
    ctx = PromptContext(available_tools=_tools(*tool_names), flags=flags)

    assert CORE_MEMORY_GUIDANCE.enabled_when(ctx) is expected


@pytest.mark.parametrize(
    "tool_names, flags, expected",
    [
        (("skill_view",), {}, True),
        (("skill_manage",), {"skill_creation": True}, True),
        (("skill_view", "skill_manage"), {"skill_creation": False}, False),
        (("read",), {"skill_creation": True}, False),
    ],
)
def test_skills_guidance_requires_a_skill_tool_and_enabled_feature(
    tool_names: tuple[str, ...], flags: dict[str, bool], expected: bool
) -> None:
    ctx = PromptContext(available_tools=_tools(*tool_names), flags=flags)

    assert CORE_SKILLS_GUIDANCE.enabled_when(ctx) is expected


@pytest.mark.parametrize("tool_names, expected", [(('agent',), True), (('read',), False)])
def test_background_task_guidance_requires_the_agent_tool(
    tool_names: tuple[str, ...], expected: bool
) -> None:
    ctx = PromptContext(available_tools=_tools(*tool_names))

    assert CORE_BACKGROUND_TASKS.enabled_when(ctx) is expected


@pytest.mark.parametrize(
    "section, enabled_ctx, disabled_ctx",
    [
        (
            CORE_MEMORY_GUIDANCE,
            PromptContext(available_tools=_tools("memory")),
            PromptContext(available_tools=_tools("read")),
        ),
        (
            CORE_SKILLS_GUIDANCE,
            PromptContext(available_tools=_tools("skill_view")),
            PromptContext(available_tools=_tools("read")),
        ),
        (
            CORE_BACKGROUND_TASKS,
            PromptContext(available_tools=_tools("agent")),
            PromptContext(available_tools=_tools("read")),
        ),
    ],
)
def test_assembly_applies_each_capability_condition(
    section, enabled_ctx: PromptContext, disabled_ctx: PromptContext
) -> None:
    enabled_prompt = assemble_system_prompt([section], enabled_ctx)

    assert enabled_prompt == section.render(enabled_ctx)
    assert assemble_system_prompt([section], disabled_ctx) == ""
