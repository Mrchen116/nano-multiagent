"""Unit tests for the prompt-section assembler framework (feat-379-M1 R1/R2).

Covers:
- assemble_system_prompt: ordering, enabled_when gate, render None filtering, join
- cache_safe invariant: all cache_safe=False segments must have order > all
  cache_safe=True segments (decision 8)
- resolve_effective_prompt: override direct-pass > section assembly (decision 9)
- feature registry: skeleton structure validity
"""
from __future__ import annotations

import pytest

from agent.core.agent.prompt_sections.base import (
    PromptContext,
    PromptSection,
    assemble_system_prompt,
    resolve_effective_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(**kwargs) -> PromptContext:
    """Build a minimal PromptContext; all optional fields default to empty."""
    return PromptContext(
        available_tools=kwargs.get("available_tools", ()),
        available_skills=kwargs.get("available_skills", ()),
        current_datetime=kwargs.get("current_datetime", "2026-01-01T00:00:00"),
        cwd=kwargs.get("cwd", "/workspace"),
        memory_block=kwargs.get("memory_block", None),
        flags=kwargs.get("flags", {}),
        scenario=kwargs.get("scenario", {}),
        vars=kwargs.get("vars", {}),
    )


def _section(name: str, order: int, text: str, *, cache_safe: bool = True,
             enabled: bool = True) -> PromptSection:
    return PromptSection(
        name=name,
        order=order,
        render=lambda ctx: text,
        enabled_when=lambda ctx: enabled,
        cache_safe=cache_safe,
    )


# ---------------------------------------------------------------------------
# assemble_system_prompt: core assembler behaviour
# ---------------------------------------------------------------------------

def test_assemble_joins_enabled_sections_with_double_newline():
    sections = [
        _section("a", 10, "Section A"),
        _section("b", 20, "Section B"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    assert result == "Section A\n\nSection B"


def test_assemble_sorts_by_order_ascending():
    sections = [
        _section("z", 300, "Last"),
        _section("a", 100, "First"),
        _section("m", 200, "Middle"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    assert result == "First\n\nMiddle\n\nLast"


def test_assemble_stable_sort_by_name_on_equal_order():
    sections = [
        _section("z", 100, "Z text"),
        _section("a", 100, "A text"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    # Alphabetically "a" < "z" so "A text" comes first.
    assert result == "A text\n\nZ text"


def test_assemble_skips_disabled_sections():
    sections = [
        _section("always", 10, "Always here"),
        _section("never", 20, "Should not appear", enabled=False),
        _section("also_always", 30, "Also here"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    assert result == "Always here\n\nAlso here"
    assert "Should not appear" not in result


def test_assemble_skips_sections_whose_render_returns_none():
    def conditional_render(ctx: PromptContext):
        return None  # This section is absent this turn.

    sections = [
        _section("stable", 10, "Stable"),
        PromptSection(name="volatile", order=20, render=conditional_render),
        _section("final", 30, "Final"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    assert result == "Stable\n\nFinal"


def test_assemble_skips_sections_whose_render_returns_empty_string():
    sections = [
        _section("real", 10, "Real"),
        PromptSection(name="empty", order=20, render=lambda ctx: ""),
        _section("real2", 30, "Real2"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    assert result == "Real\n\nReal2"


def test_assemble_passes_context_to_render():
    """render() receives the PromptContext it was assembled with."""
    received: list[PromptContext] = []

    def capturing_render(ctx: PromptContext):
        received.append(ctx)
        return "captured"

    sections = [PromptSection(name="capture", order=10, render=capturing_render)]
    ctx = _ctx(cwd="/home/user")
    assemble_system_prompt(sections, ctx)
    assert len(received) == 1
    assert received[0].cwd == "/home/user"


def test_assemble_passes_context_to_enabled_when():
    """enabled_when() receives the PromptContext and can gate on flags."""
    sections = [
        PromptSection(
            name="flag_gated",
            order=10,
            render=lambda ctx: "Feature active",
            enabled_when=lambda ctx: ctx.flags.get("my_feature", False),
        ),
        _section("always", 20, "Always"),
    ]
    # Without flag: section absent.
    without = assemble_system_prompt(sections, _ctx())
    assert "Feature active" not in without

    # With flag: section present.
    with_flag = assemble_system_prompt(sections, _ctx(flags={"my_feature": True}))
    assert "Feature active" in with_flag


def test_assemble_empty_sections_returns_empty_string():
    assert assemble_system_prompt([], _ctx()) == ""


# ---------------------------------------------------------------------------
# cache_safe invariant (decision 8)
# ---------------------------------------------------------------------------

def test_cache_safe_invariant_passes_when_all_stable():
    """All cache_safe=True: no ordering constraint to violate."""
    sections = [
        _section("a", 100, "A", cache_safe=True),
        _section("b", 200, "B", cache_safe=True),
    ]
    # Must not raise.
    assemble_system_prompt(sections, _ctx())


def test_cache_safe_invariant_passes_when_volatile_after_stable():
    sections = [
        _section("stable", 100, "Stable", cache_safe=True),
        _section("volatile", 950, "Volatile", cache_safe=False),
    ]
    assemble_system_prompt(sections, _ctx())


def test_cache_safe_invariant_fails_when_volatile_before_stable():
    """cache_safe=False segment with order < any cache_safe=True segment violates invariant."""
    sections = [
        _section("volatile_early", 100, "Volatile", cache_safe=False),
        _section("stable_late", 900, "Stable", cache_safe=True),
    ]
    with pytest.raises(ValueError, match="cache_safe"):
        assemble_system_prompt(sections, _ctx())


def test_cache_safe_invariant_fails_when_volatile_has_equal_order_to_stable():
    """Equal order between cache_safe=False and cache_safe=True must also fail (strict >)."""
    sections = [
        _section("volatile", 500, "Volatile", cache_safe=False),
        _section("stable", 500, "Stable", cache_safe=True),
    ]
    with pytest.raises(ValueError, match="cache_safe"):
        assemble_system_prompt(sections, _ctx())


# ---------------------------------------------------------------------------
# resolve_effective_prompt (decision 9): override > section assembly
# ---------------------------------------------------------------------------

def test_resolve_uses_override_when_provided():
    """Non-empty override bypasses section assembly entirely."""
    sections = [_section("default", 10, "Section output")]
    ctx = _ctx()
    result = resolve_effective_prompt(
        sections=sections,
        ctx=ctx,
        override="Direct override text",
    )
    assert result == "Direct override text"
    assert "Section output" not in result


def test_resolve_uses_section_assembly_when_no_override():
    sections = [_section("s", 10, "Assembled output")]
    result = resolve_effective_prompt(sections=sections, ctx=_ctx(), override=None)
    assert result == "Assembled output"


def test_resolve_uses_section_assembly_when_override_is_empty_string():
    """Empty string override is treated as absent; assembly runs."""
    sections = [_section("s", 10, "Assembled")]
    result = resolve_effective_prompt(sections=sections, ctx=_ctx(), override="")
    assert result == "Assembled"


def test_resolve_uses_section_assembly_when_override_is_whitespace():
    """Whitespace-only override is treated as absent; assembly runs."""
    sections = [_section("s", 10, "Assembled")]
    result = resolve_effective_prompt(sections=sections, ctx=_ctx(), override="   ")
    assert result == "Assembled"


def test_resolve_override_covers_subagent_fork_path():
    """Override direct-pass is the mechanism used by AgentContextFork (decision 9).
    Verify override beats any number of sections with any content.
    """
    sections = [
        _section("pa.identity", 100, "PA Identity"),
        _section("core.system", 200, "Core System"),
        _section("pa.user_custom", 800, "Custom Instructions"),
    ]
    fork_prompt = "# Sub-Agent System Prompt\nYou are a specialized worker."
    result = resolve_effective_prompt(
        sections=sections,
        ctx=_ctx(),
        override=fork_prompt,
    )
    assert result == fork_prompt
    assert "PA Identity" not in result
