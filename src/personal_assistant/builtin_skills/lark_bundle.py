"""Declare the Lark skills shipped with the personal assistant."""

from __future__ import annotations


LARK_SKILL_NAMES: tuple[str, ...] = (
    "lark-approval",
    "lark-apps",
    "lark-attendance",
    "lark-base",
    "lark-calendar",
    "lark-contact",
    "lark-doc",
    "lark-drive",
    "lark-event",
    "lark-im",
    "lark-mail",
    "lark-markdown",
    "lark-minutes",
    "lark-note",
    "lark-okr",
    "lark-openapi-explorer",
    "lark-shared",
    "lark-sheets",
    "lark-skill-maker",
    "lark-slides",
    "lark-task",
    "lark-vc",
    "lark-vc-agent",
    "lark-whiteboard",
    "lark-wiki",
    "lark-workflow-meeting-summary",
    "lark-workflow-standup-report",
)
"""Stable names for the complete packaged Lark capability bundle."""


def lark_skill_names() -> tuple[str, ...]:
    """Return the packaged Lark skill names in their stable install order."""

    return LARK_SKILL_NAMES
