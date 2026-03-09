"""Workspace-level helpers for resolving available Codex skills."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .registry import SkillMetadata, SkillRegistry

if TYPE_CHECKING:
    from nano_multiagent.platform.config.resolver import ConfigResolver


def default_skill_search_roots(
    *,
    workspace_root: Path,
    config_resolver: ConfigResolver | None = None,
) -> tuple[Path, ...]:
    """Return skill search roots in precedence order with duplicates removed.

    Args:
        workspace_root: Repository or project root; used as workspace base for
            both resolver-based and legacy path calculation.
        config_resolver: When provided, skill roots are resolved via
            ``config_resolver.user_skill_roots()`` (workspace > global > compat).
            When absent, falls back to the legacy ``CODEX_HOME``-based roots.

    Returns:
        Ordered, deduplicated tuple of absolute skill directory paths.
    """

    if config_resolver is not None:
        return config_resolver.user_skill_roots()

    # Legacy behavior: CODEX_HOME env var + workspace-relative fallbacks.
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
