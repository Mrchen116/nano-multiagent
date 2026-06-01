"""Golden-equivalence integration tests for the segment-based prompt assembly.

These tests assert that the new assemble_system_prompt() output is content-equivalent
to the legacy build_system_prompt() output across the four canonical scenarios
required by feat-379-M1 exit criteria.

Scenarios:
  1. Direct chat (no group), no memory/skill tools, no custom_prompt  → PA golden
  2. Group chat, memory + skill tools active                           → PA golden w/ comm context
  3. Direct chat, memory tool active                                   → PA golden w/ memory guidance
  4. Direct chat, custom_prompt non-empty                              → PA golden w/ user_custom
  5. LC direct, no memory/skill tools                                  → LC golden
  6. LC direct, memory + skill tools active                            → LC golden w/ guidance

Key invariants:
- bugfix-358 mention text (inline <mention …/>) must appear verbatim in group scenario.
- core.background_tasks ONLY appears when the "agent" tool is present (design change from
  unconditional — this is the documented M1 exception, not a golden regression).
- cache_safe=False segments (communication_context, memory_block) must be absent from
  stable-prefix scenarios (no group / no memory_block).

These tests import both the legacy prompting module and the new segment modules.
They will fail until core_sections.py and PA/LC prompt_sections.py are implemented.
"""

from __future__ import annotations

import platform
from pathlib import Path

import pytest

from agent.core.agent.prompting import (
    MEMORY_GUIDANCE,
    SKILLS_GUIDANCE,
)
from agent.core.agent.prompt_sections.base import (
    PromptContext,
    assemble_system_prompt,
    resolve_effective_prompt,
)
from agent.core.types import ToolSpec
from agent.core.skills.registry import SkillMetadata


# ---------------------------------------------------------------------------
# Minimal ToolSpec fixtures
# ---------------------------------------------------------------------------


def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name} tool.", input_schema={})


BASIC_PA_TOOLS = (
    _tool("read"),
    _tool("write"),
    _tool("edit"),
    _tool("bash"),
    _tool("web_search"),
    _tool("web_fetch"),
    _tool("send_message"),
)
MEMORY_TOOLS = (*BASIC_PA_TOOLS, _tool("memory"))
SKILL_TOOLS = (*MEMORY_TOOLS, _tool("skill_manage"))
AGENT_TOOLS = (*BASIC_PA_TOOLS, _tool("agent"))
FULL_TOOLS = (*SKILL_TOOLS, _tool("agent"))

BASIC_LC_TOOLS = (
    _tool("read"),
    _tool("write"),
    _tool("edit"),
    _tool("bash"),
    _tool("agent"),
)
LC_FULL_TOOLS = (*BASIC_LC_TOOLS, _tool("memory"), _tool("skill_manage"))


# ---------------------------------------------------------------------------
# PA section imports (will fail until PA prompt_sections.py is implemented)
# ---------------------------------------------------------------------------


def _pa_sections(
    tools: tuple[ToolSpec, ...], scenario: dict | None = None, custom_prompt: str = ""
):
    """Build PA section list and context for assembly.

    M4: uses build_pa_system_prompt() which provides the correct explicit ordering
    (stable segments first, volatile tail at the end — cache_safe invariant by
    list position). Direct CORE_SECTIONS + PA_SECTIONS concatenation is no longer
    valid because volatile core segments would appear before stable PA segments.
    """
    from agent.products.personal_assistant.prompt_sections import build_pa_system_prompt

    all_sections = build_pa_system_prompt()
    ctx = PromptContext(
        available_tools=tools,
        available_skills=(),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=None,
        flags={},
        scenario=scenario or {},
        vars={"custom_prompt": custom_prompt} if custom_prompt else {},
    )
    return all_sections, ctx


def _lc_sections(tools: tuple[ToolSpec, ...]):
    """Build LC section list and context for assembly.

    M4: uses build_lc_system_prompt() for correct explicit ordering.
    """
    from agent.products.local_coding.prompt_sections import build_lc_system_prompt

    all_sections = build_lc_system_prompt()
    ctx = PromptContext(
        available_tools=tools,
        available_skills=(),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=None,
        flags={},
        scenario={},
        vars={},
    )
    return all_sections, ctx


# feat-385: legacy golden helpers (_old_pa_prompt / _old_lc_prompt) removed.
# The old f-string templates (prompts.py) are deleted; all content is now in
# prompt_sections. Tests now only verify the new segment-assembled prompt.


# ---------------------------------------------------------------------------
# Scenario 1: PA direct chat, no memory/skill tools
# ---------------------------------------------------------------------------


def test_pa_golden_direct_no_memory_no_skill():
    """Segment assembly for direct chat without self-evolution tools."""
    sections, ctx = _pa_sections(BASIC_PA_TOOLS)
    new_prompt = assemble_system_prompt(sections, ctx)

    # Core identity present.
    assert "Nano Personal Assistant" in new_prompt
    assert "helpful personal assistant" in new_prompt

    # feat-385: pa.memory_intro deleted — replaced by core.memory_guidance (injected only
    # when memory tool is active). Direct check for the old "## Memory" / "MEMORY.md"
    # header removed since that segment is gone.

    # Heartbeat present (always-on in PA).
    assert "## Heartbeat" in new_prompt

    # Platform policy present.
    assert "Platform Policy" in new_prompt

    # Guidelines present.
    assert "## Guidelines" in new_prompt
    assert "Be concise and conversational" in new_prompt

    # Runtime footer present.
    assert "Current date and time: 2026-01-01T00:00:00" in new_prompt
    assert "Current working directory: /workspace" in new_prompt

    # Self-evolution guidance absent (tools not active).
    assert MEMORY_GUIDANCE not in new_prompt
    assert SKILLS_GUIDANCE not in new_prompt

    # No communication context (direct chat).
    assert "[Communication Context]" not in new_prompt

    # feat-385: core.runtime_tools deleted — tools travel via API tools=[] channel only.
    # The old "## Available Tools" section must NOT appear in the system prompt.
    assert "## Available Tools" not in new_prompt

    # No user custom section.
    assert "# Custom Agent Instructions" not in new_prompt

    # background_tasks absent (no agent tool).
    assert "task-notification" not in new_prompt


def test_pa_golden_direct_no_memory_no_skill_contains_old_content():
    """All unique content from old prompt must appear in new prompt."""
    sections, ctx = _pa_sections(BASIC_PA_TOOLS)
    new_prompt = assemble_system_prompt(sections, ctx)

    # Key phrases from original PA prompt.
    assert (
        "You are a helpful personal assistant communicating through instant messaging."
        in new_prompt
    )
    assert (
        "State intent before tool calls, but NEVER predict or claim results before receiving them."
        in new_prompt
    )
    assert (
        "Routing boundary (strict): when replying to this conversation, output text directly"
        in new_prompt
    )
    assert "only treat it as sent when the tool returns `ok=true`" in new_prompt


# ---------------------------------------------------------------------------
# Scenario 2: PA group chat, memory + skill tools
# ---------------------------------------------------------------------------

SAMPLE_GROUP_SCENARIO = {
    "conversation_type": "group",
    "agent_id": "agent-123",
    "participants": [
        {"type": "user", "user_id": "user-abc", "display_name": "Alice"},
        {"type": "agent", "agent_id": "agent-123", "display_name": "BotB"},
    ],
    "participant_agent_ids": ["agent-123"],
}


def test_pa_golden_group_chat_with_memory_skill():
    """Group chat scenario must include communication context and guidance."""
    sections, ctx = _pa_sections(FULL_TOOLS, scenario=SAMPLE_GROUP_SCENARIO)
    new_prompt = assemble_system_prompt(sections, ctx)

    # Communication context present.
    assert "[Communication Context]" in new_prompt
    assert "session_type: group" in new_prompt
    assert "your_agent_id: agent-123" in new_prompt
    assert "group_participants" in new_prompt

    # bugfix-358: inline mention tag format verbatim.
    assert '<mention type="agent" target_id=' in new_prompt
    assert '<mention type="user" target_id=' in new_prompt

    # Self-evolution guidance present.
    assert MEMORY_GUIDANCE in new_prompt
    assert SKILLS_GUIDANCE in new_prompt

    # Identity still present.
    assert "Nano Personal Assistant" in new_prompt

    # Background tasks present (agent tool in FULL_TOOLS).
    assert "task-notification" in new_prompt


def test_pa_golden_group_chat_mention_text_verbatim():
    """bugfix-358 mention format text must appear verbatim (character-for-character)."""
    sections, ctx = _pa_sections(BASIC_PA_TOOLS, scenario=SAMPLE_GROUP_SCENARIO)
    new_prompt = assemble_system_prompt(sections, ctx)

    # The exact phrasing established by bugfix-358.
    expected_fragment = (
        "历史消息中每条以 [display_name] 标识发言人；你的回复无需加前缀。"
        ' 在群聊中引用某人时，直接在回复中写 <mention type="agent" target_id="<id>"/> 或'
        ' <mention type="user" target_id="<id>"/>'
    )
    assert expected_fragment in new_prompt, (
        "bugfix-358 mention text not found verbatim in group chat prompt"
    )


# ---------------------------------------------------------------------------
# Scenario 3: PA direct chat, memory tool active
# ---------------------------------------------------------------------------


def test_pa_golden_direct_with_memory_tool():
    """MEMORY_GUIDANCE injected when memory tool is active."""
    sections, ctx = _pa_sections(MEMORY_TOOLS)
    new_prompt = assemble_system_prompt(sections, ctx)

    assert MEMORY_GUIDANCE in new_prompt
    assert SKILLS_GUIDANCE not in new_prompt  # skill_manage not in MEMORY_TOOLS


# ---------------------------------------------------------------------------
# Scenario 4: PA direct chat, custom_prompt non-empty
# ---------------------------------------------------------------------------


def test_pa_golden_direct_with_custom_prompt():
    """User custom instructions appear in stable prefix when custom_prompt is set."""
    custom = "You are my personal legal advisor. Always cite relevant statutes."
    sections, ctx = _pa_sections(BASIC_PA_TOOLS, custom_prompt=custom)
    new_prompt = assemble_system_prompt(sections, ctx)

    assert "# Custom Agent Instructions" in new_prompt
    assert custom in new_prompt

    # Custom section must appear after all standard sections (order 800).
    custom_pos = new_prompt.index("# Custom Agent Instructions")
    identity_pos = new_prompt.index("Nano Personal Assistant")
    assert custom_pos > identity_pos, "user_custom must come after identity"


def test_pa_golden_direct_without_custom_prompt_no_custom_header():
    """No custom instructions section when custom_prompt is empty."""
    sections, ctx = _pa_sections(BASIC_PA_TOOLS, custom_prompt="")
    new_prompt = assemble_system_prompt(sections, ctx)
    assert "# Custom Agent Instructions" not in new_prompt


# ---------------------------------------------------------------------------
# Scenario 5: LC direct chat, no memory/skill tools
# ---------------------------------------------------------------------------


def test_lc_golden_direct_no_memory_no_skill():
    """LC assembly matches legacy LOCAL_CODING_SYSTEM_PROMPT content."""
    sections, ctx = _lc_sections(BASIC_LC_TOOLS)
    new_prompt = assemble_system_prompt(sections, ctx)

    # LC identity.
    assert (
        "coding assistant" in new_prompt.lower()
        or "expert coding" in new_prompt.lower()
    )

    # Runtime footer.
    assert "Current date and time: 2026-01-01T00:00:00" in new_prompt
    assert "Current working directory: /workspace" in new_prompt

    # No memory/skill guidance.
    assert MEMORY_GUIDANCE not in new_prompt
    assert SKILLS_GUIDANCE not in new_prompt

    # No communication context (LC has no group chat).
    assert "[Communication Context]" not in new_prompt

    # background_tasks present (agent tool in BASIC_LC_TOOLS).
    assert "task-notification" in new_prompt


# ---------------------------------------------------------------------------
# Scenario 6: LC direct chat, memory + skill tools active
# ---------------------------------------------------------------------------


def test_lc_golden_direct_with_memory_and_skill():
    """LC with both self-evolution tools injects both guidance blocks."""
    sections, ctx = _lc_sections(LC_FULL_TOOLS)
    new_prompt = assemble_system_prompt(sections, ctx)

    assert MEMORY_GUIDANCE in new_prompt
    assert SKILLS_GUIDANCE in new_prompt


# ---------------------------------------------------------------------------
# Invariant: background_tasks gate (M1 documented exception)
# ---------------------------------------------------------------------------


def test_background_tasks_absent_without_agent_tool():
    """core.background_tasks must NOT appear when 'agent' tool is absent."""
    # PA without agent tool.
    sections, ctx = _pa_sections(BASIC_PA_TOOLS)  # no agent tool
    new_prompt = assemble_system_prompt(sections, ctx)
    assert "task-notification" not in new_prompt, (
        "core.background_tasks must be gated on 'agent' tool"
    )


def test_background_tasks_present_with_agent_tool():
    """core.background_tasks must appear when 'agent' tool is present."""
    sections, ctx = _pa_sections(AGENT_TOOLS)
    new_prompt = assemble_system_prompt(sections, ctx)
    assert "task-notification" in new_prompt


# ---------------------------------------------------------------------------
# cache_safe ordering: volatile segments must come after stable segments
# ---------------------------------------------------------------------------


def test_cache_safe_ordering_in_pa_direct():
    """M4 Decision 16: volatile segments are at the end of the list (list-position invariant)."""
    from agent.products.personal_assistant.prompt_sections import build_pa_system_prompt

    all_sections = build_pa_system_prompt()

    stable_indices = [i for i, s in enumerate(all_sections) if s.cache_safe]
    volatile_indices = [i for i, s in enumerate(all_sections) if not s.cache_safe]

    if stable_indices and volatile_indices:
        assert min(volatile_indices) > max(stable_indices), (
            f"cache_safe invariant violated by list position: "
            f"min volatile idx={min(volatile_indices)}, "
            f"max stable idx={max(stable_indices)}"
        )


# ---------------------------------------------------------------------------
# memory_block: volatile segment present when ctx.memory_block is set
# ---------------------------------------------------------------------------


def test_memory_block_present_when_ctx_has_memory_block():
    """core.memory_block segment renders the memory_block from context."""
    from agent.products.personal_assistant.prompt_sections import build_pa_system_prompt

    all_sections = build_pa_system_prompt()
    fake_block = "══════\nMEMORY [0% — 0/2,200 chars]\n══════\n"
    ctx = PromptContext(
        available_tools=BASIC_PA_TOOLS,
        available_skills=(),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=fake_block,
        flags={},
        scenario={},
        vars={},
    )
    result = assemble_system_prompt(all_sections, ctx)
    assert fake_block in result
