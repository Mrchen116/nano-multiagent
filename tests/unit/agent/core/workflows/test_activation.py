from agent.core.llm.interfaces import LLMMessage
from agent.core.types import ToolSpec
from agent.core.workflows import (
    WORKFLOW_KEYWORD_REMINDER,
    WORKFLOW_STANDING_REMINDER,
    append_workflow_turn_reminder,
    output_token_budget_for_turn,
)


WORKFLOW = ToolSpec(name="Workflow", description="", input_schema={})


def _messages() -> list[LLMMessage]:
    return [LLMMessage(role="user", content="please ultracode this")]


def test_inactive_or_nonhuman_keyword_never_attaches_reminder() -> None:
    inactive = _messages()
    append_workflow_turn_reminder(
        inactive,
        active_tools=(),
        origin="human",
        human_text="please ultracode this",
        standing=True,
    )
    nonhuman = _messages()
    append_workflow_turn_reminder(
        nonhuman,
        active_tools=(WORKFLOW,),
        origin="user",
        human_text="please ultracode this",
        standing=False,
    )

    assert [item.role for item in inactive] == ["user"]
    assert [item.role for item in nonhuman] == ["user"]


def test_human_keyword_and_standing_append_one_ordered_turn_system() -> None:
    messages = _messages()
    append_workflow_turn_reminder(
        messages,
        active_tools=(WORKFLOW,),
        origin="human",
        human_text="please ultracode this",
        standing=True,
    )

    assert [item.role for item in messages] == ["user", "turn_system"]
    assert messages[-1].content == (
        WORKFLOW_KEYWORD_REMINDER + "\n\n" + WORKFLOW_STANDING_REMINDER
    )


def test_active_without_opt_in_has_no_reminder_and_standing_is_exact() -> None:
    ordinary = [LLMMessage(role="user", content="review this")]
    append_workflow_turn_reminder(
        ordinary,
        active_tools=(WORKFLOW,),
        origin="human",
        human_text="review this",
        standing=False,
    )
    standing = [LLMMessage(role="user", content="review this")]
    append_workflow_turn_reminder(
        standing,
        active_tools=(WORKFLOW,),
        origin="human",
        human_text="review this",
        standing=True,
    )

    assert [item.role for item in ordinary] == ["user"]
    assert [item.role for item in standing] == ["user", "turn_system"]
    assert standing[-1].content == WORKFLOW_STANDING_REMINDER


def test_only_trusted_human_turn_creates_output_token_target() -> None:
    budget = output_token_budget_for_turn(
        origin="human", human_text="use workflow +500k"
    )

    assert budget is not None
    assert budget.total == 500_000
    assert (
        output_token_budget_for_turn(origin="user", human_text="use workflow +500k")
        is None
    )
