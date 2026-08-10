"""Saved Workflow discovery and persistence along product-provided roots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from agent.core.workflows import compile_workflow

from .store import slugify_workflow_name


@dataclass(frozen=True, slots=True)
class SavedWorkflow:
    name: str
    scope: str
    path: str
    description: str = ""
    namespace: str | None = None


class SavedWorkflowRegistry:
    def __init__(
        self,
        *,
        config_dirname: str,
        personal_root: Path,
        bundled_root: Path | None = None,
        plugin_roots: Sequence[tuple[str, Path]] = (),
    ) -> None:
        self._config_dirname = config_dirname
        self._personal_root = personal_root.expanduser().resolve()
        self._bundled_root = (
            bundled_root.expanduser().resolve() if bundled_root is not None else None
        )
        self._plugin_roots = tuple(
            (namespace, path.expanduser().resolve()) for namespace, path in plugin_roots
        )

    def resolve(self, name: str, *, workspace_root: Path) -> SavedWorkflow | None:
        namespace, _, plain_name = name.partition(":")
        if plain_name:
            for candidate_namespace, root in self._plugin_roots:
                if candidate_namespace == namespace:
                    return self._load(
                        root / f"{plain_name}.py", scope="plugin", namespace=namespace
                    )
            return None
        discovered = {
            item.name: item for item in self.list(workspace_root=workspace_root)
        }
        return discovered.get(name)

    def list(self, *, workspace_root: Path) -> tuple[SavedWorkflow, ...]:
        found: dict[str, SavedWorkflow] = {}
        if self._bundled_root is not None:
            for path in sorted(self._bundled_root.glob("*.py")):
                item = self._load(path, scope="bundled")
                if item is not None:
                    found[item.name] = item
        for path in sorted(self._personal_root.glob("*.py")):
            item = self._load(path, scope="personal")
            if item is not None:
                found[item.name] = item
        roots = self._project_workflow_roots(workspace_root)
        for root in reversed(roots):
            for path in sorted(root.glob("*.py")):
                item = self._load(path, scope="project")
                if item is not None:
                    found[item.name] = item
        for namespace, root in self._plugin_roots:
            for path in sorted(root.glob("*.py")):
                item = self._load(path, scope="plugin", namespace=namespace)
                if item is not None:
                    found[f"{namespace}:{item.name}"] = item
        return tuple(
            sorted(found.values(), key=lambda item: (item.namespace or "", item.name))
        )

    def save(
        self,
        *,
        source: str,
        name: str,
        scope: str,
        workspace_root: Path,
    ) -> SavedWorkflow:
        compiled = compile_workflow(source)
        slug = slugify_workflow_name(name or compiled.meta.name)
        if scope == "personal":
            target_root = self._personal_root
            target = target_root / f"{slug}.py"
            if target.is_symlink():
                raise ValueError("personal Workflow target must not be a symlink")
        elif scope == "project":
            roots = self._project_workflow_roots(workspace_root)
            target_root = next((root for root in roots if root.is_dir()), None)
            if target_root is None:
                git_root = self._git_root(workspace_root)
                target_root = git_root / self._config_dirname / "workflows"
            config_root = target_root.parent
            target = target_root / f"{slug}.py"
            if (
                config_root.is_symlink()
                or target_root.is_symlink()
                or target.is_symlink()
            ):
                raise ValueError(
                    "project Workflow destination must not contain a symlink"
                )
        else:
            raise ValueError(f"unknown Workflow save scope: {scope}")
        target_root.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".py.tmp")
        temp.write_text(source, encoding="utf-8")
        temp.replace(target)
        return SavedWorkflow(
            name=slug,
            scope=scope,
            path=str(target),
            description=compiled.meta.description,
        )

    def _project_workflow_roots(self, workspace_root: Path) -> tuple[Path, ...]:
        current = workspace_root.expanduser().resolve()
        git_root = self._git_root(current)
        roots: list[Path] = []
        while True:
            roots.append(current / self._config_dirname / "workflows")
            if current == git_root:
                break
            current = current.parent
        return tuple(roots)

    @staticmethod
    def _git_root(workspace_root: Path) -> Path:
        current = workspace_root.expanduser().resolve()
        for candidate in (current, *current.parents):
            if (candidate / ".git").exists():
                return candidate
        return current

    @staticmethod
    def _load(
        path: Path, *, scope: str, namespace: str | None = None
    ) -> SavedWorkflow | None:
        if not path.is_file():
            return None
        try:
            compiled = compile_workflow(
                path.read_text(encoding="utf-8"), filename=str(path)
            )
        except (OSError, ValueError):
            return None
        return SavedWorkflow(
            name=path.stem,
            scope=scope,
            path=str(path),
            description=compiled.meta.description,
            namespace=namespace,
        )
