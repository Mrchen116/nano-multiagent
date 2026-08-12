"""Provider-neutral turn attachments for Workflow opt-in."""

from __future__ import annotations

from collections.abc import Sequence
import re

from agent.core.llm.interfaces import LLMMessage
from agent.core.types import ToolSpec

from .runtime import OutputTokenBudget


WORKFLOW_KEYWORD_REMINDER = (
    'The user included the keyword "ultracode", opting this turn into multi-agent '
    "orchestration — use the Workflow tool to fulfill the request."
)
WORKFLOW_STANDING_REMINDER = (
    "Ultracode is on: optimize for the most exhaustive, correct answer — not the "
    "fastest or cheapest. Use the Workflow tool on every substantive task; token "
    "cost is not a constraint. See the Workflow tool's **Ultracode** section and "
    "quality patterns. Solo only on conversational/trivial turns."
)
_TOKEN_TARGET_RE = re.compile(r"(?<!\w)\+(\d+)([kKmM])\b")


def output_token_budget_for_turn(
    *, origin: str | None, human_text: str
) -> OutputTokenBudget | None:
    """Parse a trusted-human ``+500k`` style shared output target."""

    if origin != "human":
        return None
    match = _TOKEN_TARGET_RE.search(human_text)
    if match is None:
        return None
    multiplier = 1_000 if match.group(2).casefold() == "k" else 1_000_000
    return OutputTokenBudget(total=int(match.group(1)) * multiplier)


def append_workflow_turn_reminder(
    messages: list[LLMMessage],
    *,
    active_tools: Sequence[ToolSpec],
    origin: str | None,
    human_text: str,
    standing: bool,
) -> None:
    """Append the exact trusted-human/standing reminder after the current input."""

    if not any(tool.name == "Workflow" for tool in active_tools):
        return
    reminders: list[str] = []
    if origin == "human" and "ultracode" in human_text.casefold():
        reminders.append(WORKFLOW_KEYWORD_REMINDER)
    if standing:
        reminders.append(WORKFLOW_STANDING_REMINDER)
    if reminders:
        messages.append(LLMMessage(role="turn_system", content="\n\n".join(reminders)))
