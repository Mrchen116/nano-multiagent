"""Unit tests for core_sections R3 changes.

Validates:
- core.runtime_tools segment is GONE from CORE_SECTIONS
- core.user_profile_block segment is in CORE_SECTIONS (order=960, cache_safe=False)
- core.user_profile_block renders ctx.user_profile_block when set
- core.user_profile_block is disabled when ctx.user_profile_block is None/empty
- cache_safe invariant is satisfied (all cache_safe=False segments have order > max stable order)
"""
from __future__ import annotations

import pytest

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.agent.prompt_sections.core_sections import CORE_SECTIONS
from agent.core.types import ToolSpec


def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name}.", input_schema={})


def test_core_runtime_tools_segment_removed() -> None:
    """core.runtime_tools must not be in CORE_SECTIONS after R3."""
    names = {s.name for s in CORE_SECTIONS}
    assert "core.runtime_tools" not in names


def test_core_user_profile_block_segment_exists() -> None:
    names = {s.name for s in CORE_SECTIONS}
    assert "core.user_profile_block" in names


def test_core_user_profile_block_cache_safe_and_position() -> None:
    """M4 Decision 16: no order field; check cache_safe + list position relative to memory_block."""
    seg = next(s for s in CORE_SECTIONS if s.name == "core.user_profile_block")
    assert seg.cache_safe is False
    # user_profile_block must come after memory_block in the list (both volatile)
    names = [s.name for s in CORE_SECTIONS]
    memory_idx = names.index("core.memory_block")
    user_idx = names.index("core.user_profile_block")
    assert user_idx > memory_idx, "user_profile_block must be listed after memory_block"


def test_core_user_profile_block_renders_when_set() -> None:
    ctx = PromptContext(user_profile_block="## User Profile\n- Alice is a developer.")
    seg = next(s for s in CORE_SECTIONS if s.name == "core.user_profile_block")
    rendered = seg.render(ctx)
    assert rendered == "## User Profile\n- Alice is a developer."


def test_core_user_profile_block_disabled_when_none() -> None:
    ctx = PromptContext(user_profile_block=None)
    seg = next(s for s in CORE_SECTIONS if s.name == "core.user_profile_block")
    assert not seg.enabled_when(ctx)


def test_core_user_profile_block_not_in_assembly_when_none() -> None:
    ctx = PromptContext(
        available_tools=(_tool("read"),),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        user_profile_block=None,
    )
    result = assemble_system_prompt(CORE_SECTIONS, ctx)
    assert "User Profile" not in result


def test_core_user_profile_block_in_assembly_when_set() -> None:
    ctx = PromptContext(
        available_tools=(_tool("read"),),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        user_profile_block="## User Profile\n- Name: Alice",
    )
    result = assemble_system_prompt(CORE_SECTIONS, ctx)
    assert "## User Profile\n- Name: Alice" in result


def test_cache_safe_invariant_satisfied() -> None:
    """assemble_system_prompt must not raise — invariant satisfied."""
    ctx = PromptContext(
        available_tools=(_tool("read"),),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block="## Memory\n- fact",
        user_profile_block="## User Profile\n- Alice",
    )
    # Should not raise ValueError
    result = assemble_system_prompt(CORE_SECTIONS, ctx)
    assert result  # non-empty


def test_available_tools_not_listed_in_prompt() -> None:
    """After removing core.runtime_tools, tools should not appear as ## Available Tools."""
    ctx = PromptContext(
        available_tools=(_tool("read"), _tool("write")),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
    )
    result = assemble_system_prompt(CORE_SECTIONS, ctx)
    assert "## Available Tools" not in result
