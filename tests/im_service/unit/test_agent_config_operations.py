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
from personal_assistant.gateway.agent_config_sync import agent_operation_fingerprint


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
        "skills_selection_mode": "explicit_allowlist",
        "tool_allowlist": ["read"],
        "group_reply_policy": "manual",
        "default_model": "model-a",
        "model_fallbacks": [],
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


@pytest.mark.parametrize(
    ("skills", "selection", "expected_mode"),
    [
        pytest.param(["plan"], {}, "explicit_allowlist", id="legacy-absent"),
        pytest.param(
            [],
            {"skills_selection_mode": None},
            "default_discovery",
            id="legacy-null",
        ),
        pytest.param(
            [],
            {"skills_selection_mode": "default_discovery"},
            "default_discovery",
            id="default-discovery",
        ),
        pytest.param(
            ["plan"],
            {"skills_selection_mode": "explicit_allowlist"},
            "explicit_allowlist",
            id="explicit-nonempty",
        ),
        pytest.param(
            [],
            {"skills_selection_mode": "explicit_allowlist"},
            "explicit_allowlist",
            id="explicit-empty",
        ),
    ],
)
def test_im_and_gateway_candidate_fingerprints_share_selection_schema(
    skills: list[str], selection: dict[str, object], expected_mode: str
) -> None:
    """Keep both sides of the config-operation fingerprint protocol identical."""
    candidate = {
        "agent_id": "agent-1",
        "display_name": "Agent One",
        "skills": skills,
        "tool_allowlist": ["read"],
        "group_reply_policy": "manual",
        "default_model": "model-a",
        "reasoning_effort": "high",
        "workspace_root": "/srv/agent-1",
        "features": {"heartbeat": True},
        "custom_prompt": None,
        "heartbeat_json": None,
        **selection,
    }

    projected = gateway_candidate(candidate)

    assert projected["skills_selection_mode"] == expected_mode
    assert candidate_fingerprint(candidate) == agent_operation_fingerprint(projected)


@pytest.mark.parametrize(
    ("skills", "effective_mode"),
    [
        pytest.param([], "default_discovery", id="legacy-empty"),
        pytest.param(["plan"], "explicit_allowlist", id="legacy-nonempty"),
    ],
)
def test_legacy_selection_fingerprint_matches_explicit_effective_mode(
    skills: list[str], effective_mode: str
) -> None:
    legacy = {"agent_id": "agent-1", "skills": skills}
    explicit = {
        **legacy,
        "skills_selection_mode": effective_mode,
    }

    assert candidate_fingerprint(legacy) == agent_operation_fingerprint(
        gateway_candidate(explicit)
    )


def test_explicit_empty_fingerprint_differs_from_default_discovery() -> None:
    candidate = {"agent_id": "agent-1", "skills": []}

    assert candidate_fingerprint(
        {**candidate, "skills_selection_mode": "explicit_allowlist"}
    ) != agent_operation_fingerprint(
        gateway_candidate({**candidate, "skills_selection_mode": "default_discovery"})
    )


def test_im_candidate_fingerprint_rejects_invalid_selection_mode() -> None:
    with pytest.raises(ValueError, match="invalid skills_selection_mode"):
        candidate_fingerprint(
            {
                "agent_id": "agent-1",
                "skills": [],
                "skills_selection_mode": "all_skills",
            }
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
