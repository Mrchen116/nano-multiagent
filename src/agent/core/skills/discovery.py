"""Canonical skill discovery helpers for resolver-aware filesystem search."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .registry import SkillMetadata, SkillRegistry


class SkillRootResolver(Protocol):
    """Describe the resolver contract needed by core skill discovery."""

    def user_skill_roots(self) -> tuple[Path, ...]:
        """Return ordered skill search roots for the active product context."""


class _WorkspaceDirnameSkillResolver:
    """Minimal SkillRootResolver for the 2-layer path (no ProductProfile).

    Resolves skills under ``<workspace_root>/<workspace_config_dirname>/skills``
    FIRST (per-workspace), then the build-time deployment ``extra_roots`` (shared
    user-level/global/compat skill dirs the consumer factory owns), deduplicating
    by directory while preserving order.

    Moved from agent.sdk.kernel to agent.core.skills (bugfix-431) so that
    AgentRuntime (core) can call make_skill_resolver at the same layer without
    creating a core→sdk reverse dependency.
    """

    def __init__(
        self,
        *,
        workspace_root: Path,
        workspace_config_dirname: str,
        extra_roots: tuple[Path, ...] = (),
    ) -> None:
        ordered: list[Path] = [
            (workspace_root / workspace_config_dirname / "skills")
            .expanduser()
            .resolve()
        ]
        for root in extra_roots:
            resolved = Path(root).expanduser().resolve()
            if resolved not in ordered:
                ordered.append(resolved)
        self._roots = tuple(ordered)

    def user_skill_roots(self) -> tuple[Path, ...]:
        return self._roots


def make_skill_resolver(
    workspace_root: Path,
    workspace_config_dirname: str | None,
    skill_search_roots: tuple[Path, ...],
) -> SkillRootResolver | None:
    """Build a per-workspace skill resolver from the same inputs used by preview/list_skills.

    This is the single source of truth for skill resolver construction (bugfix-431).
    AgentRuntime (core) calls this at the same layer (core→core); Kernel (sdk) imports
    it downward (sdk→core), which is the legal direction. Placing it here avoids the
    core→sdk reverse dependency that would arise if it lived in agent.sdk.kernel.

    Args:
        workspace_root: Per-session workspace directory.
        workspace_config_dirname: Product config subdirectory name (supplied by the consumer
            factory, e.g. the PA or CLI product dirname). Returns None when absent —
            callers treat None as "no workspace skills".
        skill_search_roots: Deployment-level shared skill directories supplied by the
            consumer factory (e.g. PA_SKILL_SEARCH_ROOTS). Appended after the
            per-workspace root, deduplicating by directory.

    Returns:
        A SkillRootResolver whose user_skill_roots() yields workspace-first roots,
        or None when workspace_config_dirname is not supplied.
    """
    if not workspace_config_dirname:
        return None
    return _WorkspaceDirnameSkillResolver(
        workspace_root=workspace_root,
        workspace_config_dirname=workspace_config_dirname,
        extra_roots=skill_search_roots,
    )


def default_skill_search_roots(
    *,
    workspace_root: Path,
    config_resolver: SkillRootResolver | None = None,
) -> tuple[Path, ...]:
    """Return skill search roots in precedence order with duplicates removed.

    When config_resolver is supplied its roots are used directly. When None,
    returns an empty tuple — callers must supply explicit roots via a resolver
    or SkillRegistry(search_roots=...).

    The legacy Codex fallback roots (~/.codex/skills, <ws>/.codex/skills,
    <ws>/.nano/skills) and product_skill_root parameter are removed (bugfix-431
    决策 4): they were implicit residue of the old ProductProfile path and were the
    structural reason runtime diverged from preview (runtime got Codex-only roots,
    preview got the correct workspace + deployment roots from the resolver).
    """
    if config_resolver is not None:
        roots = list(config_resolver.user_skill_roots())
        unique_roots: list[Path] = []
        for candidate in roots:
            if candidate not in unique_roots:
                unique_roots.append(candidate)
        return tuple(unique_roots)

    # No resolver → no implicit roots. All skill paths must be declared explicitly
    # via a resolver or SkillRegistry(search_roots=...).
    return ()


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


__all__ = [
    "default_skill_search_roots",
    "make_skill_resolver",
    "resolve_available_skills",
]
