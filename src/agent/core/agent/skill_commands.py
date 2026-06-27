"""Rewrite `/skill:*` shortcuts into explicit model instructions."""

import re

# feat-430 决策5: a command may be preceded by an optional `[..]` annotation segment.
# This is a product-agnostic command-parsing convention — the kernel does not parse
# the segment's content and preserves it verbatim (IM groups put `[sender] ` there).
# Constraint (fix-r2 / code-review P2.6): the segment is a SINGLE `[...]` with no inner
# `]` (`[^\]]*`). A sender display name containing `]` (e.g. `[User [VIP]]`) would not
# match and the command degrades to a no-op rewrite (the literal `/skill:...` is sent,
# which the agent can still interpret). We deliberately do NOT use a greedy `\[.*\]`:
# that would mis-absorb earlier bracketed text on the line as the annotation segment.
# A structured sender field was rejected (design-review #4) as worse cross-layer coupling.
_SKILL_COMMAND_PATTERN = re.compile(
    r"^\s*(?P<prefix>\[[^\]]*\]\s*)?"
    r"/skill:(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\s+(?P<args>[\s\S]*\S))?\s*$"
)


def rewrite_skill_command(user_text: str) -> str:
    """Normalize slash-skill shortcuts into plain prompt text.

    Args:
        user_text: Raw user input text.

    Returns:
        Rewritten instruction when `/skill:<name>` matches; otherwise original text.
        A leading `[..]` annotation segment (if present) is preserved before the
        rewritten instruction so the receiving Agent still sees it (feat-430).
    """

    match = _SKILL_COMMAND_PATTERN.match(user_text)
    if match is None:
        return user_text

    prefix = match.group("prefix") or ""
    skill_name = match.group("name")
    user_args = (match.group("args") or "").strip()
    rewritten = f'{prefix}Use the "{skill_name}" skill for this request.'
    if user_args:
        return f"{rewritten}\nUser input:\n{user_args}"
    return rewritten
