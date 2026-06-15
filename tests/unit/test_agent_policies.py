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


# R1: 默认值断言
def test_default_max_turns_is_10000() -> None:
    policies = AgentPolicies()

    assert policies.max_turns == 10_000


def test_default_max_context_messages_is_zero() -> None:
    policies = AgentPolicies()

    assert policies.max_context_messages == 0


def test_default_max_tool_calls_is_zero() -> None:
    # bugfix-412 #102: 默认 0 = 不限。工具调用上限交给消费者按场景注入，
    # core 不再替所有产品兜底一个 64 的硬天花板。
    policies = AgentPolicies()

    assert policies.max_tool_calls == 0


def test_ensure_tool_calls_allowed_unlimited_by_default() -> None:
    # 默认 policies 下，任意大的累计工具调用数都不触发 PolicyViolation。
    policies = AgentPolicies()

    policies.ensure_tool_calls_allowed(tool_call_count=10_000)


def test_ensure_tool_calls_allowed_unlimited_when_zero() -> None:
    policies = AgentPolicies(max_tool_calls=0)

    policies.ensure_tool_calls_allowed(tool_call_count=999)


def test_ensure_tool_calls_allowed_still_enforces_positive_limit() -> None:
    # 消费者显式传正整数时约束照常生效。
    policies = AgentPolicies(max_tool_calls=5)

    with pytest.raises(PolicyViolation, match="max_tool_calls"):
        policies.ensure_tool_calls_allowed(tool_call_count=6)


# R1: truncate_history 边界 bug 修复
def test_truncate_history_returns_original_when_max_context_messages_is_zero() -> None:
    """max_context_messages=0 表示无限制，应返回原始 messages，而非空元组。"""
    policies = AgentPolicies(max_context_messages=0)
    messages = ("m1", "m2", "m3")

    assert policies.truncate_history(messages) == messages


def test_truncate_history_returns_original_when_max_context_messages_is_negative() -> (
    None
):
    """max_context_messages<0 也视为无限制，返回原始 messages。"""
    policies = AgentPolicies(max_context_messages=-1)
    messages = ("m1", "m2", "m3")

    assert policies.truncate_history(messages) == messages
