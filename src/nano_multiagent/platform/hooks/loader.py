"""Hook discovery/registration loader for built-in and workspace modules."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from nano_multiagent.core.hooks.registry import HookAPI, HookRegistry
from nano_multiagent.core.hooks.types import LoadedHookModule

if TYPE_CHECKING:
    from nano_multiagent.platform.config.resolver import ConfigResolver


def build_hook_registry(
    *,
    repo_root: Path,
    builtins_dir: Path | None = None,
    workspace_dir: Path | None = None,
    config_resolver: ConfigResolver | None = None,
) -> HookRegistry:
    """Build a hook registry by loading built-in and user-provided hook modules.

    Args:
        repo_root: Workspace root; used as reference even when resolver is given.
        builtins_dir: Override for built-in hooks directory; defaults to the
            ``builtins/`` sub-package next to this module.
        workspace_dir: Override for workspace hooks directory; only used when
            ``config_resolver`` is ``None``.
        config_resolver: When provided, workspace hook directories are resolved
            via ``config_resolver.user_hook_roots()``; the legacy ``.nano/hooks``
            path (and ``workspace_dir`` kwarg) is ignored.  When absent, falls
            back to ``workspace_dir`` or ``<repo_root>/.nano/hooks``.

    Returns:
        HookRegistry with built-in hooks loaded, plus any user hook modules.
    """

    if config_resolver is not None:
        # Use resolver-specified hook roots; first root = workspace, rest = global/compat.
        hook_roots = config_resolver.user_hook_roots()
        # Load builtins first, then each resolver-specified dir as "workspace".
        resolved_workspace_dir = hook_roots[0] if hook_roots else None
        registry, _ = load_hooks_from_directories(
            repo_root=repo_root,
            builtins_dir=builtins_dir,
            workspace_dir=resolved_workspace_dir,
            registry=HookRegistry(),
        )
        # Load additional (global, compat) roots as "workspace" source too.
        for extra_root in hook_roots[1:]:
            if extra_root.is_dir():
                for file_path in discover_hook_files(extra_root):
                    module = _import_hook_module(file_path, source="workspace")
                    setup = getattr(module, "setup", None)
                    if not callable(setup):
                        raise RuntimeError(f"hook module missing setup(hooks): {file_path}")
                    setup(HookAPI(registry, source="workspace", module_name=module.__name__, file_path=file_path))
        return registry
    else:
        registry, _ = load_hooks_from_directories(
            repo_root=repo_root,
            builtins_dir=builtins_dir,
            workspace_dir=workspace_dir,
            registry=HookRegistry(),
        )
        return registry


def discover_hook_files(directory: Path) -> tuple[Path, ...]:
    """Return loadable `.py` hook files from a directory."""

    if not directory.is_dir():
        return ()

    files = [
        file_path
        for file_path in directory.glob("*.py")
        if file_path.is_file() and not file_path.name.startswith("_")
    ]
    return tuple(sorted(files))


def load_hooks_from_directories(
    *,
    repo_root: Path,
    builtins_dir: Path | None = None,
    workspace_dir: Path | None = None,
    registry: HookRegistry | None = None,
) -> tuple[HookRegistry, tuple[LoadedHookModule, ...]]:
    """Load hooks from canonical directories and return registry plus module metadata."""

    resolved_repo_root = repo_root.expanduser().resolve()
    active_registry = registry or HookRegistry()
    builtin_root = (builtins_dir or Path(__file__).resolve().parent / "builtins").expanduser().resolve()
    workspace_root = (workspace_dir or resolved_repo_root / ".nano" / "hooks").expanduser().resolve()

    loaded_modules: list[LoadedHookModule] = []
    for source, root in (("builtin", builtin_root), ("workspace", workspace_root)):
        for file_path in discover_hook_files(root):
            module = _import_hook_module(file_path, source=source)
            setup = getattr(module, "setup", None)
            if not callable(setup):
                raise RuntimeError(f"hook module missing setup(hooks): {file_path}")
            setup(
                HookAPI(
                    active_registry,
                    source=source,
                    module_name=module.__name__,
                    file_path=file_path,
                )
            )
            loaded_modules.append(
                LoadedHookModule(
                    module_name=module.__name__,
                    file_path=file_path,
                    source=source,
                )
            )
    return active_registry, tuple(loaded_modules)


def _import_hook_module(path: Path, *, source: str) -> ModuleType:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    module_name = f"nano_multiagent_{source}_hook_{path.stem}_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load hook module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
