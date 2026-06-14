"""Tests for runtime scenario → PromptContext wiring (feat-379-M1 R7).

Verifies:
- build_prompt_context_from_session_config correctly maps hook_metadata /
  session scenario fields into PromptContext.
- communication_context hook's before_agent_start no longer injects a
  system_prompt override (prompt injection retired in M1).
- resolve_effective_prompt with the assembled sections produces group-chat
  context via the pa.communication_context segment instead of the hook.
"""

from __future__ import annotations

import pytest

from agent.core.agent.prompt_sections.base import (
    PromptContext,
    resolve_effective_prompt,
)


# ---------------------------------------------------------------------------
# build_prompt_context_from_metadata (new helper in runtime or loop)
# ---------------------------------------------------------------------------


def test_build_prompt_context_from_metadata_basic():
    """build_prompt_context_from_metadata should produce a valid PromptContext."""
    from agent.core.agent.prompt_sections.wiring import (
        build_prompt_context_from_metadata,
    )

    from agent.core.types import ToolSpec

    tools = (ToolSpec(name="read", description="Read.", input_schema={}),)
    metadata = {
        "conversation_type": "direct",
        "agent_id": "agent-1",
    }
    ctx = build_prompt_context_from_metadata(
        metadata=metadata,
        available_tools=tools,
        available_skills=(),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=None,
        flags={},
    )
    assert isinstance(ctx, PromptContext)
    assert ctx.scenario["conversation_type"] == "direct"
    assert ctx.scenario["agent_id"] == "agent-1"
    assert ctx.current_datetime == "2026-01-01T00:00:00"
    assert ctx.cwd == "/workspace"


def test_build_prompt_context_group_scenario():
    """Group conversation_type is propagated into PromptContext.scenario."""
    from agent.core.agent.prompt_sections.wiring import (
        build_prompt_context_from_metadata,
    )

    metadata = {
        "conversation_type": "group",
        "agent_id": "bot-2",
        "participants": [
            {"type": "user", "user_id": "u1", "display_name": "Alice"},
            {"type": "agent", "agent_id": "bot-2", "display_name": "BotB"},
        ],
        "participant_agent_ids": ["bot-2"],
    }
    ctx = build_prompt_context_from_metadata(
        metadata=metadata,
        available_tools=(),
        available_skills=(),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=None,
        flags={},
    )
    assert ctx.scenario["conversation_type"] == "group"
    assert "participants" in ctx.scenario


def test_build_prompt_context_empty_metadata():
    """Empty metadata produces PromptContext with empty scenario."""
    from agent.core.agent.prompt_sections.wiring import (
        build_prompt_context_from_metadata,
    )

    ctx = build_prompt_context_from_metadata(
        metadata={},
        available_tools=(),
        available_skills=(),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=None,
        flags={},
    )
    assert ctx.scenario == {}


# ---------------------------------------------------------------------------
# communication_context hook: prompt injection retired
# ---------------------------------------------------------------------------
