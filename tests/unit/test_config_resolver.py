"""Unit tests for ConfigResolver path resolution logic.

Tests verify resolver methods return correct paths with workspace/global/compat
precedence, and that resolver without workspace_root gracefully omits workspace paths.
"""

from pathlib import Path

import pytest

from agent.platform.config.resolver import ConfigResolver
from agent.products.base import ProductProfile


def _make_profile(
    *,
    global_config_home: Path | None = None,
    workspace_config_dirname: str = ".testproduct",
    session_db_filename: str = "sessions.sqlite3",
    compat_skill_roots: list[Path] | None = None,
) -> ProductProfile:
    return ProductProfile(
        product_id="test_product",
        display_name="Test Product",
        config_namespace="testproduct",
        global_config_home=global_config_home or Path("~/.testproduct"),
        workspace_config_dirname=workspace_config_dirname,
        session_db_filename=session_db_filename,
        compat_skill_roots=compat_skill_roots or [],
    )


def test_global_config_root_expands_home() -> None:
    profile = _make_profile(global_config_home=Path("~/.myproduct"))
    resolver = ConfigResolver(profile=profile)
    result = resolver.global_config_root()
    assert result.is_absolute()
    assert not str(result).startswith("~")
    assert result.name == ".myproduct"


def test_session_db_path_always_in_global_dir() -> None:
    profile = _make_profile(
        global_config_home=Path("~/.myproduct"),
        session_db_filename="sessions.sqlite3",
    )
    resolver = ConfigResolver(profile=profile)
    db_path = resolver.session_db_path()
    global_root = resolver.global_config_root()
    assert db_path == global_root / "sessions.sqlite3"
    assert db_path.parent == global_root


def test_session_db_filename_respected() -> None:
    profile = _make_profile(session_db_filename="custom.db")
    resolver = ConfigResolver(profile=profile)
    assert resolver.session_db_path().name == "custom.db"


def test_user_tool_roots_workspace_first(tmp_path: Path) -> None:
    profile = _make_profile(workspace_config_dirname=".myproduct")
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    roots = resolver.user_tool_roots()
    assert len(roots) >= 2
    # workspace comes first
    assert roots[0] == tmp_path / ".myproduct" / "tools"
    # global comes second
    assert roots[1] == resolver.global_config_root() / "tools"


def test_user_hook_roots_workspace_first(tmp_path: Path) -> None:
    profile = _make_profile(workspace_config_dirname=".myproduct")
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    roots = resolver.user_hook_roots()
    assert len(roots) >= 2
    assert roots[0] == tmp_path / ".myproduct" / "hooks"
    assert roots[1] == resolver.global_config_root() / "hooks"


def test_user_skill_roots_workspace_global_compat(tmp_path: Path) -> None:
    compat = Path("~/.codex/skills")
    profile = _make_profile(
        workspace_config_dirname=".myproduct",
        compat_skill_roots=[compat],
    )
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    roots = resolver.user_skill_roots()
    # workspace > global > compat
    assert roots[0] == tmp_path / ".myproduct" / "skills"
    assert roots[1] == resolver.global_config_root() / "skills"
    assert roots[2] == compat.expanduser().resolve()


def test_resolver_without_workspace_root() -> None:
    """When no workspace_root, workspace-relative paths are omitted."""
    profile = _make_profile()
    resolver = ConfigResolver(profile=profile)
    # tool roots: only global (no workspace)
    tool_roots = resolver.user_tool_roots()
    global_tools = resolver.global_config_root() / "tools"
    assert global_tools in tool_roots
    # no workspace path in roots
    for r in tool_roots:
        assert ".testproduct" not in str(r) or str(r) == str(global_tools)


def test_user_skill_roots_no_workspace_no_compat() -> None:
    """Without workspace or compat roots, only global skill root is returned."""
    profile = _make_profile(compat_skill_roots=[])
    resolver = ConfigResolver(profile=profile)
    roots = resolver.user_skill_roots()
    assert len(roots) == 1
    assert roots[0] == resolver.global_config_root() / "skills"


def test_user_skill_roots_compat_deduped() -> None:
    """Compat root equal to global is not added twice."""
    profile = _make_profile(compat_skill_roots=[Path("~/.testproduct/skills")])
    resolver = ConfigResolver(profile=profile)
    roots = resolver.user_skill_roots()
    # global root is ~/.testproduct/skills, compat is same - should appear once
    global_skills = resolver.global_config_root() / "skills"
    count = sum(1 for r in roots if r == global_skills)
    assert count == 1
