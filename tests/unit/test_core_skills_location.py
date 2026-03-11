"""Verify core/skills is the canonical home for shared skill abstractions."""

from importlib.util import find_spec

from agent.core.skills import (
    SkillMetadata,
    SkillRegistry,
    default_skill_search_roots,
    format_available_skills_section,
    resolve_available_skills,
)
from agent.core.skills.discovery import default_skill_search_roots as CoreDefaultSkillSearchRoots
from agent.core.skills.discovery import resolve_available_skills as CoreResolveAvailableSkills
from agent.core.skills.formatter import format_available_skills_section as CoreFormatAvailableSkillsSection
from agent.core.skills.registry import SkillMetadata as CoreSkillMetadata
from agent.core.skills.registry import SkillRegistry as CoreSkillRegistry



def test_core_skills_is_canonical_home() -> None:
    """Core skill exports must originate from core-owned modules."""
    assert SkillMetadata is CoreSkillMetadata
    assert SkillRegistry is CoreSkillRegistry
    assert default_skill_search_roots is CoreDefaultSkillSearchRoots
    assert resolve_available_skills is CoreResolveAvailableSkills
    assert format_available_skills_section is CoreFormatAvailableSkillsSection

    assert SkillMetadata.__module__ == "agent.core.skills.registry"
    assert SkillRegistry.__module__ == "agent.core.skills.registry"
    assert default_skill_search_roots.__module__ == "agent.core.skills.discovery"
    assert resolve_available_skills.__module__ == "agent.core.skills.discovery"
    assert format_available_skills_section.__module__ == "agent.core.skills.formatter"



def test_legacy_skills_root_is_removed() -> None:
    assert find_spec("agent.skills") is None
