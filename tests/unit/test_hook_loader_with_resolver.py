"""Unit tests for hooks/loader ConfigResolver integration.

Verifies that build_hook_registry uses resolver-specified hook roots when a
ConfigResolver is provided, and falls back to .nano/hooks otherwise.
"""

from pathlib import Path

from agent.platform.hooks.loader import build_hook_registry
from agent.platform.config.resolver import ConfigResolver
from agent.products.base import ProductProfile


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


def test_build_hook_registry_includes_product_root_between_builtin_and_user_layers(tmp_path: Path) -> None:
    product_dir = tmp_path / "products" / "sample" / "hooks"
    product_dir.mkdir(parents=True)
    (product_dir / "product_hook.py").write_text(_HOOK_CODE)

    resolver = _make_resolver(global_home=tmp_path / ".global", workspace_root=tmp_path)
    registry = build_hook_registry(
        repo_root=tmp_path,
        config_resolver=resolver,
        product_hook_dir=product_dir,
    )

    hooks = registry.handlers_for("turn_start")
    assert any(h.file_path == product_dir / "product_hook.py" for h in hooks if h.file_path is not None)


def test_build_hook_registry_workspace_overrides_product_hook_module(tmp_path: Path) -> None:
    product_dir = tmp_path / "products" / "sample" / "hooks"
    product_dir.mkdir(parents=True)
    (product_dir / "shared_hook.py").write_text(_HOOK_CODE)
    workspace_dir = tmp_path / ".testprod" / "hooks"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "shared_hook.py").write_text(_HOOK_CODE)

    resolver = _make_resolver(global_home=tmp_path / ".global", workspace_root=tmp_path)
    registry = build_hook_registry(
        repo_root=tmp_path,
        config_resolver=resolver,
        product_hook_dir=product_dir,
    )

    shared_hooks = [
        h for h in registry.handlers_for("turn_start") if h.file_path is not None and h.file_path.name == "shared_hook.py"
    ]
    assert len(shared_hooks) == 1
    assert shared_hooks[0].file_path == workspace_dir / "shared_hook.py"


def test_build_hook_registry_global_overrides_product_hook_when_workspace_missing(tmp_path: Path) -> None:
    product_dir = tmp_path / "products" / "sample" / "hooks"
    product_dir.mkdir(parents=True)
    (product_dir / "shared_hook.py").write_text(_HOOK_CODE)
    global_dir = tmp_path / ".global" / "hooks"
    global_dir.mkdir(parents=True)
    (global_dir / "shared_hook.py").write_text(_HOOK_CODE)

    resolver = _make_resolver(global_home=tmp_path / ".global", workspace_root=tmp_path)
    registry = build_hook_registry(
        repo_root=tmp_path,
        config_resolver=resolver,
        product_hook_dir=product_dir,
    )

    shared_hooks = [
        h for h in registry.handlers_for("turn_start") if h.file_path is not None and h.file_path.name == "shared_hook.py"
    ]
    assert len(shared_hooks) == 1
    assert shared_hooks[0].file_path == global_dir / "shared_hook.py"
