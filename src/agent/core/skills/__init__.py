"""Canonical shared skill metadata, discovery, and prompt formatting helpers."""

from .discovery import (
    build_skill_search_roots,
    default_skill_search_roots,
    make_skill_resolver,
    resolve_available_skills,
)
from .formatter import format_available_skills_section
from .registry import SkillMetadata, SkillRegistry

__all__ = [
    "SkillMetadata",
    "SkillRegistry",
    "build_skill_search_roots",
    "default_skill_search_roots",
    "make_skill_resolver",
    "resolve_available_skills",
    "format_available_skills_section",
]
