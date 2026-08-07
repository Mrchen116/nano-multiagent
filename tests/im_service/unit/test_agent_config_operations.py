"""Unit coverage for the shared Agent configuration operation projection."""

from IM.application.agent_config_operations import (
    candidate_fingerprint,
    gateway_candidate,
)


def test_gateway_candidate_uses_gateway_canonical_values() -> None:
    candidate = {
        "agent_id": " agent-1 ",
        "display_name": " Agent One ",
        "skills": [" plan ", "", 1],
        "tool_allowlist": [" read "],
        "group_reply_policy": " manual ",
        "default_model": " model-a ",
        "reasoning_effort": " high ",
        "workspace_root": "/srv/agent-1",
        "features": {"heartbeat": True, "bad": "yes"},
        "custom_prompt": "",
        "heartbeat_json": '{"every": "30m", "active_hours": null}',
    }

    assert gateway_candidate(candidate) == {
        "agent_id": "agent-1",
        "display_name": "Agent One",
        "skills": ["plan"],
        "tool_allowlist": ["read"],
        "group_reply_policy": "manual",
        "default_model": "model-a",
        "reasoning_effort": "high",
        "workspace_root": "/srv/agent-1",
        "features": {"heartbeat": True},
        "custom_prompt": None,
        "heartbeat_json": '{"active_hours":null,"every":"30m"}',
    }


def test_omitted_create_skills_have_a_distinct_fingerprint() -> None:
    candidate = {"agent_id": "agent-1"}

    assert "skills" not in gateway_candidate(candidate)
    assert candidate_fingerprint(candidate) != candidate_fingerprint(
        {**candidate, "skills": []}
    )
