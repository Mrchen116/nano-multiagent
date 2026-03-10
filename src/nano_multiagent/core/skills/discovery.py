"""Canonical skill discovery helpers for resolver-aware filesystem search."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, Sequence

from .registry import SkillMetadata, SkillRegistry


class SkillRootResolver(Protocol):
    """Describe the resolver contract needed by core skill discovery."""

    def user_skill_roots(self) -> tuple[Path, ...]:
        """Return ordered skill search roots for the active product context."""


def default_skill_search_roots(
    *,
    workspace_root: Path,
    config_resolver: SkillRootResolver | None = None,
) -> tuple[Path, ...]:
    """Return skill search roots in precedence order with duplicates removed."""

    if config_resolver is not None:
        return config_resolver.user_skill_roots()

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
    config_resolver: SkillRootResolver | None = None,
) -> tuple[SkillMetadata, ...]:
    """Resolve available skills, optionally filtering by requested names."""

    active_registry = registry or SkillRegistry(
        search_roots=default_skill_search_roots(
            workspace_root=workspace_root,
            config_resolver=config_resolver,
        )
    )
    skills = active_registry.list_skills()
    if include_names is None:
        return skills

    requested = set(include_names)
    return tuple(skill for skill in skills if skill.name in requested)


__all__ = ["default_skill_search_roots", "resolve_available_skills"]
