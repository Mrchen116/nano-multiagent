"""Gateway-local Agent ID immutability and create recovery."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

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


def test_create_retry_without_operation_id_rejects_legacy_agent(
    tmp_path: Path,
) -> None:
    """Reject no-id retries against an existing legacy Gateway Agent."""
    sync, owners = _build_sync(tmp_path)
    workspace = tmp_path / "retry-root"
    first = sync.handle_agent_create(
        {"agent_id": "retry-agent", "workspace_root": str(workspace)}
    )
    sentinel = workspace / "keep.txt"
    sentinel.write_text("keep\n", encoding="utf-8")

    retried = sync.handle_agent_create(
        {"agent_id": "retry-agent", "workspace_root": str(workspace)}
    )

    assert first["agent_id"] == "retry-agent"
    assert retried == {
        "error": {
            "code": "agent_id_already_exists",
            "detail": "Agent ID already exists on this node.",
        }
    }
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert owners.catalog.require("retry-agent").config.workspace_root == workspace


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


def test_concurrent_divergent_creates_cannot_replace_same_local_agent_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serialize the local check-and-publish boundary for one Agent ID."""
    sync, owners = _build_sync(tmp_path)
    first_publish_entered = threading.Event()
    release_first_publish = threading.Event()
    second_publish_entered = threading.Event()
    original_publish = sync._publish_agent_config  # noqa: SLF001
    publish_count = 0
    publish_count_lock = threading.Lock()

    def controlled_publish(config: AgentWorkspaceConfig) -> None:
        nonlocal publish_count
        with publish_count_lock:
            publish_count += 1
            call_number = publish_count
        if config.agent_id == "race-agent" and call_number == 1:
            first_publish_entered.set()
            assert release_first_publish.wait(timeout=2)
        elif config.agent_id == "race-agent":
            second_publish_entered.set()
        original_publish(config)

    monkeypatch.setattr(sync, "_publish_agent_config", controlled_publish)
    roots = [tmp_path / "race-root-1", tmp_path / "race-root-2"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            sync.handle_agent_create,
            {"agent_id": "race-agent", "workspace_root": str(roots[0])},
        )
        assert first_publish_entered.wait(timeout=2)
        second_future = executor.submit(
            sync.handle_agent_create,
            {"agent_id": "race-agent", "workspace_root": str(roots[1])},
        )
        assert not second_publish_entered.wait(timeout=0.1)
        release_first_publish.set()
        results = [first_future.result(timeout=2), second_future.result(timeout=2)]

    assert results[0]["workspace_root"] == str(roots[0].resolve())
    assert results[1] == {
        "error": {
            "code": "agent_id_already_exists",
            "detail": "Agent ID already exists on this node.",
        }
    }
    assert owners.catalog.require("race-agent").config.workspace_root == roots[0]
    assert not roots[1].exists()
