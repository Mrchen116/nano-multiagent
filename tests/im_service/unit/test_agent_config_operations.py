"""Unit coverage for the shared Agent configuration operation projection."""

from pathlib import Path

import pytest

from IM.application.agent_config_operations import (
    candidate_fingerprint,
    gateway_candidate,
)
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agent_config_operations import (
    AgentConfigOperationPendingError,
    AgentConfigOperationRepository,
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


def test_active_operation_collision_returns_pending_instead_of_sqlite_error(
    tmp_path: Path,
) -> None:
    """A concurrent create receives the safe retryable operation state."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    repository = AgentConfigOperationRepository(connection)
    candidate = {"agent_id": "agent-1"}
    kwargs = {
        "agent_id": "agent-1",
        "owner_id": "owner-1",
        "node_id": "node-1",
        "operation_kind": "create",
        "candidate": candidate,
        "previous_candidate": None,
        "candidate_fingerprint": candidate_fingerprint(candidate),
        "expected_previous_fingerprint": None,
        "expected_profile_version": None,
    }
    repository.create(operation_id="operation-1", **kwargs)

    with pytest.raises(AgentConfigOperationPendingError, match="config_apply_pending"):
        repository.create(operation_id="operation-2", **kwargs)
