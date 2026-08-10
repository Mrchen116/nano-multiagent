"""Skill selection intent for Gateway-local Agent configuration."""

from __future__ import annotations

DEFAULT_DISCOVERY = "default_discovery"
EXPLICIT_ALLOWLIST = "explicit_allowlist"
VALID_SELECTION_MODES = frozenset({DEFAULT_DISCOVERY, EXPLICIT_ALLOWLIST})


def effective_skills_selection_mode(mode: str | None, skills: tuple[str, ...]) -> str:
    """Resolve legacy missing mode from its pre-upgrade names semantics."""
    if mode in VALID_SELECTION_MODES:
        return mode
    return EXPLICIT_ALLOWLIST if skills else DEFAULT_DISCOVERY


__all__ = [
    "DEFAULT_DISCOVERY",
    "EXPLICIT_ALLOWLIST",
    "VALID_SELECTION_MODES",
    "effective_skills_selection_mode",
]
