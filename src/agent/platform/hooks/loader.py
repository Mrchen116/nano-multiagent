"""Hook discovery/registration loader for built-in and workspace modules."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Protocol

from agent.core.hooks.registry import HookAPI, HookRegistry
from agent.core.hooks.types import LoadedHookModule


class _HookRootResolver(Protocol):
    """Duck-typed resolver supplying user hook search roots.

    refactor-406-M2: the concrete ConfigResolver class was removed with products/.
    The 2-layer build_kernel path does not pass a resolver here (legacy ``.nano/hooks``
    discovery only); this minimal Protocol documents the contract without a
    product-profile dependency.
    """

    def user_hook_roots(self) -> tuple[Path, ...]: ...


def build_hook_registry(
    *,
    repo_root: Path,
    builtins_dir: Path | None = None,
    workspace_dir: Path | None = None,
    config_resolver: _HookRootResolver | None = None,
    product_hook_dir: Path | None = None,
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
        product_hook_dir: Optional product-owned hook directory loaded after
            built-ins and before user global/workspace layers.

    Returns:
        HookRegistry with built-in hooks loaded, plus any user hook modules.
    """

    if config_resolver is not None:
        registry, _ = load_hooks_from_directories(
            repo_root=repo_root,
            builtins_dir=builtins_dir,
            workspace_dir=None,
            registry=HookRegistry(),
            include_default_workspace=False,
        )
        if product_hook_dir is not None:
            _load_hook_dir_into_registry(
                registry, product_hook_dir, source="product", replace=True
            )
        for extra_root in reversed(config_resolver.user_hook_roots()):
            _load_hook_dir_into_registry(
                registry, extra_root, source="workspace", replace=True
            )
        return registry
    else:
        registry, _ = load_hooks_from_directories(
            repo_root=repo_root,
            builtins_dir=builtins_dir,
            workspace_dir=workspace_dir,
            registry=HookRegistry(),
        )
        if product_hook_dir is not None:
            _load_hook_dir_into_registry(
                registry, product_hook_dir, source="product", replace=True
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
    include_default_workspace: bool = True,
) -> tuple[HookRegistry, tuple[LoadedHookModule, ...]]:
    """Load hooks from canonical directories and return registry plus module metadata."""

    resolved_repo_root = repo_root.expanduser().resolve()
    active_registry = registry or HookRegistry()
    builtin_root = (
        (builtins_dir or Path(__file__).resolve().parent / "builtins")
        .expanduser()
        .resolve()
    )
    workspace_root = None
    if workspace_dir is not None:
        workspace_root = workspace_dir.expanduser().resolve()
    elif include_default_workspace:
        workspace_root = (resolved_repo_root / ".nano" / "hooks").expanduser().resolve()

    loaded_modules: list[LoadedHookModule] = []
    roots: list[tuple[str, Path]] = [("builtin", builtin_root)]
    if workspace_root is not None:
        roots.append(("workspace", workspace_root))
    for source, root in roots:
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


def _load_hook_dir_into_registry(
    registry: HookRegistry,
    directory: Path,
    *,
    source: str,
    replace: bool = False,
) -> None:
    if not directory.is_dir():
        return

    for file_path in discover_hook_files(directory):
        if replace:
            _remove_existing_hook_registrations(
                registry, source=source, file_name=file_path.name
            )
        module = _import_hook_module(file_path, source=source)
        setup = getattr(module, "setup", None)
        if not callable(setup):
            raise RuntimeError(f"hook module missing setup(hooks): {file_path}")
        setup(
            HookAPI(
                registry,
                source=source,
                module_name=module.__name__,
                file_path=file_path,
            )
        )


def _remove_existing_hook_registrations(
    registry: HookRegistry, *, source: str, file_name: str
) -> None:
    removable_sources = {source}
    if source == "workspace":
        removable_sources.add("product")

    for event, registrations in list(registry._registrations.items()):  # type: ignore[attr-defined]
        filtered = [
            registration
            for registration in registrations
            if not (
                registration.file_path is not None
                and registration.file_path.name == file_name
                and registration.source in removable_sources
            )
        ]
        registry._registrations[event] = filtered  # type: ignore[attr-defined]


def _import_hook_module(path: Path, *, source: str) -> ModuleType:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    module_name = f"agent_{source}_hook_{path.stem}_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load hook module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
