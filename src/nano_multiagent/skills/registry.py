"""Compatibility shim re-exporting canonical core skill discovery types."""

from nano_multiagent.core.skills.registry import (
    SkillMetadata,
    SkillRegistry,
    _extract_description,
    _extract_frontmatter_and_body,
    _parse_skill_metadata,
)

__all__ = [
    "SkillMetadata",
    "SkillRegistry",
    "_extract_description",
    "_extract_frontmatter_and_body",
    "_parse_skill_metadata",
]
