"""Gateway-local workspace creation behavior."""

from pathlib import Path

import pytest

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    GatewayLifecycleConfig,
    HeartbeatConfig,
    LocalConfig,
    NodeConfig,
    load_local_config,
)
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
import personal_assistant.gateway.agent_config_sync as agent_config_sync_module
from tests.unit.personal_assistant._config_sync_test_owners import (
    build_config_sync_test_owners,
)


def _build_sync(
    tmp_path: Path,
    *,
    agents: tuple[AgentWorkspaceConfig, ...] = (),
) -> tuple[IMAgentConfigSync, object]:
    seed = tmp_path / "seed"
    seed.mkdir(exist_ok=True)
    initial_agents = agents or (
        AgentWorkspaceConfig(agent_id="seed", workspace_root=seed),
    )
    config = LocalConfig(
        node=NodeConfig(node_id="node-a"),
        agents=initial_agents,
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=LLMConfigPayload(
            default_model="test-model",
            providers=(
                LLMProviderPayload(
                    name="test",
                    base_url="http://127.0.0.1:4000",
                    models=(LLMModelPayload(name="test-model"),),
                ),
            ),
        ),
        source_path=tmp_path / "config.yaml",
    )
    owners = build_config_sync_test_owners(config)
    base = tmp_path / "default-workspaces"
    sync = IMAgentConfigSync(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=config,
        workspace_root_factory=lambda agent_id: base / agent_id,
    )
    return sync, owners


def test_default_and_new_custom_workspace_record_canonical_root_and_source(
    tmp_path: Path,
) -> None:
    """Create default/custom roots with Gateway-owned canonical provenance."""
    sync, owners = _build_sync(tmp_path)

    default = sync.handle_agent_create({"agent_id": "default-agent"})
    (tmp_path / "projects").mkdir()
    custom_path = tmp_path / "projects" / ".." / "custom-agent"
    custom = sync.handle_agent_create(
        {"agent_id": "custom-agent", "workspace_root": str(custom_path)}
    )

    assert default["workspace_root"] == str(
        (tmp_path / "default-workspaces" / "default-agent").resolve()
    )
    assert default["workspace_is_default"] is True
    assert custom["workspace_root"] == str(custom_path.resolve())
    assert custom["workspace_is_default"] is False
    assert owners.catalog.require("default-agent").config.workspace_is_default is True
    assert owners.catalog.require("custom-agent").config.workspace_is_default is False
    persisted = load_local_config(tmp_path / "config.yaml")
    sources = {item.agent_id: item.workspace_is_default for item in persisted.agents}
    assert sources["default-agent"] is True
    assert sources["custom-agent"] is False


def test_custom_workspace_rejects_invalid_parent_and_non_directory_target(
    tmp_path: Path,
) -> None:
    """Reject invalid custom targets before config or workspace initialization."""
    sync, owners = _build_sync(tmp_path)
    missing_target = tmp_path / "missing-parent" / "agent"
    file_target = tmp_path / "not-a-directory"
    file_target.write_text("data", encoding="utf-8")

    missing = sync.handle_agent_create(
        {"agent_id": "missing", "workspace_root": str(missing_target)}
    )
    not_directory = sync.handle_agent_create(
        {"agent_id": "file", "workspace_root": str(file_target)}
    )

    assert missing == {
        "error": {
            "code": "workspace_parent_missing",
            "detail": "Workspace parent directory does not exist.",
        }
    }
    assert not_directory == {
        "error": {
            "code": "workspace_target_not_directory",
            "detail": "Workspace target exists but is not a directory.",
        }
    }
    assert not missing_target.exists()
    assert owners.catalog.get("missing") is None
    assert owners.catalog.get("file") is None


def test_custom_workspace_rejects_unusable_parent_without_creating_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report an unusable existing parent before attempting target creation."""
    sync, owners = _build_sync(tmp_path)
    parent = tmp_path / "read-only-parent"
    parent.mkdir()
    target = parent / "agent"
    monkeypatch.setattr(agent_config_sync_module.os, "access", lambda *_args: False)

    result = sync.handle_agent_create(
        {"agent_id": "unusable", "workspace_root": str(target)}
    )

    assert result == {
        "error": {
            "code": "workspace_parent_unusable",
            "detail": "Workspace parent directory is not usable.",
        }
    }
    assert not target.exists()
    assert owners.catalog.get("unusable") is None


def test_initialization_failure_does_not_publish_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return a typed error when workspace defaults cannot be initialized."""
    sync, owners = _build_sync(tmp_path)
    target = tmp_path / "initialization-fails"

    def _fail_initialization(_workspace: Path) -> Path:
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(
        agent_config_sync_module, "ensure_workspace_defaults", _fail_initialization
    )

    result = sync.handle_agent_create(
        {"agent_id": "init-fails", "workspace_root": str(target)}
    )

    assert result == {
        "error": {
            "code": "workspace_initialization_failed",
            "detail": "Workspace could not be initialized on the selected node.",
        }
    }
    assert owners.catalog.get("init-fails") is None


def test_existing_workspace_requires_confirmation_then_preserves_files(
    tmp_path: Path,
) -> None:
    """Leave existing directories untouched until an explicit confirmation retry."""
    sync, owners = _build_sync(tmp_path)
    workspace = tmp_path / "existing-project"
    workspace.mkdir()
    existing = workspace / "README.md"
    existing.write_text("keep me\n", encoding="utf-8")

    first = sync.handle_agent_create(
        {"agent_id": "existing", "workspace_root": str(workspace)}
    )

    assert first == {
        "error": {
            "code": "workspace_confirmation_required",
            "detail": "Workspace target is an existing directory and requires confirmation.",
        }
    }
    assert not (workspace / ".nanoassistant").exists()
    assert not (workspace / "HEARTBEAT.md").exists()
    assert owners.catalog.get("existing") is None

    confirmed = sync.handle_agent_create(
        {
            "agent_id": "existing",
            "workspace_root": str(workspace),
            "confirm_existing_workspace": True,
        }
    )

    assert confirmed["workspace_root"] == str(workspace.resolve())
    assert confirmed["workspace_is_default"] is False
    assert existing.read_text(encoding="utf-8") == "keep me\n"
    assert (workspace / ".nanoassistant" / "memory" / "MEMORY.md").is_file()


def test_canonical_workspace_root_is_unique_within_one_gateway(tmp_path: Path) -> None:
    """Reject aliases of a canonical root already owned by a local agent."""
    owned = tmp_path / "owned"
    owned.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(owned, target_is_directory=True)
    existing = AgentWorkspaceConfig(
        agent_id="owner-agent",
        workspace_root=owned,
        workspace_is_default=False,
    )
    sync, owners = _build_sync(tmp_path, agents=(existing,))

    result = sync.handle_agent_create(
        {
            "agent_id": "other-agent",
            "workspace_root": str(alias),
            "confirm_existing_workspace": True,
        }
    )

    assert result == {
        "error": {
            "code": "workspace_already_assigned",
            "detail": "Workspace is already assigned to another Agent.",
            "agent_id": "owner-agent",
        }
    }
    assert owners.catalog.get("other-agent") is None


def test_workspace_ownership_is_scoped_to_each_gateway_config(tmp_path: Path) -> None:
    """Allow another node-local config to adopt the same path after confirmation."""
    workspace = tmp_path / "shared-string-path"
    workspace.mkdir()
    owner = AgentWorkspaceConfig(
        agent_id="node-a-agent",
        workspace_root=workspace,
        workspace_is_default=False,
    )
    node_a_root = tmp_path / "node-a"
    node_a_root.mkdir()
    _node_a_sync, _node_a_owners = _build_sync(node_a_root, agents=(owner,))
    node_b_root = tmp_path / "node-b"
    node_b_root.mkdir()
    node_b_sync, node_b_owners = _build_sync(node_b_root)

    result = node_b_sync.handle_agent_create(
        {
            "agent_id": "node-b-agent",
            "workspace_root": str(workspace),
            "confirm_existing_workspace": True,
        }
    )

    assert result["workspace_root"] == str(workspace.resolve())
    assert node_b_owners.catalog.require("node-b-agent").config.workspace_root == workspace


def test_preview_workspace_resolution_uses_gateway_paths_without_initializing(
    tmp_path: Path,
) -> None:
    """Resolve preview paths on the node without creating workspace content."""
    sync, _owners = _build_sync(tmp_path)
    custom = tmp_path / "custom-preview"

    default_root = sync.resolve_preview_workspace(
        workspace_mode="default",
        agent_id_hint="preview-agent",
        workspace_root=None,
    )
    custom_root = sync.resolve_preview_workspace(
        workspace_mode="custom",
        agent_id_hint="preview-agent",
        workspace_root=str(custom),
    )

    assert default_root == str(
        (tmp_path / "default-workspaces" / "preview-agent").resolve()
    )
    assert custom_root == str(custom.resolve())
    assert not Path(default_root).exists()
    assert not custom.exists()
