"""Verify core/skills is the canonical home for shared skill abstractions."""

from importlib.util import find_spec
from pathlib import Path

from agent.core.skills import (
    SkillMetadata,
    SkillRegistry,
    default_skill_search_roots,
    format_available_skills_section,
    make_skill_resolver,
    resolve_available_skills,
)
from agent.core.skills.discovery import (
    default_skill_search_roots as CoreDefaultSkillSearchRoots,
)
from agent.core.skills.discovery import make_skill_resolver as CoreMakeSkillResolver
from agent.core.skills.discovery import (
    resolve_available_skills as CoreResolveAvailableSkills,
)
from agent.core.skills.formatter import (
    format_available_skills_section as CoreFormatAvailableSkillsSection,
)
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


def test_make_skill_resolver_lives_in_core() -> None:
    """make_skill_resolver must be in agent.core, not agent.sdk (bugfix-431).

    This prevents the core→sdk reverse dependency: AgentRuntime (core) must
    call make_skill_resolver at the same layer (core→core), not import it from sdk.
    """
    assert make_skill_resolver is CoreMakeSkillResolver
    assert CoreMakeSkillResolver.__module__ == "agent.core.skills.discovery"
    # Not defined in sdk (sdk may import and use it, but must not define it)
    import importlib  # noqa: PLC0415

    sdk_kernel = importlib.import_module("agent.sdk.kernel")
    assert not hasattr(sdk_kernel, "make_skill_resolver"), (
        "make_skill_resolver must not be defined in agent.sdk.kernel"
    )


def test_make_skill_resolver_returns_resolver_with_correct_roots(tmp_path: Path) -> None:
    """make_skill_resolver constructs a resolver with workspace-first root ordering."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    extra = tmp_path / "extra_skills"
    extra.mkdir()

    resolver = make_skill_resolver(
        workspace_root=ws,
        workspace_config_dirname=".nanoassistant",
        skill_search_roots=(extra,),
    )
    assert resolver is not None
    roots = resolver.user_skill_roots()
    # workspace-relative root comes first
    assert roots[0] == (ws / ".nanoassistant" / "skills").resolve()
    # extra root appears after workspace root
    assert extra.resolve() in roots


def test_make_skill_resolver_returns_none_without_dirname(tmp_path: Path) -> None:
    """make_skill_resolver returns None when no workspace_config_dirname given."""
    resolver = make_skill_resolver(
        workspace_root=tmp_path,
        workspace_config_dirname=None,
        skill_search_roots=(),
    )
    assert resolver is None


def test_legacy_skills_root_is_removed() -> None:
    assert find_spec("agent.skills") is None
