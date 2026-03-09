"""Discovery and dynamic loading for workspace-provided tools."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from nano_multiagent.core.hooks.runner import HookRunner
from nano_multiagent.tools.base import Tool, ToolContext
from nano_multiagent.tools.registry import ToolRegistry

from .builtins import register_builtin_tools
from .safety import load_tool_safety_config

if TYPE_CHECKING:
    from nano_multiagent.platform.config.resolver import ConfigResolver


def build_tool_registry(
    *,
    repo_root: Path,
    hook_runner: HookRunner | None = None,
    runtime: Any | None = None,
    config_resolver: ConfigResolver | None = None,
) -> ToolRegistry:
    """Build a tool registry containing built-ins and user-provided tool plugins.

    Args:
        repo_root: Workspace root; used for safety sandboxing and, when no
            ``config_resolver`` is given, for legacy ``.nano/tools`` discovery.
        hook_runner: Optional hook runner wired after registry construction.
        runtime: Optional runtime reference passed to built-in tools.
        config_resolver: When provided, user tool directories are resolved via
            ``config_resolver.user_tool_roots()`` instead of the legacy
            ``<repo_root>/.nano/tools`` path.  When absent, falls back to the
            legacy location for backward compatibility.

    Returns:
        Wired ToolRegistry with built-ins and any discovered user tools loaded.
    """

    context = ToolContext.create(
        repo_root=repo_root,
        safety_config=load_tool_safety_config(repo_root=repo_root),
    )
    registry = ToolRegistry(context=context, hook_runner=hook_runner)
    register_builtin_tools(registry, runtime=runtime)

    if config_resolver is not None:
        # Load from resolver-specified roots; legacy .nano/tools is NOT searched.
        for tool_root in config_resolver.user_tool_roots():
            _load_tools_from_single_dir(tool_root=tool_root, registry=registry)
    else:
        load_tools_from_directory(repo_root=repo_root, registry=registry)

    return registry


def discover_tool_files(repo_root: Path) -> tuple[Path, ...]:
    """Return importable user tool files from the legacy `<repo>/.nano/tools` dir.

    Args:
        repo_root: Repository root; scans ``<repo_root>/.nano/tools``.

    Returns:
        Sorted tuple of ``.py`` files that do not start with ``_``.
    """

    tools_dir = repo_root / ".nano" / "tools"
    if not tools_dir.is_dir():
        return ()

    files = [
        path
        for path in tools_dir.glob("*.py")
        if path.is_file() and not path.name.startswith("_")
    ]
    return tuple(sorted(files))


def _load_tools_from_single_dir(*, tool_root: Path, registry: ToolRegistry) -> tuple[str, ...]:
    """Import tool modules from a single directory and register discovered tools.

    Args:
        tool_root: Absolute directory to scan for ``.py`` tool files.
        registry: Registry to register discovered tools into.

    Returns:
        Tuple of registered tool names from this directory.
    """

    if not tool_root.is_dir():
        return ()

    loaded_names: list[str] = []
    for file_path in sorted(tool_root.glob("*.py")):
        if not file_path.is_file() or file_path.name.startswith("_"):
            continue
        module = _import_module_from_path(file_path)
        for tool in _extract_tools(module, file_path=file_path):
            registry.register(tool)
            loaded_names.append(tool.name)
    return tuple(loaded_names)


def load_tools_from_directory(*, repo_root: Path, registry: ToolRegistry) -> tuple[str, ...]:
    """Import user tool modules and register exported tool objects."""

    loaded_names: list[str] = []
    for file_path in discover_tool_files(repo_root):
        module = _import_module_from_path(file_path)
        for tool in _extract_tools(module, file_path=file_path):
            registry.register(tool)
            loaded_names.append(tool.name)
    return tuple(loaded_names)


def _import_module_from_path(path: Path) -> ModuleType:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    module_name = f"nano_multiagent_user_tool_{path.stem}_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load tool module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_tools(module: ModuleType, *, file_path: Path) -> tuple[Tool, ...]:
    discovered: list[Tool] = []

    if hasattr(module, "TOOL"):
        _append_if_tool(discovered, getattr(module, "TOOL"), file_path=file_path)

    if hasattr(module, "TOOLS"):
        raw_tools = getattr(module, "TOOLS")
        if isinstance(raw_tools, (list, tuple)):
            for raw_tool in raw_tools:
                _append_if_tool(discovered, raw_tool, file_path=file_path)

    if hasattr(module, "get_tool"):
        factory = getattr(module, "get_tool")
        if callable(factory):
            _append_if_tool(discovered, factory(), file_path=file_path)

    if not discovered:
        raise RuntimeError(f"no tool export found in: {file_path}")

    return tuple(discovered)


def _append_if_tool(discovered: list[Tool], candidate: Any, *, file_path: Path) -> None:
    if _is_tool(candidate):
        discovered.append(candidate)
        return
    raise RuntimeError(f"invalid tool object in {file_path}")


def _is_tool(candidate: Any) -> bool:
    return (
        isinstance(getattr(candidate, "name", None), str)
        and isinstance(getattr(candidate, "description", None), str)
        and isinstance(getattr(candidate, "input_schema", None), dict)
        and callable(getattr(candidate, "run", None))
    )
