"""Unit tests: bootstrap_product returns a ResolvedProductConfig."""

from pathlib import Path

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.bootstrap import bootstrap_product
from agent.products.base import ProductProfile, ResolvedProductConfig


def test_bootstrap_product_returns_resolved_config(tmp_path: Path) -> None:
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        default_system_prompt="You are a test assistant.",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert isinstance(resolved, ResolvedProductConfig)


def test_bootstrap_product_resolved_system_prompt_matches_profile(tmp_path: Path) -> None:
    expected_prompt = "You are a test assistant."
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        default_system_prompt=expected_prompt,
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.resolved_system_prompt == expected_prompt


def test_bootstrap_product_resolved_config_has_product_id(tmp_path: Path) -> None:
    profile = ProductProfile(
        product_id="my_product",
        display_name="My Product",
        config_namespace="myproduct",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.product_id == "my_product"


def test_bootstrap_product_tool_registry_not_none(tmp_path: Path) -> None:
    """bootstrap_product must wire a ToolRegistry (not None) for the product."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.tool_registry is not None


def test_bootstrap_product_hook_registry_not_none(tmp_path: Path) -> None:
    """bootstrap_product must wire a HookRegistry (not None) for the product."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.hook_registry is not None


def test_bootstrap_respects_default_tool_ids(tmp_path: Path) -> None:
    """bootstrap_product filters to only declared tool ids when default_tool_ids is set."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        default_tool_ids=["read", "bash"],
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.tool_registry is not None
    tool_names = {spec.name for spec in resolved.tool_registry.list_specs()}
    assert "read" in tool_names
    assert "bash" in tool_names
    # write, edit, task are NOT in the declared list, so must be excluded.
    assert "write" not in tool_names
    assert "edit" not in tool_names
    assert "task" not in tool_names


def test_bootstrap_product_exposes_config_resolver(tmp_path: Path) -> None:
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=tmp_path / ".test-global",
        workspace_config_dirname=".test-workspace",
    )

    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)

    assert resolved.config_resolver is not None
    assert resolved.config_resolver.workspace_config_root() == tmp_path / ".test-workspace"
    assert resolved.config_resolver.global_config_root() == (tmp_path / ".test-global").resolve()


def test_bootstrap_product_builds_profile_session_store(tmp_path: Path) -> None:
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=tmp_path / ".test-global",
        workspace_config_dirname=".test-workspace",
        session_db_filename="profile.sqlite3",
    )

    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)

    assert isinstance(resolved.session_store, JsonlSessionStore)
    # workspace-aware mode: no fixed data_dir — sessions resolve per workspace_root
    assert resolved.session_store._data_dir is None


def test_session_jsonl_falls_in_workspace_root_not_process_cwd(tmp_path: Path) -> None:
    """session JSONL must land in workspace_root/.nano/sessions/, not process cwd/.nano/sessions/.

    bugfix-348: this was the root cause — store used process cwd instead of workspace_root.
    """
    from agent.core.session.manager import SessionManager

    workspace_root = tmp_path / "my-agent-workspace"
    workspace_root.mkdir()

    store = JsonlSessionStore(data_dir=None)  # workspace-aware mode
    manager = SessionManager(store=store)

    session = manager.create_session(workspace_root=workspace_root)

    expected_path = workspace_root / ".nano" / "sessions" / f"{session.session_id}.jsonl"
    assert expected_path.exists(), (
        f"JSONL must be at {{workspace_root}}/.nano/sessions/{{session_id}}.jsonl, "
        f"but not found at {expected_path}"
    )

    # Sanity: must NOT be in process cwd
    import os
    wrong_path = Path(os.getcwd()) / ".nano" / "sessions" / f"{session.session_id}.jsonl"
    assert not wrong_path.exists(), (
        f"JSONL must not fall in process cwd, but found at {wrong_path}"
    )


def test_workspace_aware_store_multiple_workspaces_isolated(tmp_path: Path) -> None:
    """Sessions from different workspace_roots must land in their respective dirs."""
    from agent.core.session.manager import SessionManager

    ws1 = tmp_path / "workspace-agent-1"
    ws2 = tmp_path / "workspace-agent-2"
    ws1.mkdir()
    ws2.mkdir()

    store = JsonlSessionStore(data_dir=None)  # workspace-aware mode
    manager = SessionManager(store=store)

    sess1 = manager.create_session(workspace_root=ws1)
    sess2 = manager.create_session(workspace_root=ws2)

    assert (ws1 / ".nano" / "sessions" / f"{sess1.session_id}.jsonl").exists()
    assert (ws2 / ".nano" / "sessions" / f"{sess2.session_id}.jsonl").exists()
    # Each session must not appear in the other workspace
    assert not (ws2 / ".nano" / "sessions" / f"{sess1.session_id}.jsonl").exists()
    assert not (ws1 / ".nano" / "sessions" / f"{sess2.session_id}.jsonl").exists()


def test_workspace_aware_store_load_and_append_after_create(tmp_path: Path) -> None:
    """load() and append() must work for sessions created in workspace-aware mode."""
    from agent.core.session.manager import SessionManager

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    store = JsonlSessionStore(data_dir=None)
    manager = SessionManager(store=store)

    session = manager.create_session(workspace_root=workspace_root, title="test-session")

    # load must succeed without error
    result = store.load(session.session_id)
    assert result.config.session_id == session.session_id
    assert result.config.workspace_root == workspace_root

    # append must not raise
    store.append(session.session_id, {"type": "turn", "uuid": "msg_1", "role": "user", "content": "hi", "timestamp": "2026-01-01T00:00:00+00:00"})
    import time; time.sleep(0.05)  # give writer thread time to flush
    store.writer.flush()
    result2 = store.load(session.session_id)
    assert len(result2.messages) == 1
