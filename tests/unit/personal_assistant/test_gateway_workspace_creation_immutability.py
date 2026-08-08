"""Gateway-local Agent ID immutability and create recovery."""

from pathlib import Path

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from .test_gateway_workspace_creation import _build_sync


def test_create_rejects_existing_agent_id_before_initializing_a_new_root(
    tmp_path: Path,
) -> None:
    """An Agent's first Gateway-local workspace remains fixed across create retries."""
    fixed_root = tmp_path / "fixed-root"
    fixed_root.mkdir()
    existing = AgentWorkspaceConfig(
        agent_id="fixed-agent",
        workspace_root=fixed_root,
        workspace_is_default=False,
    )
    sync, owners = _build_sync(tmp_path, agents=(existing,))
    replacement_root = tmp_path / "replacement-root"

    result = sync.handle_agent_create(
        {
            "agent_id": "fixed-agent",
            "workspace_root": str(replacement_root),
        }
    )

    assert result == {
        "error": {
            "code": "agent_id_already_exists",
            "detail": "Agent ID already exists on this node.",
        }
    }
    assert not replacement_root.exists()
    assert owners.catalog.require("fixed-agent").config.workspace_root == fixed_root
    assert not (tmp_path / "config.yaml").exists()


def test_create_retry_requires_the_original_durable_operation_id(
    tmp_path: Path,
) -> None:
    """Gateway exposes a local create result only to its original IM operation."""
    sync, _owners = _build_sync(tmp_path)
    workspace = tmp_path / "operation-root"

    first = sync.handle_agent_create(
        {
            "agent_id": "operation-agent",
            "workspace_root": str(workspace),
            "create_operation_id": "op-original",
        }
    )
    retry = sync.handle_agent_create(
        {
            "agent_id": "operation-agent",
            "workspace_root": str(workspace),
            "create_operation_id": "op-original",
        }
    )
    wrong_operation = sync.handle_agent_create(
        {
            "agent_id": "operation-agent",
            "workspace_root": str(workspace),
            "create_operation_id": "op-other",
        }
    )
    missing_operation = sync.handle_agent_create(
        {
            "agent_id": "operation-agent",
            "workspace_root": str(workspace),
        }
    )

    assert first["create_operation_id"] == "op-original"
    assert retry["create_operation_id"] == "op-original"
    assert wrong_operation == {
        "error": {
            "code": "agent_id_already_exists",
            "detail": "Agent ID already exists on this node.",
        }
    }
    assert missing_operation == wrong_operation
