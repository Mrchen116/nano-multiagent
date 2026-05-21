"""Core prompt-section data structures and assembler.

Design decisions captured here:
- Decision 1: explicit order: int for global sort (core + product segments interleave).
- Decision 2: PromptSection is a pure data + two pure functions; no side effects.
  PromptContext is a frozen dataclass (assembly-time read-only snapshot).
- Decision 8: cache_safe=False segments must have order > every cache_safe=True
  segment — enforced at assembly time so the stable prefix is always contiguous
  and provider auto-prefix-cache hit rate is maximised.
- Decision 9: resolve_effective_prompt is the single resolution point: override
  direct-pass (internal / sub-agent fork) beats section assembly.

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
        memory_block: Pre-rendered MemoryStore snapshot, or None when absent.
            Volatile (changes turn to turn) — passed to cache_safe=False segment.
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
    flags: Mapping[str, bool] = field(default_factory=dict)
    scenario: Mapping[str, object] = field(default_factory=dict)
    vars: Mapping[str, str] = field(default_factory=dict)

    def has_tool(self, name: str) -> bool:
        """Return True when a tool with the given name is active this turn."""
        return any(getattr(t, "name", None) == name for t in self.available_tools)


@dataclass(frozen=True)
class PromptSection:
    """A single named, ordered, gate-controlled segment of the system prompt.

    Segments are pure-data objects — render and enabled_when are pure functions
    that receive PromptContext and produce deterministic output (no IO, no state).

    Args:
        name: Stable internal identifier (e.g. "core.system", "pa.identity").
            Not rendered into the prompt text; used for ordering and registry
            references.  Convention: ``<layer>.<semantic_name>``.
        order: Integer position in the global ordered sequence.  Segments from
            core and product packages are sorted together by (order, name) so
            product segments can interleave with core segments intentionally.
            Number bands (see design.md decision 1):
              100–199  product identity + runtime
              200–299  core behaviour rules (system/actions/tools/tone)
              300–399  product lore (memory / heartbeat / policy / guidelines)
              400–499  tool + skill listings
              500–599  self-evolution guidance (user-togglable)
              700–799  mechanism segments (background tasks / footer)
              800      user custom instructions (stable-prefix tail)
              900+     volatile tail (cache_safe=False)
        render: ``(ctx) -> str | None``.  Returns the rendered text for this
            segment, or None / empty string to omit it entirely this turn.
        enabled_when: ``(ctx) -> bool``.  When False the segment is skipped
            without calling render.  Defaults to always-enabled.
        cache_safe: When True the segment's content is stable across turns and
            contributes to the provider's auto-prefix-cache stable prefix.
            When False the segment may change turn-to-turn (e.g. MemoryStore
            snapshot, live participant list) and must be ordered after all
            cache_safe=True segments (decision 8; enforced by assemble_system_prompt).
    """

    name: str
    order: int
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
    1. Validate the cache_safe invariant (decision 8): every cache_safe=False
       segment must have order strictly greater than every cache_safe=True segment.
       Raises ValueError on violation so mis-wired segments are loud failures,
       not silent cache degradations.
    2. Sort sections by (order, name) — stable, deterministic.
    3. For each section: skip if not enabled_when(ctx); call render(ctx); skip if
       result is None or empty.
    4. Join surviving pieces with "\n\n".

    Args:
        sections: Unordered collection of PromptSection objects (core + product).
        ctx: Frozen runtime snapshot for this turn.

    Returns:
        Fully assembled system-prompt string.  Empty string when all sections
        are absent/disabled.

    Raises:
        ValueError: When the cache_safe invariant is violated — a cache_safe=False
            segment has order ≤ the maximum order of any cache_safe=True segment.
    """
    if sections:
        _validate_cache_safe_invariant(sections)

    ordered = sorted(sections, key=lambda s: (s.order, s.name))
    parts: list[str] = []
    for section in ordered:
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

    Priority (decision 9 — mirrors CC buildEffectiveSystemPrompt):
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
    """Raise ValueError when any cache_safe=False segment has order ≤ max stable order.

    The invariant guarantees that the stable prefix is always contiguous: every
    segment the provider can auto-prefix-cache appears before any volatile segment.
    A violation would silently shrink the cacheable prefix every time a volatile
    segment value changes.

    Args:
        sections: Sections to validate (may be unordered).

    Raises:
        ValueError: With a message listing the offending segment names.
    """
    stable_orders = [s.order for s in sections if s.cache_safe]
    volatile_sections = [s for s in sections if not s.cache_safe]

    if not stable_orders or not volatile_sections:
        return  # Nothing to violate.

    max_stable_order = max(stable_orders)
    violators = [s for s in volatile_sections if s.order <= max_stable_order]
    if violators:
        names = ", ".join(f"{s.name}(order={s.order})" for s in violators)
        raise ValueError(
            f"cache_safe invariant violated: cache_safe=False segments must have "
            f"order > max cache_safe=True order ({max_stable_order}). "
            f"Violating segments: {names}"
        )
