"""Unit tests for skills/workspace ConfigResolver integration.

Verifies that default_skill_search_roots uses resolver-specified skill roots
when a ConfigResolver is provided, and falls back to CODEX_HOME env behavior.
"""

from pathlib import Path

from nano_multiagent.platform.config.resolver import ConfigResolver
from nano_multiagent.products.base import ProductProfile
from nano_multiagent.skills.workspace import default_skill_search_roots


def _make_resolver(
    global_home: Path,
    workspace_root: Path | None = None,
    compat_skill_roots: list[Path] | None = None,
) -> ConfigResolver:
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=global_home,
        workspace_config_dirname=".testprod",
        session_db_filename="sessions.sqlite3",
        compat_skill_roots=compat_skill_roots or [],
    )
    return ConfigResolver(profile=profile, workspace_root=workspace_root)


def test_default_skill_search_roots_uses_resolver(tmp_path: Path) -> None:
    """default_skill_search_roots returns resolver roots when resolver provided."""
    resolver = _make_resolver(
        global_home=tmp_path / ".global",
        workspace_root=tmp_path,
    )
    roots = default_skill_search_roots(workspace_root=tmp_path, config_resolver=resolver)
    # workspace comes first
    assert roots[0] == tmp_path / ".testprod" / "skills"
    # global comes second
    assert roots[1] == (tmp_path / ".global" / "skills").resolve()


def test_default_skill_search_roots_includes_compat(tmp_path: Path) -> None:
    """Compat skill roots appear after global when resolver provided."""
    compat = tmp_path / "compat_skills"
    resolver = _make_resolver(
        global_home=tmp_path / ".global",
        workspace_root=tmp_path,
        compat_skill_roots=[compat],
    )
    roots = default_skill_search_roots(workspace_root=tmp_path, config_resolver=resolver)
    assert compat.resolve() in roots
    # compat should be after global
    global_idx = roots.index((tmp_path / ".global" / "skills").resolve())
    compat_idx = roots.index(compat.resolve())
    assert compat_idx > global_idx


def test_default_skill_search_roots_falls_back(tmp_path: Path, monkeypatch) -> None:
    """Without resolver, legacy CODEX_HOME behavior is used."""
    fake_codex = tmp_path / "codex_home"
    monkeypatch.setenv("CODEX_HOME", str(fake_codex))
    roots = default_skill_search_roots(workspace_root=tmp_path)
    # legacy behavior: codex_home/skills appears
    assert fake_codex / "skills" in roots


def test_default_skill_search_roots_no_duplicates_with_resolver(tmp_path: Path) -> None:
    """Resolver roots are deduplicated (compat == global is not doubled)."""
    global_home = tmp_path / ".global"
    compat = global_home / "skills"  # same as global skill root
    resolver = _make_resolver(
        global_home=global_home,
        compat_skill_roots=[compat],
    )
    roots = default_skill_search_roots(workspace_root=tmp_path, config_resolver=resolver)
    count = sum(1 for r in roots if r == global_home.resolve() / "skills")
    assert count == 1
