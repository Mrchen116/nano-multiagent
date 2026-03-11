"""Canonical shared skill metadata, discovery, and prompt formatting helpers."""

from .discovery import default_skill_search_roots, resolve_available_skills
from .formatter import format_available_skills_section
from .registry import SkillMetadata, SkillRegistry

__all__ = [
    "SkillMetadata",
    "SkillRegistry",
    "default_skill_search_roots",
    "resolve_available_skills",
    "format_available_skills_section",
]
