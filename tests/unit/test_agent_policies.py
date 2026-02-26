import pytest

from nano_multiagent.agent.policies import AgentPolicies
from nano_multiagent.core.errors import PolicyViolation


def test_ensure_turn_allowed_raises_when_turn_budget_exceeded() -> None:
    policies = AgentPolicies(max_turns=1)

    with pytest.raises(PolicyViolation, match="max_turns"):
        policies.ensure_turn_allowed(turn_count=1)


def test_truncate_history_keeps_recent_items() -> None:
    policies = AgentPolicies(max_context_messages=2)

    assert policies.truncate_history(("m1", "m2", "m3")) == ("m2", "m3")
