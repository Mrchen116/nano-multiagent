"""Core prompt-section data structures and assembler.

Design decisions captured here:
- Decision 2: PromptSection is a pure data + two pure functions; no side effects.
  PromptContext is a frozen dataclass (assembly-time read-only snapshot).
- Decision 8 (M4 updated): cache_safe=False segments must appear after every
  cache_safe=True segment — validated by list position (volatile segments' indices
  must all be greater than every stable segment's index). Enforced at assembly time
  so the stable prefix is always contiguous and provider auto-prefix-cache hit rate
  is maximised.
- Decision 9: resolve_effective_prompt is the single resolution point: override
  direct-pass (internal / sub-agent fork) beats section assembly.
- Decision 15/16 (M4): ordering is explicit by list position — the caller (product
  build_<product>_system_prompt function) returns sections in the desired order.
  There is no 'order' magic number field. This mirrors CC's getSystemPrompt where
  the function body is a linear list of sections.

This module is pure core: no imports from the platform or products layers —
core must not depend on higher layers (contract: test_core_no_platform_imports.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class PromptContext:
    """Immutable snapshot of runtime context passed to every PromptSection.

    Fields are read-only; assembly-time state only — mutable runtime state
    never enters here.

    Args:
        available_tools: Tool specs active for this session turn.
        available_skills: Skill metadata active for this session turn.
        current_datetime: Session-created-at timestamp string (stable across
            turns so it lands in the cache-stable prefix).
        cwd: Current working directory string for this session.
        memory_block: Pre-rendered MemoryStore snapshot (banner + content), or
            None when absent. Volatile (changes turn to turn) — passed to
            cache_safe=False segment.
        user_profile_block: Pre-rendered USER.md snapshot (banner + content), or
            None when absent. Volatile (changes turn-to-turn) — passed to
            cache_safe=False segment.
        flags: Per-agent feature flags (key → bool).  Missing key → False.
        scenario: Conversation-level metadata (conversation_type, participants,
            group_reply_policy, run_origin, …).  Read by gated segments.
        vars: Freeform string vars (e.g. "custom_prompt" for pa.user_custom).
    """

    available_tools: tuple = field(default_factory=tuple)
    available_skills: tuple = field(default_factory=tuple)
    current_datetime: str = ""
    cwd: str = ""
    memory_block: str | None = None
    user_profile_block: str | None = None    # independent field + volatile segment for USER.md user profile
    flags: Mapping[str, bool] = field(default_factory=dict)
    scenario: Mapping[str, object] = field(default_factory=dict)
    vars: Mapping[str, str] = field(default_factory=dict)

    def has_tool(self, name: str) -> bool:
        """Return True when a tool with the given name is active this turn."""
        return any(getattr(t, "name", None) == name for t in self.available_tools)


@dataclass(frozen=True)
class PromptSection:
    """A single named, gate-controlled segment of the system prompt.

    Segments are pure-data objects — render and enabled_when are pure functions
    that receive PromptContext and produce deterministic output (no IO, no state).

    Ordering is by list position in the sequence passed to assemble_system_prompt
    (Decision 16 / M4). The product's build_<product>_system_prompt() function is
    the single authoritative place for segment ordering — open it and you see the
    complete prompt structure at a glance (mirrors CC getSystemPrompt).

    Args:
        name: Stable internal identifier (e.g. "core.system", "pa.identity").
            Not rendered into the prompt text; used for registry references.
            Convention: ``<layer>.<semantic_name>``.
        render: ``(ctx) -> str | None``.  Returns the rendered text for this
            segment, or None / empty string to omit it entirely this turn.
        enabled_when: ``(ctx) -> bool``.  When False the segment is skipped
            without calling render.  Defaults to always-enabled.
        cache_safe: When True the segment's content is stable across turns and
            contributes to the provider's auto-prefix-cache stable prefix.
            When False the segment may change turn-to-turn (e.g. MemoryStore
            snapshot, live participant list) and must be placed after all
            cache_safe=True segments in the list (enforced by assemble_system_prompt
            to protect prefix-cache stability).
    """

    name: str
    render: Callable[[PromptContext], str | None]
    enabled_when: Callable[[PromptContext], bool] = field(
        default_factory=lambda: lambda ctx: True
    )
    cache_safe: bool = True


def assemble_system_prompt(
    sections: Sequence[PromptSection],
    ctx: PromptContext,
) -> str:
    """Assemble sections into a single system-prompt string.

    Algorithm:
    1. Validate the cache_safe invariant by list position: every cache_safe=False
       segment's index must be greater than every cache_safe=True segment's index
       (volatile segments must come after the stable prefix). Raises ValueError on
       violation so mis-wired product assemblies are loud failures, not silent
       cache degradations.
    2. Iterate sections in list order (no additional sorting — order is the caller's
       responsibility via build_<product>_system_prompt).
    3. For each section: skip if not enabled_when(ctx); call render(ctx); skip if
       result is None or empty.
    4. Join surviving pieces with "\\n\\n".

    Args:
        sections: Ordered sequence of PromptSection objects (as returned by
            build_<product>_system_prompt or a test-supplied list).
        ctx: Frozen runtime snapshot for this turn.

    Returns:
        Fully assembled system-prompt string.  Empty string when all sections
        are absent/disabled.

    Raises:
        ValueError: When the cache_safe invariant is violated — any cache_safe=False
            segment appears at a list index ≤ the maximum index of any
            cache_safe=True segment.
    """
    if sections:
        _validate_cache_safe_invariant(sections)

    parts: list[str] = []
    for section in sections:
        if not section.enabled_when(ctx):
            continue
        rendered = section.render(ctx)
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts)


def resolve_effective_prompt(
    *,
    sections: Sequence[PromptSection],
    ctx: PromptContext,
    override: str | None,
) -> str:
    """Resolve the final system-prompt string from competing sources.

    Priority (mirrors CC buildEffectiveSystemPrompt):
      1. override (non-empty) — used by internal sub-agent fork paths and tests.
      2. Section assembly — the standard path for all product agents.

    Args:
        sections: Product + core sections for assembly.
        ctx: Frozen runtime context.
        override: Optional raw string that bypasses assembly entirely.  Empty /
            whitespace-only is treated as absent.

    Returns:
        Resolved system-prompt string.
    """
    if override and override.strip():
        return override
    return assemble_system_prompt(sections, ctx)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_cache_safe_invariant(sections: Sequence[PromptSection]) -> None:
    """Raise ValueError when any cache_safe=False segment is not in the volatile tail.

    The invariant guarantees that the stable prefix is always contiguous: every
    segment the provider can auto-prefix-cache appears before any volatile segment.
    A violation would silently shrink the cacheable prefix every time a volatile
    segment value changes.

    Validation is by list position (Decision 16 / M4): the index of every
    cache_safe=False segment must be strictly greater than the index of every
    cache_safe=True segment.

    Args:
        sections: Ordered sequence of sections to validate.

    Raises:
        ValueError: With a message listing the offending segment names.
    """
    stable_indices = [i for i, s in enumerate(sections) if s.cache_safe]
    volatile_sections_with_idx = [(i, s) for i, s in enumerate(sections) if not s.cache_safe]

    if not stable_indices or not volatile_sections_with_idx:
        return  # Nothing to violate.

    max_stable_idx = max(stable_indices)
    violators = [(i, s) for i, s in volatile_sections_with_idx if i <= max_stable_idx]
    if violators:
        names = ", ".join(f"{s.name}(idx={i})" for i, s in violators)
        raise ValueError(
            f"cache_safe invariant violated: cache_safe=False segments must appear "
            f"after all cache_safe=True segments (max stable idx={max_stable_idx}). "
            f"Violating segments: {names}"
        )
