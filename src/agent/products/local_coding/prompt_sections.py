"""Local Coding product prompt segments (lc.*).

Text is migrated verbatim from LOCAL_CODING_SYSTEM_PROMPT in prompts.py so
that golden-equivalence tests pass with zero content changes.

Segment name convention: ``lc.<semantic_name>``
Order bands used (full table in design.md):
  100  product identity
  330  product guidelines

LC does not have group chat, heartbeat, user_custom, or communication_context.
Core segments (runtime_tools, skills_listing, memory/skill guidance, background
tasks, runtime_footer, memory_block) are shared with PA via CORE_SECTIONS.
"""
from __future__ import annotations

from agent.core.agent.prompt_sections.base import PromptContext, PromptSection


# Provenance: new — migrated verbatim from LOCAL_CODING_SYSTEM_PROMPT opening
#   in agent/core/agent/prompting.py (the string starts "You are an expert
#   coding assistant…")
_LC_IDENTITY = PromptSection(
    name="lc.identity",
    render=lambda ctx: (
        "You are an expert coding assistant operating inside a coding agent harness. "
        "You help users by reading files, executing commands, editing code, and writing new files."
    ),
    cache_safe=True,
)

# Provenance: new — migrated verbatim from Guidelines block in LOCAL_CODING_SYSTEM_PROMPT
_LC_GUIDELINES = PromptSection(
    name="lc.guidelines",
    render=lambda ctx: (
        "Guidelines:\n"
        "- Use bash for file operations like ls, rg, find\n"
        "- Use read to examine files before editing. You must use this tool instead of cat or sed.\n"
        "- Use edit for precise changes (old text must match exactly)\n"
        "- Use write only for new files or complete rewrites\n"
        "- When summarizing your actions, output plain text directly - "
        "do NOT use cat or bash to display what you did\n"
        "- Be concise in your responses\n"
        "- Show file paths clearly when working with files"
    ),
    cache_safe=True,
)

# Provenance: new — migrated from "In addition to the tools above..." note in
#   LOCAL_CODING_SYSTEM_PROMPT; placed between available tools and guidelines.
_LC_TOOLS_FOOTER = PromptSection(
    name="lc.tools_footer",
    render=lambda ctx: (
        "In addition to the tools above, you may have access to other custom tools "
        "depending on the project."
    ),
    cache_safe=True,
)


# ---------------------------------------------------------------------------
# Public export: ordered tuple of all LC segments
# ---------------------------------------------------------------------------

LC_SECTIONS: tuple[PromptSection, ...] = (
    _LC_IDENTITY,
    _LC_GUIDELINES,
    _LC_TOOLS_FOOTER,
)


# ---------------------------------------------------------------------------
# M4 Decision 15: explicit assembly function (mirrors CC getSystemPrompt)
# ---------------------------------------------------------------------------

def build_lc_system_prompt() -> list[PromptSection]:
    """Return the explicit, ordered list of segments for the Local Coding product.

    Mirrors CC getSystemPrompt pattern: one function, linear list, explicit order.

    Returns:
        Ordered list of PromptSection objects for assembly by assemble_system_prompt.
    """
    from agent.core.agent.prompt_sections.core_sections import (  # noqa: PLC0415
        CORE_SYSTEM,
        CORE_ACTIONS_CARE,
        CORE_TOOL_RULES,
        CORE_TONE_STYLE,
        CORE_SKILLS_LISTING,
        CORE_MEMORY_GUIDANCE,
        CORE_SKILLS_GUIDANCE,
        CORE_BACKGROUND_TASKS,
        CORE_RUNTIME_FOOTER,
        CORE_MEMORY_BLOCK,
        CORE_USER_PROFILE_BLOCK,
    )
    return [
        # ── Stable prefix (cache_safe=True) ──────────────────────────────────
        # Product identity
        _LC_IDENTITY,
        # Core behaviour rules (CC-aligned)
        CORE_SYSTEM,
        CORE_ACTIONS_CARE,
        CORE_TOOL_RULES,
        CORE_TONE_STYLE,
        # Product-specific behaviour (tools footer before guidelines)
        _LC_TOOLS_FOOTER,
        _LC_GUIDELINES,
        # Self-evolution guidance (gated by feature flags + tool presence)
        CORE_SKILLS_LISTING,
        CORE_MEMORY_GUIDANCE,
        CORE_SKILLS_GUIDANCE,
        # Background task framing + runtime mechanism
        CORE_BACKGROUND_TASKS,
        CORE_RUNTIME_FOOTER,
        # ── Volatile tail (cache_safe=False) ─────────────────────────────────
        CORE_MEMORY_BLOCK,          # MEMORY.md snapshot
        CORE_USER_PROFILE_BLOCK,    # USER.md snapshot
    ]
