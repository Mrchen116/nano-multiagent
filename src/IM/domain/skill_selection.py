"""Skill selection intent shared by IM persistence and API projection."""

from __future__ import annotations


DEFAULT_DISCOVERY = "default_discovery"
EXPLICIT_ALLOWLIST = "explicit_allowlist"


def effective_skills_selection_mode(mode: str | None, skills: list[str]) -> str:
    """Resolve legacy profiles without eagerly rewriting persisted data."""
    if mode in {DEFAULT_DISCOVERY, EXPLICIT_ALLOWLIST}:
        return mode
    return EXPLICIT_ALLOWLIST if skills else DEFAULT_DISCOVERY


__all__ = [
    "DEFAULT_DISCOVERY",
    "EXPLICIT_ALLOWLIST",
    "effective_skills_selection_mode",
]
