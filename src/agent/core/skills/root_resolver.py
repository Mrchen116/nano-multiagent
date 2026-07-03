"""Shared skill-root resolution for skill tools.

The runtime owns workspace metadata; tools should resolve roots from the same
inputs so list/view/create all see the same precedence order.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .registry import SkillRegistry
from .writer import SkillWriter


@dataclass(frozen=True, slots=True)
class ResolvedSkillRoots:
    """Resolved skill roots for one tool call."""

    agent_skill_root: Path
    search_roots: tuple[Path, ...]
    registry: SkillRegistry
    agent_writer: SkillWriter
    pa_skill_root: Path | None = None

    def writer_for_scope(self, scope: str) -> SkillWriter:
        """Return the write-side SkillWriter for the requested create scope."""
        normalized = scope or "agent"
        if normalized == "agent":
            return self.agent_writer
        if normalized != "pa":
            raise ValueError("scope must be 'agent' or 'pa'")
        if self.pa_skill_root is None:
            raise ValueError("pa skill root is not configured")
        pa_registry = SkillRegistry(search_roots=(self.pa_skill_root, *self.search_roots))
        return SkillWriter(skill_root=self.pa_skill_root, registry=pa_registry)

    def root_for_location(self, location: Path) -> Path:
        """Return the configured search root that owns a discovered skill file."""

        resolved_location = location.expanduser().resolve()
        for root in self.search_roots:
            resolved_root = root.expanduser().resolve()
            try:
                resolved_location.relative_to(resolved_root)
            except ValueError:
                continue
            return resolved_root
        return self.agent_skill_root


def resolve_skill_roots(
    ctx: Any,
    *,
    workspace_config_dirname: str | None,
    extra_roots: tuple[Path, ...] = (),
    pa_skill_root: Path | None = None,
) -> ResolvedSkillRoots:
    """Resolve per-session skill roots from ToolContext-like metadata.

    Args:
        ctx: ToolContext-like object carrying ``session_metadata``.
        workspace_config_dirname: Product workspace config dir name.
        extra_roots: Deployment-level read/search roots appended after agent root.
        pa_skill_root: Optional product-level root eligible for ``scope="pa"`` writes.

    Returns:
        Resolved roots plus registry/writer objects.

    Raises:
        RuntimeError: If workspace metadata cannot identify the agent root.
    """
    metadata = getattr(ctx, "session_metadata", {}) or {}
    workspace_root = metadata.get("workspace_root")
    dirname = metadata.get("workspace_config_dirname") or workspace_config_dirname
    if not workspace_root or not dirname:
        raise RuntimeError(
            "skill tools cannot resolve a per-session skill root: missing "
            "workspace_root or workspace_config_dirname in session_metadata"
        )

    ws = Path(str(workspace_root)).expanduser().resolve()
    agent_root = (ws / str(dirname) / "skills").expanduser().resolve()
    resolved_pa = (
        Path(pa_skill_root).expanduser().resolve() if pa_skill_root is not None else None
    )
    search_roots: list[Path] = [agent_root]
    for root in extra_roots:
        resolved = Path(root).expanduser().resolve()
        if resolved not in search_roots:
            search_roots.append(resolved)
    registry = SkillRegistry(search_roots=tuple(search_roots))
    return ResolvedSkillRoots(
        agent_skill_root=agent_root,
        search_roots=tuple(search_roots),
        registry=registry,
        agent_writer=SkillWriter(skill_root=agent_root, registry=registry),
        pa_skill_root=resolved_pa,
    )


__all__ = ["ResolvedSkillRoots", "resolve_skill_roots"]
