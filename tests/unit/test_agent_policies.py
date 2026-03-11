import pytest

from agent.core.agent.policies import AgentPolicies
from agent.core.errors import PolicyViolation


def test_ensure_turn_allowed_raises_when_turn_budget_exceeded() -> None:
    policies = AgentPolicies(max_turns=1)

    with pytest.raises(PolicyViolation, match="max_turns"):
        policies.ensure_turn_allowed(turn_count=1)


def test_truncate_history_keeps_recent_items() -> None:
    policies = AgentPolicies(max_context_messages=2)

    assert policies.truncate_history(("m1", "m2", "m3")) == ("m2", "m3")


def test_ensure_tool_calls_allowed_raises_when_tool_call_budget_exceeded() -> None:
    policies = AgentPolicies(max_tool_calls=1)

    with pytest.raises(PolicyViolation, match="max_tool_calls"):
        policies.ensure_tool_calls_allowed(tool_call_count=2)


def test_ensure_tool_calls_allowed_accepts_tool_call_count_at_limit() -> None:
    policies = AgentPolicies(max_tool_calls=1)

    policies.ensure_tool_calls_allowed(tool_call_count=1)
