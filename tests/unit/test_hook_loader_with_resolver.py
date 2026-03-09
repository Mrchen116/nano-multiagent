"""Unit tests for hooks/loader ConfigResolver integration.

Verifies that build_hook_registry uses resolver-specified hook roots when a
ConfigResolver is provided, and falls back to .nano/hooks otherwise.
"""

from pathlib import Path

from nano_multiagent.hooks.loader import build_hook_registry
from nano_multiagent.platform.config.resolver import ConfigResolver
from nano_multiagent.products.base import ProductProfile


_HOOK_CODE = """
def setup(hooks):
    def my_hook(event, ctx):
        pass
    hooks.on("turn_start", my_hook)
"""


def _make_resolver(global_home: Path, workspace_root: Path | None = None) -> ConfigResolver:
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=global_home,
        workspace_config_dirname=".testprod",
        session_db_filename="sessions.sqlite3",
        compat_skill_roots=[],
    )
    return ConfigResolver(profile=profile, workspace_root=workspace_root)


def test_build_hook_registry_uses_resolver_workspace_hook_root(tmp_path: Path) -> None:
    """build_hook_registry loads workspace hooks from resolver-specified directory."""
    hook_dir = tmp_path / ".testprod" / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "my_hook.py").write_text(_HOOK_CODE)

    resolver = _make_resolver(global_home=tmp_path / ".global", workspace_root=tmp_path)
    registry = build_hook_registry(repo_root=tmp_path, config_resolver=resolver)

    # Verify hook was registered (turn.start listener present)
    hooks = registry.handlers_for("turn_start")
    assert len(hooks) >= 1
    assert any(h.source == "workspace" for h in hooks)


def test_build_hook_registry_uses_resolver_global_hook_root(tmp_path: Path) -> None:
    """build_hook_registry loads hooks from resolver global hook dir."""
    global_hook_dir = tmp_path / ".global" / "hooks"
    global_hook_dir.mkdir(parents=True)
    (global_hook_dir / "global_hook.py").write_text(_HOOK_CODE)

    resolver = _make_resolver(global_home=tmp_path / ".global")
    # No workspace root → only global hook root used
    registry = build_hook_registry(repo_root=tmp_path, config_resolver=resolver)

    hooks = registry.handlers_for("turn_start")
    assert len(hooks) >= 1
    assert any(h.source == "workspace" for h in hooks)


def test_build_hook_registry_falls_back_to_nano_hooks(tmp_path: Path) -> None:
    """Without config_resolver, hooks loaded from legacy .nano/hooks path."""
    hook_dir = tmp_path / ".nano" / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "legacy_hook.py").write_text(_HOOK_CODE)

    # No resolver: falls back to .nano/hooks
    registry = build_hook_registry(repo_root=tmp_path)
    hooks = registry.handlers_for("turn_start")
    # Should find the workspace hook (legacy path)
    assert any(h.source == "workspace" for h in hooks)


def test_build_hook_registry_with_resolver_does_not_load_nano_hooks(tmp_path: Path) -> None:
    """When resolver is provided, legacy .nano/hooks dir is NOT searched."""
    legacy_dir = tmp_path / ".nano" / "hooks"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "legacy_hook.py").write_text(_HOOK_CODE)

    # No hooks in resolver paths → turn.start should only have builtin hooks
    resolver = _make_resolver(global_home=tmp_path / ".global", workspace_root=tmp_path)
    registry = build_hook_registry(repo_root=tmp_path, config_resolver=resolver)
    hooks = registry.handlers_for("turn_start")
    # All workspace hooks should come from resolver-specified dirs (not .nano/hooks)
    for h in hooks:
        if h.source == "workspace":
            assert h.file_path is not None
            assert str(h.file_path).startswith(str(tmp_path / ".testprod"))
