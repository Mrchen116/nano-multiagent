"""Unit tests: bootstrap_product returns a ResolvedProductConfig."""

from pathlib import Path

from nano_multiagent.platform.bootstrap import bootstrap_product
from nano_multiagent.platform.persistence.session.sqlite_store import SQLiteSessionStore
from nano_multiagent.products.base import ProductProfile, ResolvedProductConfig


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

    assert isinstance(resolved.session_store, SQLiteSessionStore)
    assert resolved.session_store._db_path.resolve() == (tmp_path / ".test-global" / "profile.sqlite3").resolve()
