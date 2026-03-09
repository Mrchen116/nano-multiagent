"""Verify platform/tools is importable with builtins, loader, and safety."""


def test_platform_tools_builtins_importable() -> None:
    """After migration, builtins must be importable from the platform/tools path."""
    from nano_multiagent.platform.tools import builtins  # noqa: F401


def test_platform_tools_loader_importable() -> None:
    """After migration, loader must be importable from the platform/tools path."""
    from nano_multiagent.platform.tools.loader import build_tool_registry  # noqa: F401


def test_platform_tools_safety_importable() -> None:
    """After migration, safety must be importable from the platform/tools path."""
    from nano_multiagent.platform.tools.safety import load_tool_safety_config  # noqa: F401


def test_old_tools_loader_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for tools.loader."""
    from nano_multiagent.tools.loader import build_tool_registry  # noqa: F401


def test_old_tools_safety_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for tools.safety."""
    from nano_multiagent.tools.safety import load_tool_safety_config  # noqa: F401


def test_old_tools_builtins_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for tools.builtins."""
    from nano_multiagent.tools.builtins import register_builtin_tools  # noqa: F401
