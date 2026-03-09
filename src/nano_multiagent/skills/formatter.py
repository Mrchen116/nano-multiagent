"""Compatibility shim re-exporting canonical core skill prompt formatting."""

from nano_multiagent.core.skills.formatter import SKILLS_GUIDANCE, format_available_skills_section

__all__ = ["SKILLS_GUIDANCE", "format_available_skills_section"]
