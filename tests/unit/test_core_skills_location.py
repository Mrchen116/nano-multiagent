"""Verify core/skills is the canonical home for shared skill abstractions."""

from nano_multiagent.core.skills import SkillMetadata, SkillRegistry, format_available_skills_section
from nano_multiagent.core.skills.formatter import format_available_skills_section as CoreFormatAvailableSkillsSection
from nano_multiagent.core.skills.registry import SkillMetadata as CoreSkillMetadata
from nano_multiagent.core.skills.registry import SkillRegistry as CoreSkillRegistry
from nano_multiagent.skills.formatter import format_available_skills_section as LegacyFormatAvailableSkillsSection
from nano_multiagent.skills.registry import SkillMetadata as LegacySkillMetadata
from nano_multiagent.skills.registry import SkillRegistry as LegacySkillRegistry


def test_core_skills_is_canonical_home() -> None:
    """Core skill exports must originate from core-owned modules."""
    assert SkillMetadata is CoreSkillMetadata
    assert SkillRegistry is CoreSkillRegistry
    assert format_available_skills_section is CoreFormatAvailableSkillsSection

    assert SkillMetadata.__module__ == "nano_multiagent.core.skills.registry"
    assert SkillRegistry.__module__ == "nano_multiagent.core.skills.registry"
    assert format_available_skills_section.__module__ == "nano_multiagent.core.skills.formatter"


def test_old_skills_paths_are_compat_shims() -> None:
    """Legacy skill modules must re-export the canonical core skill objects."""
    assert LegacySkillMetadata is CoreSkillMetadata
    assert LegacySkillRegistry is CoreSkillRegistry
    assert LegacyFormatAvailableSkillsSection is CoreFormatAvailableSkillsSection
