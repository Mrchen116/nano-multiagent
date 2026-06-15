"""SDK-owned prompt slot value objects (refactor-406 决策 8).

`PromptSlots` is the public contract by which a consumer's factory feeds its
product-specific system-prompt text into the kernel's template skeleton. The
kernel owns the fixed-order skeleton (head → core 行为规则 → body → 通用 feature
指引 → 后台/footer → custom → 内核易变尾部 → tail); the product fills four slots
with already-gated plain text.

These types are SDK-owned (their ``__module__`` is ``agent.sdk.*``) so the
public-surface ownership guard (决策 7) passes. The kernel skeleton reads slots
**structurally** (duck-typed ``.head`` / ``.body`` / ``.custom`` / ``.tail``)
rather than importing this module, mirroring the Tool/ToolContext/HookAPI
Protocol approach (决策 2) — this avoids a core→sdk import inversion.

All slots are **per-session**: the consumer factory builds the PromptSlots once
per session (cron/heartbeat guidance → body, group context → tail) and the kernel
assembles them into the system prompt once at session start; the product never
injects into the system prompt per-turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptText:
    """A single named piece of product prompt text within a slot.

    Each ``PromptText`` becomes one segment in the assembled prompt, joined to
    its neighbours with a blank line (``\\n\\n``), exactly like a kernel segment.
    Splitting a slot into several ``PromptText`` entries (rather than one big
    string) lets the product reproduce the existing multi-segment layout
    byte-for-byte (e.g. identity + runtime as two head pieces).

    Args:
        name: Stable identifier for tracing/preview (e.g. ``"pa.identity"``).
            Not rendered into the prompt text itself.
        text: The rendered segment text. Empty / whitespace-only text is dropped
            during assembly (the slot entry contributes nothing), matching the
            kernel's "render returned empty → omit" rule.
    """

    name: str
    text: str


@dataclass(frozen=True)
class PromptSlots:
    """Product-supplied, per-session system-prompt content for the four slots.

    The kernel template skeleton places each slot at a fixed position:

    - ``head``: product identity / persona, before the core behaviour rules.
    - ``body``: product behaviour guidance (e.g. cron/heartbeat指引, guidelines,
      routing), after the core rules and inside the stable cache prefix.
    - ``custom``: user-supplied custom instructions, in the stable-prefix tail
      (after footer, before the kernel's volatile tail).
    - ``tail``: content that must land after the kernel's volatile tail (group
      chat communication context — volatile, may change turn-to-turn).

    Each slot is a sequence of ``PromptText`` (possibly empty). The product is
    responsible for gating: only include the cron piece when cron is enabled,
    the group context only for group conversations, etc. The kernel does not
    re-gate slot content; it only places it.

    Args:
        head: Identity / persona pieces.
        body: Behaviour-guidance pieces (stable prefix).
        custom: User custom-instruction pieces (stable-prefix tail).
        tail: Volatile-tail pieces (group context).
    """

    head: tuple[PromptText, ...] = field(default_factory=tuple)
    body: tuple[PromptText, ...] = field(default_factory=tuple)
    custom: tuple[PromptText, ...] = field(default_factory=tuple)
    tail: tuple[PromptText, ...] = field(default_factory=tuple)


__all__ = ["PromptSlots", "PromptText"]
