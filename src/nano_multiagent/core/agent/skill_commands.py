"""Rewrite `/skill:*` shortcuts into explicit model instructions."""

import re

_SKILL_COMMAND_PATTERN = re.compile(
    r"^\s*/skill:(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\s+(?P<args>[\s\S]*\S))?\s*$"
)


def rewrite_skill_command(user_text: str) -> str:
    """Normalize slash-skill shortcuts into plain prompt text.

    Args:
        user_text: Raw user input text.

    Returns:
        Rewritten instruction when `/skill:<name>` matches; otherwise original text.
    """

    match = _SKILL_COMMAND_PATTERN.match(user_text)
    if match is None:
        return user_text

    skill_name = match.group("name")
    user_args = (match.group("args") or "").strip()
    rewritten = f'Use the "{skill_name}" skill for this request.'
    if user_args:
        return f"{rewritten}\nUser input:\n{user_args}"
    return rewritten
