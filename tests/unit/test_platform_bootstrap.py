"""Unit tests: bootstrap_product returns a ResolvedProductConfig."""

from pathlib import Path

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
    assert resolved.session_store._data_dir.resolve() == (tmp_path / ".nano").resolve()


# ---------------------------------------------------------------------------
# R3 tests: bootstrap_product registers skill_manage + memory tools
# ---------------------------------------------------------------------------


def test_bootstrap_registers_skill_manage_when_config_resolver_available(tmp_path: Path) -> None:
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


def test_bootstrap_registers_memory_when_config_resolver_available(tmp_path: Path) -> None:
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


def test_bootstrap_default_session_metadata_no_workspace_config_uses_defaults(tmp_path: Path) -> None:
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
        yaml.safe_dump({"self_evolution": {"enabled": False, "skill_nudge_interval": 20}}),
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
