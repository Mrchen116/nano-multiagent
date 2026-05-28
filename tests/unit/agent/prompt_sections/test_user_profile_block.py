"""Unit tests for PromptContext.user_profile_block + wiring.

Validates:
- PromptContext has user_profile_block field (str | None, default None)
- build_prompt_context_from_metadata accepts user_profile_block param
- user_profile_block is passed through to PromptContext correctly
"""
from __future__ import annotations

import pytest

from agent.core.agent.prompt_sections.base import PromptContext
from agent.core.agent.prompt_sections.wiring import build_prompt_context_from_metadata


def test_prompt_context_has_user_profile_block_field() -> None:
    ctx = PromptContext()
    assert hasattr(ctx, "user_profile_block")
    assert ctx.user_profile_block is None


def test_prompt_context_user_profile_block_can_be_set() -> None:
    ctx = PromptContext(user_profile_block="## User Profile\n- Name: Alice")
    assert ctx.user_profile_block == "## User Profile\n- Name: Alice"


def test_build_prompt_context_from_metadata_passes_user_profile_block() -> None:
    from agent.core.types import ToolSpec

    ctx = build_prompt_context_from_metadata(
        metadata={},
        available_tools=[ToolSpec(name="read", description="Read.", input_schema={})],
        available_skills=[],
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block="## Memory\n- fact",
        user_profile_block="## User Profile\n- Alice",
        flags={},
    )
    assert ctx.user_profile_block == "## User Profile\n- Alice"
    assert ctx.memory_block == "## Memory\n- fact"


def test_build_prompt_context_from_metadata_user_profile_block_none() -> None:
    ctx = build_prompt_context_from_metadata(
        metadata={},
        available_tools=[],
        available_skills=[],
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=None,
        user_profile_block=None,
        flags={},
    )
    assert ctx.user_profile_block is None
