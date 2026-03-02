from dataclasses import fields

from nano_multiagent.agent.policies import AgentPolicies
from nano_multiagent.agent.state import AgentState, InputPart


def test_input_part_fields_are_stable() -> None:
    assert [field.name for field in fields(InputPart)] == [
        "type",
        "text",
        "image_url",
        "mime_type",
        "metadata",
    ]


def test_agent_state_fields_are_stable() -> None:
    assert [field.name for field in fields(AgentState)] == [
        "session_id",
        "turn_id",
        "turn_count",
        "history_messages",
        "input_parts",
        "user_text",
    ]


def test_agent_policies_fields_are_stable() -> None:
    assert [field.name for field in fields(AgentPolicies)] == [
        "max_turns",
        "max_context_messages",
        "max_tool_calls",
    ]
