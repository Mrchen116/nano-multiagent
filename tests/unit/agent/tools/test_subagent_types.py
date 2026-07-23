"""内置子 agent 类型目录：解析 / deny 求交 / 未知类型文案（feat-474 M1 R1）。"""

from __future__ import annotations

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.subagent_types import (
    apply_tool_deny,
    format_available_agents,
    iter_agent_types,
    resolve_agent_type,
)


def test_default_resolves_to_general_purpose() -> None:
    definition = resolve_agent_type(None)
    assert definition.name == "general-purpose"
    assert definition.disallowed_tools == frozenset()


@pytest.mark.parametrize("name", ["general-purpose", "Explore", "Plan"])
def test_known_types_resolve_by_exact_name(name: str) -> None:
    definition = resolve_agent_type(name)
    assert definition.name == name


@pytest.mark.parametrize("name", ["oracle", "explore", "PLAN", "general_purpose"])
def test_unknown_or_wrong_case_names_fail_with_available_agents(name: str) -> None:
    with pytest.raises(ToolError) as exc_info:
        resolve_agent_type(name)
    assert "not found" in str(exc_info.value)
    assert "Available agents: general-purpose, Explore, Plan" in str(exc_info.value)
    assert exc_info.value.details["code"] == "unknown_agent_type"


def test_explore_and_plan_deny_write_edit_agent_skill_manage() -> None:
    for name in ("Explore", "Plan"):
        definition = resolve_agent_type(name)
        assert definition.disallowed_tools == frozenset(
            {"write", "edit", "agent", "skill_manage"}
        )


def test_apply_tool_deny_preserves_parent_order_and_drops_denied() -> None:
    parent_tools = ["read", "write", "bash", "edit", "agent", "web_fetch"]
    result = apply_tool_deny(parent_tools, frozenset({"write", "edit", "agent"}))
    assert result == ["read", "bash", "web_fetch"]


def test_apply_tool_deny_with_empty_denylist_returns_full_parent_set() -> None:
    parent_tools = ["read", "write", "bash"]
    assert apply_tool_deny(parent_tools, frozenset()) == parent_tools


def test_format_available_agents_lists_in_stable_registration_order() -> None:
    assert (
        format_available_agents()
        == "Available agents: general-purpose, Explore, Plan"
    )


def test_role_prompt_seeds_are_distinct_and_read_only_types_avoid_gp_copy() -> None:
    seeds = {d.name: d.role_prompt_seed for d in iter_agent_types()}
    assert len(seeds) == 3
    for name in ("Explore", "Plan"):
        body_text = " ".join(item.text for item in seeds[name].body)
        assert "READ-ONLY" in body_text
    gp_body = " ".join(item.text for item in seeds["general-purpose"].body)
    assert "READ-ONLY" not in gp_body
