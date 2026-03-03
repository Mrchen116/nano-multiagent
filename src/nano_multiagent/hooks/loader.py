"""Hook discovery/registration loader for built-in and workspace modules."""

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

from .registry import HookAPI, HookRegistry
from .types import LoadedHookModule


def build_hook_registry(
    *,
    repo_root: Path,
    builtins_dir: Path | None = None,
    workspace_dir: Path | None = None,
) -> HookRegistry:
    """Build a hook registry by loading built-in and workspace hook files."""

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
