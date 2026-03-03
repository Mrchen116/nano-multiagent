"""Workspace-level helpers for resolving available Codex skills."""

import os
from pathlib import Path
from typing import Sequence

from .registry import SkillMetadata, SkillRegistry


def default_skill_search_roots(*, workspace_root: Path) -> tuple[Path, ...]:
    """Return default skill roots in precedence order with duplicates removed."""

    codex_home = Path(os.getenv("CODEX_HOME", "~/.codex")).expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()

    unique_roots: list[Path] = []
    for candidate in (
        codex_home / "skills",
        workspace / ".codex" / "skills",
        workspace / ".nano" / "skills",
    ):
        if candidate not in unique_roots:
            unique_roots.append(candidate)
    return tuple(unique_roots)


def resolve_available_skills(
    *,
    workspace_root: Path,
    include_names: Sequence[str] | None = None,
    registry: SkillRegistry | None = None,
) -> tuple[SkillMetadata, ...]:
    """Resolve available skills, optionally filtering by requested names."""

    active_registry = registry or SkillRegistry(search_roots=default_skill_search_roots(workspace_root=workspace_root))
    skills = active_registry.list_skills()
    if include_names is None:
        return skills

    requested = set(include_names)
    return tuple(skill for skill in skills if skill.name in requested)
