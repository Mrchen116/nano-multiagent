"""Verify platform/hooks is importable with builtins and loader."""


def test_platform_hooks_builtins_importable() -> None:
    """After migration, builtins must be importable from the platform/hooks path."""
    from nano_multiagent.platform.hooks import builtins  # noqa: F401



def test_platform_hooks_loader_importable() -> None:
    """After migration, loader must be importable from the platform/hooks path."""
    from nano_multiagent.platform.hooks.loader import build_hook_registry  # noqa: F401



def test_old_hooks_loader_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for hooks.loader."""
    from nano_multiagent.hooks.loader import build_hook_registry  # noqa: F401



def test_old_hooks_builtins_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for hooks.builtins package."""
    from nano_multiagent.hooks import builtins  # noqa: F401
