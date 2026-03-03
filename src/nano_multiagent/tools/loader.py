"""Discovery and dynamic loading for workspace-provided tools."""

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from nano_multiagent.hooks.runner import HookRunner

from .base import Tool
from .builtins import register_builtin_tools
from .registry import ToolRegistry


def build_tool_registry(
    *,
    repo_root: Path,
    hook_runner: HookRunner | None = None,
    runtime: Any | None = None,
) -> ToolRegistry:
    """Build a tool registry containing built-ins and `.nano/tools` plugins."""

    from .base import ToolContext

    context = ToolContext.create(repo_root=repo_root)
    registry = ToolRegistry(context=context, hook_runner=hook_runner)
    register_builtin_tools(registry, runtime=runtime)
    load_tools_from_directory(repo_root=repo_root, registry=registry)
    return registry


def discover_tool_files(repo_root: Path) -> tuple[Path, ...]:
    """Return importable user tool files from `<repo>/.nano/tools`."""

    tools_dir = repo_root / ".nano" / "tools"
    if not tools_dir.is_dir():
        return ()

    files = [
        path
        for path in tools_dir.glob("*.py")
        if path.is_file() and not path.name.startswith("_")
    ]
    return tuple(sorted(files))


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
