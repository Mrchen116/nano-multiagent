"""Kernel template skeleton — product-neutral fixed-order prompt assembly (refactor-406 决策 8).

The kernel owns one fixed-order template skeleton shared by every product. Core
behaviour rules, the two general feature-guidance segments (memory/skill), the
background-task framing, the runtime footer and the volatile memory/profile tail
are kernel-owned segments (unchanged from core_sections). Product-specific text
enters through four slots on ``PromptContext.prompt_slots`` (an SDK-owned
``PromptSlots``, read structurally so core stays sdk-independent — 决策 2):

    head slot
    CORE_SYSTEM / CORE_ACTIONS_CARE / CORE_TOOL_RULES / CORE_TONE_STYLE
    body slot
    CORE_SKILLS_LISTING / CORE_MEMORY_GUIDANCE / CORE_SKILLS_GUIDANCE
    CORE_BACKGROUND_TASKS / CORE_RUNTIME_FOOTER
    custom slot
    CORE_MEMORY_BLOCK / CORE_USER_PROFILE_BLOCK   (volatile)
    tail slot                                     (volatile)

This order reproduces the existing PA/LC assembly byte-for-byte (refactor-406
risk 1, golden-守); slot pieces join with their neighbours via the same ``\\n\\n``
rule as kernel segments. Product gating (cron only when enabled, group context
only for group chats) is done by the consumer factory when it builds PromptSlots;
the skeleton only places already-gated slot text.

Pure core module: no imports from platform / products / sdk.
"""

from __future__ import annotations

from typing import Sequence

from agent.core.agent.prompt_sections.base import PromptContext, PromptSection
from agent.core.agent.prompt_sections.core_sections import (
    CORE_ACTIONS_CARE,
    CORE_BACKGROUND_TASKS,
    CORE_MEMORY_BLOCK,
    CORE_MEMORY_GUIDANCE,
    CORE_RUNTIME_FOOTER,
    CORE_SKILLS_GUIDANCE,
    CORE_SKILLS_LISTING,
    CORE_SYSTEM,
    CORE_TONE_STYLE,
    CORE_TOOL_RULES,
    CORE_USER_PROFILE_BLOCK,
)


def _slot_pieces(ctx: PromptContext, slot_name: str) -> Sequence:
    """Return the PromptText pieces for one slot, read structurally from ctx.

    Reads ``ctx.prompt_slots.<slot_name>`` duck-typed (each piece exposes
    ``.name`` / ``.text``). Returns an empty tuple when no slots are present or
    the slot is unset — the slot then contributes nothing to the prompt.
    """
    slots = ctx.prompt_slots
    if slots is None:
        return ()
    pieces = getattr(slots, slot_name, None)
    return pieces or ()


def _make_slot_section(slot_name: str, *, cache_safe: bool) -> PromptSection:
    """Build a PromptSection that renders one slot's pieces in order.

    Pieces join with ``\\n\\n`` (same as the top-level assembler joins segments),
    so a multi-piece slot reproduces the legacy multi-segment layout byte-for-byte.
    Empty/whitespace-only piece text is dropped (matches the kernel omit rule).
    """

    def _render(ctx: PromptContext) -> str | None:
        parts = [
            piece.text
            for piece in _slot_pieces(ctx, slot_name)
            if getattr(piece, "text", "") and piece.text.strip()
        ]
        if not parts:
            return None
        return "\n\n".join(parts)

    return PromptSection(
        name=f"slot.{slot_name}",
        render=_render,
        cache_safe=cache_safe,
    )


# Slot sections. head/body/custom live in the stable cache prefix (cache_safe);
# tail lives in the volatile tail after the kernel memory/profile blocks
# (cache_safe=False) — group communication context belongs there (对齐现状
# pa.communication_context 位置, bugfix-358).
_SLOT_HEAD = _make_slot_section("head", cache_safe=True)
_SLOT_BODY = _make_slot_section("body", cache_safe=True)
_SLOT_CUSTOM = _make_slot_section("custom", cache_safe=True)
_SLOT_TAIL = _make_slot_section("tail", cache_safe=False)


# The single product-neutral template skeleton (fixed order). Product text comes
# only from the four slot sections; everything else is kernel-owned.
KERNEL_PROMPT_SKELETON: tuple[PromptSection, ...] = (
    # head: product identity / persona
    _SLOT_HEAD,
    # core behaviour rules (CC-aligned, kernel-owned)
    CORE_SYSTEM,
    CORE_ACTIONS_CARE,
    CORE_TOOL_RULES,
    CORE_TONE_STYLE,
    # body: product behaviour guidance (cron/heartbeat/guidelines/routing/…)
    _SLOT_BODY,
    # general feature guidance (gated by feature flag + tool presence, kernel-owned)
    CORE_SKILLS_LISTING,
    CORE_MEMORY_GUIDANCE,
    CORE_SKILLS_GUIDANCE,
    # background-task framing + runtime footer (kernel-owned)
    CORE_BACKGROUND_TASKS,
    CORE_RUNTIME_FOOTER,
    # custom: user custom instructions (stable-prefix tail)
    _SLOT_CUSTOM,
    # volatile tail (kernel-owned, cache_safe=False)
    CORE_MEMORY_BLOCK,
    CORE_USER_PROFILE_BLOCK,
    # tail: product volatile content (group communication context)
    _SLOT_TAIL,
)


def build_kernel_prompt_skeleton() -> list[PromptSection]:
    """Return the kernel's fixed-order template skeleton section list.

    The list is product-neutral: product text is supplied per-session via
    ``PromptContext.prompt_slots`` (an SDK-owned ``PromptSlots``). Feed the
    returned list to ``assemble_system_prompt`` together with a PromptContext
    whose ``prompt_slots`` carries the product's head/body/custom/tail pieces.

    Returns:
        Ordered list of PromptSection objects (kernel segments + slot sections).
    """
    return list(KERNEL_PROMPT_SKELETON)
