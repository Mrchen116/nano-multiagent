"""Unit tests: bootstrap_product returns a ResolvedProductConfig."""

from pathlib import Path

import pytest

from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.types import HookEventMode
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.bootstrap import _filter_hook_registry, bootstrap_product
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


def test_bootstrap_product_resolved_system_prompt_matches_profile(
    tmp_path: Path,
) -> None:
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


def test_filter_hook_registry_preserves_background_mode(tmp_path: Path) -> None:
    """_filter_hook_registry must carry the ``mode`` field through filtering.

    Regression for feat-349 round 1 Issue #1: dropping ``mode`` re-registered the
    self_improvement BACKGROUND hook as OBSERVE, so ``fork_conversation`` was never
    injected and the self-evolution flow never fired.
    """

    async def _bg_handler(ctx):  # pragma: no cover - never invoked in this test
        return None

    full = HookRegistry()
    full.on(
        "agent_end",
        _bg_handler,
        mode=HookEventMode.BACKGROUND,
        module_name="self_improvement",
        file_path=Path("self_improvement.py"),
    )

    filtered = _filter_hook_registry(full, ["self_improvement"])

    background = filtered.background_handlers_for("agent_end")
    assert len(background) == 1, "background-mode hook must survive filtering"
    assert background[0].mode == HookEventMode.BACKGROUND
    # And it must not leak into the blocking observe/intercept dispatch path.
    assert filtered.handlers_for("agent_end") == ()


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
    assert (
        resolved.config_resolver.workspace_config_root() == tmp_path / ".test-workspace"
    )
    assert (
        resolved.config_resolver.global_config_root()
        == (tmp_path / ".test-global").resolve()
    )


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
    # Stateless store: no fixed data_dir default base. Production callers must
    # pass workspace_root on every path-resolving call; there is no cwd fallback.
    assert resolved.session_store._data_dir is None


def test_session_jsonl_falls_in_workspace_root_not_process_cwd(tmp_path: Path) -> None:
    """session JSONL must land in workspace_root/.nano/sessions/, not process cwd/.nano/sessions/.

    bugfix-348: this was the root cause — store used process cwd instead of workspace_root.
    """
    from agent.core.session.manager import SessionManager

    workspace_root = tmp_path / "my-agent-workspace"
    workspace_root.mkdir()

    # data_dir=None — stateless store; create() resolves the path from
    # SessionConfig.workspace_root, no caller-passed workspace_root needed.
    store = JsonlSessionStore(data_dir=None)
    manager = SessionManager(store=store)

    session = manager.create_session(workspace_root=workspace_root)

    expected_path = (
        workspace_root / ".nano" / "sessions" / f"{session.session_id}.jsonl"
    )
    assert expected_path.exists(), (
        f"JSONL must be at {{workspace_root}}/.nano/sessions/{{session_id}}.jsonl, "
        f"but not found at {expected_path}"
    )

    # Sanity: must NOT be in process cwd
    import os

    wrong_path = (
        Path(os.getcwd()) / ".nano" / "sessions" / f"{session.session_id}.jsonl"
    )
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

    store = JsonlSessionStore(data_dir=None)
    manager = SessionManager(store=store)

    sess1 = manager.create_session(workspace_root=ws1)
    sess2 = manager.create_session(workspace_root=ws2)

    assert (ws1 / ".nano" / "sessions" / f"{sess1.session_id}.jsonl").exists()
    assert (ws2 / ".nano" / "sessions" / f"{sess2.session_id}.jsonl").exists()
    # Each session must not appear in the other workspace
    assert not (ws2 / ".nano" / "sessions" / f"{sess1.session_id}.jsonl").exists()
    assert not (ws1 / ".nano" / "sessions" / f"{sess2.session_id}.jsonl").exists()


def test_stateless_store_load_and_append_with_caller_workspace_root(
    tmp_path: Path,
) -> None:
    """load() and append() work when the caller passes workspace_root explicitly."""
    from agent.core.session.manager import SessionManager

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    store = JsonlSessionStore(data_dir=None)
    manager = SessionManager(store=store)

    session = manager.create_session(
        workspace_root=workspace_root, title="test-session"
    )

    # load must succeed when the caller supplies workspace_root
    result = store.load(session.session_id, workspace_root=workspace_root)
    assert result.config.session_id == session.session_id
    assert result.config.workspace_root == workspace_root

    # append must write to the same workspace-scoped file
    store.append(
        session.session_id,
        {
            "type": "turn",
            "uuid": "msg_1",
            "role": "user",
            "content": "hi",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
        workspace_root=workspace_root,
    )
    store.writer.flush()
    result2 = store.load(session.session_id, workspace_root=workspace_root)
    assert len(result2.messages) == 1


def test_stateless_store_load_survives_process_restart(tmp_path: Path) -> None:
    """A session written by a previous process must still load() after restart.

    bugfix-348: the kernel is stateless — it holds no session_id -> workspace_root
    mapping. A brand-new store (fresh process, no cache) must still load and
    append to an old session as long as the caller supplies the workspace_root,
    which the gateway/CLI always know.
    """
    from agent.core.session.manager import SessionManager

    workspace_root = tmp_path / "agent-workspace"
    workspace_root.mkdir()

    # --- process lifetime A: create + write a turn ---
    store_a = JsonlSessionStore(data_dir=None)
    manager_a = SessionManager(store=store_a)
    session = manager_a.create_session(
        workspace_root=workspace_root, title="cross-restart"
    )
    store_a.append(
        session.session_id,
        {
            "type": "turn",
            "uuid": "msg_a",
            "role": "user",
            "content": "hello from A",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
        workspace_root=workspace_root,
    )
    store_a.writer.flush()
    del store_a, manager_a  # simulate kernel process exit

    # --- process lifetime B: brand-new store, no in-process state at all ---
    store_b = JsonlSessionStore(data_dir=None)

    # load() succeeds because the caller passes workspace_root (no kernel state).
    result = store_b.load(session.session_id, workspace_root=workspace_root)
    assert result.config.session_id == session.session_id
    assert result.config.workspace_root == workspace_root
    assert [m.content for m in result.messages] == ["hello from A"]

    # resolve_path points at the original workspace, not raises.
    resolved = store_b.resolve_path(session.session_id, workspace_root=workspace_root)
    assert (
        resolved
        == workspace_root / ".nano" / "sessions" / f"{session.session_id}.jsonl"
    )

    # append() after restart keeps writing to the same file.
    store_b.append(
        session.session_id,
        {
            "type": "turn",
            "uuid": "msg_b",
            "parent_uuid": "msg_a",
            "role": "assistant",
            "content": "hello from B",
            "timestamp": "2026-01-01T00:01:00+00:00",
        },
        workspace_root=workspace_root,
    )
    store_b.writer.flush()
    result2 = store_b.load(session.session_id, workspace_root=workspace_root)
    assert [m.content for m in result2.messages] == ["hello from A", "hello from B"]


def test_stateless_store_raises_without_workspace_root_and_without_data_dir(
    tmp_path: Path,
) -> None:
    """A data_dir=None store must raise loudly when the caller omits workspace_root.

    No silent cwd fallback — that silent fallback is exactly the bugfix-348 bug.
    """
    from agent.core.session.jsonl_store import SessionNotFoundError

    store = JsonlSessionStore(data_dir=None)
    with pytest.raises(SessionNotFoundError):
        store.load("sess_whatever")  # no workspace_root, no data_dir
    with pytest.raises(SessionNotFoundError):
        store.resolve_path("sess_whatever")


def test_stateless_store_raises_when_jsonl_missing_workspace_root_field(
    tmp_path: Path,
) -> None:
    """A JSONL whose session_created entry omits workspace_root must raise loudly.

    Same-family bug as bugfix-348: silently filling the missing field with
    Path.cwd() splits a session across two physical files on the next append
    (old messages stay in the original workspace, new messages land under cwd).
    No backward compatibility — malformed files are rejected at load time.
    """
    import json
    from agent.core.session.jsonl_store import SessionNotFoundError

    workspace_root = tmp_path / "ws"
    sessions_dir = workspace_root / ".nano" / "sessions"
    sessions_dir.mkdir(parents=True)
    jsonl_path = sessions_dir / "sess_legacy.jsonl"
    # Simulate a pre-bugfix-348 file: session_created entry without workspace_root.
    jsonl_path.write_text(
        json.dumps(
            {
                "type": "session_created",
                "session_id": "sess_legacy",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    store = JsonlSessionStore(data_dir=None)
    with pytest.raises(SessionNotFoundError, match="missing required 'workspace_root'"):
        store.load("sess_legacy", workspace_root=workspace_root)


def test_stateless_store_list_sessions_scoped_to_workspace_root(tmp_path: Path) -> None:
    """list_session_ids is scoped to the workspace_root the caller passes."""
    from agent.core.session.manager import SessionManager

    ws1 = tmp_path / "ws-1"
    ws2 = tmp_path / "ws-2"
    ws1.mkdir()
    ws2.mkdir()

    store = JsonlSessionStore(data_dir=None)
    manager = SessionManager(store=store)
    sess1 = manager.create_session(workspace_root=ws1)
    sess2 = manager.create_session(workspace_root=ws2)

    # A brand-new store (fresh process) lists ws1's sessions when scoped to ws1.
    fresh = JsonlSessionStore(data_dir=None)
    listed_ws1 = fresh.list_session_ids(limit=10, offset=0, workspace_root=ws1)
    listed_ws2 = fresh.list_session_ids(limit=10, offset=0, workspace_root=ws2)
    assert sess1.session_id in listed_ws1
    assert sess1.session_id not in listed_ws2
    assert sess2.session_id in listed_ws2
    assert sess2.session_id not in listed_ws1


# ---------------------------------------------------------------------------
# R3 tests: bootstrap_product registers skill_manage + memory tools
# ---------------------------------------------------------------------------


def test_bootstrap_registers_skill_manage_when_config_resolver_available(
    tmp_path: Path,
) -> None:
    """When global_config_home + workspace_config_dirname are set, skill_manage is in the registry."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=tmp_path / ".test-global",
        workspace_config_dirname=".test-workspace",
        default_tool_ids=["read", "bash", "skill_manage", "memory"],
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    tool_names = {spec.name for spec in resolved.tool_registry.list_specs()}
    assert "skill_manage" in tool_names


def test_bootstrap_registers_memory_when_config_resolver_available(
    tmp_path: Path,
) -> None:
    """When global_config_home + workspace_config_dirname are set, memory is in the registry."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=tmp_path / ".test-global",
        workspace_config_dirname=".test-workspace",
        default_tool_ids=["read", "bash", "skill_manage", "memory"],
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    tool_names = {spec.name for spec in resolved.tool_registry.list_specs()}
    assert "memory" in tool_names


def test_bootstrap_default_session_metadata_no_workspace_config_uses_defaults(
    tmp_path: Path,
) -> None:
    """When no workspace config file exists, default_session_metadata.self_evolution is all-enabled."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=tmp_path / ".test-global",
        workspace_config_dirname=".test-workspace",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    self_evo = resolved.default_session_metadata.get("self_evolution", {})
    assert self_evo.get("enabled", True) is True


def test_bootstrap_reads_self_evolution_from_workspace_config(tmp_path: Path) -> None:
    """When workspace config file exists with self_evolution section, it is loaded into metadata."""
    import yaml

    config_dir = tmp_path / ".test-workspace"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        yaml.safe_dump(
            {"self_evolution": {"enabled": False, "skill_nudge_interval": 20}}
        ),
        encoding="utf-8",
    )

    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=tmp_path / ".test-global",
        workspace_config_dirname=".test-workspace",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    self_evo = resolved.default_session_metadata.get("self_evolution", {})
    assert self_evo.get("enabled") is False
    assert self_evo.get("skill_nudge_interval") == 20
