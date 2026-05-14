"""Unit tests for core/skills SkillWriter write-side operations.

Covers: create / edit / patch / name regex / frontmatter validation /
        content size limit / cache invalidation after write.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.skills.registry import SkillRegistry
from agent.core.skills.writer import SkillWriter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_FRONTMATTER = "---\nname: test-skill\ndescription: A test skill\n---\n\n# Body\n\nSome content."


@pytest.fixture()
def skill_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    root.mkdir()
    return root


@pytest.fixture()
def registry(skill_root: Path) -> SkillRegistry:
    return SkillRegistry(search_roots=[skill_root])


@pytest.fixture()
def writer(skill_root: Path, registry: SkillRegistry) -> SkillWriter:
    return SkillWriter(skill_root=skill_root, registry=registry)


# ---------------------------------------------------------------------------
# R2.1  create — happy path
# ---------------------------------------------------------------------------


def test_create_writes_skill_md(writer: SkillWriter, skill_root: Path) -> None:
    writer.create("my-skill", _VALID_FRONTMATTER)
    skill_file = skill_root / "my-skill" / "SKILL.md"
    assert skill_file.exists()
    assert skill_file.read_text(encoding="utf-8") == _VALID_FRONTMATTER


def test_create_invalidates_cache(writer: SkillWriter, registry: SkillRegistry) -> None:
    # Warm the cache
    _ = registry.list_skills()
    writer.create("new-skill", _VALID_FRONTMATTER.replace("test-skill", "new-skill"))
    # Cache must be invalidated — list should include new skill
    skills = registry.list_skills()
    names = [s.name for s in skills]
    assert "new-skill" in names


def test_create_duplicate_raises(writer: SkillWriter) -> None:
    writer.create("dup-skill", _VALID_FRONTMATTER.replace("test-skill", "dup-skill"))
    with pytest.raises(ValueError, match="already exists"):
        writer.create("dup-skill", _VALID_FRONTMATTER.replace("test-skill", "dup-skill"))


# ---------------------------------------------------------------------------
# R2.2  create — name validation (regex: ^[a-z0-9][a-z0-9._-]*$, max 64)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "-starts-with-dash",
        "_starts_with_underscore",
        "UPPERCASE",
        "has spaces",
        "has/slash",
        "a" * 65,  # 65 chars — exceeds max 64
        "",
    ],
)
def test_create_invalid_name_raises(writer: SkillWriter, bad_name: str) -> None:
    with pytest.raises(ValueError, match="name"):
        writer.create(bad_name, _VALID_FRONTMATTER)


@pytest.mark.parametrize(
    "good_name",
    [
        "simple",
        "with-dash",
        "with.dot",
        "with_underscore",
        "abc123",
        "a",
        "a" * 64,  # exactly 64 chars — at limit
    ],
)
def test_create_valid_name_accepted(writer: SkillWriter, skill_root: Path, good_name: str) -> None:
    content = f"---\nname: {good_name}\ndescription: desc\n---\n\n# Body\n"
    writer.create(good_name, content)
    assert (skill_root / good_name / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# R2.3  frontmatter validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_content",
    [
        # No frontmatter
        "# Just a heading\nSome text",
        # Missing 'description'
        "---\nname: skill-a\n---\n\n# Body\n",
        # Missing 'name'
        "---\ndescription: A skill\n---\n\n# Body\n",
        # No body after frontmatter
        "---\nname: skill-b\ndescription: desc\n---\n",
        # description > 1024 chars
        f"---\nname: skill-c\ndescription: {'x' * 1025}\n---\n\n# Body\n",
    ],
)
def test_create_invalid_frontmatter_raises(writer: SkillWriter, bad_content: str) -> None:
    with pytest.raises(ValueError, match="frontmatter"):
        writer.create("valid-name", bad_content)


# ---------------------------------------------------------------------------
# R2.4  content size limit
# ---------------------------------------------------------------------------


def test_create_content_too_large_raises(writer: SkillWriter) -> None:
    huge_body = "x" * 100_001
    content = f"---\nname: big-skill\ndescription: desc\n---\n\n{huge_body}"
    with pytest.raises(ValueError, match="size"):
        writer.create("big-skill", content)


# ---------------------------------------------------------------------------
# R2.5  edit — full rewrite
# ---------------------------------------------------------------------------


def test_edit_replaces_content(writer: SkillWriter, skill_root: Path) -> None:
    writer.create("edit-skill", _VALID_FRONTMATTER.replace("test-skill", "edit-skill"))
    new_content = "---\nname: edit-skill\ndescription: Updated\n---\n\n# New Body\n"
    writer.edit("edit-skill", new_content)
    result = (skill_root / "edit-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert result == new_content


def test_edit_nonexistent_raises(writer: SkillWriter) -> None:
    with pytest.raises(ValueError, match="not found"):
        writer.edit("nonexistent", _VALID_FRONTMATTER)


def test_edit_invalidates_cache(writer: SkillWriter, registry: SkillRegistry) -> None:
    writer.create("cached-skill", _VALID_FRONTMATTER.replace("test-skill", "cached-skill"))
    _ = registry.list_skills()  # warm cache
    new_content = "---\nname: cached-skill\ndescription: Updated desc\n---\n\n# Body\n"
    writer.edit("cached-skill", new_content)
    skills = registry.list_skills()
    descs = {s.name: s.description for s in skills}
    assert descs.get("cached-skill") == "Updated desc"


# ---------------------------------------------------------------------------
# R2.6  patch — find-and-replace
# ---------------------------------------------------------------------------


def test_patch_replaces_substring(writer: SkillWriter, skill_root: Path) -> None:
    content = "---\nname: patch-skill\ndescription: desc\n---\n\n# Body\n\nOld text here."
    writer.create("patch-skill", content)
    writer.patch("patch-skill", old_string="Old text here.", new_string="New text here.")
    result = (skill_root / "patch-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "New text here." in result
    assert "Old text here." not in result


def test_patch_nonexistent_skill_raises(writer: SkillWriter) -> None:
    with pytest.raises(ValueError, match="not found"):
        writer.patch("ghost", old_string="x", new_string="y")


def test_patch_old_string_not_found_raises(writer: SkillWriter) -> None:
    writer.create("p-skill", _VALID_FRONTMATTER.replace("test-skill", "p-skill"))
    with pytest.raises(ValueError, match="not found"):
        writer.patch("p-skill", old_string="DOES_NOT_EXIST", new_string="y")


def test_patch_invalidates_cache(writer: SkillWriter, registry: SkillRegistry) -> None:
    content = "---\nname: pat2\ndescription: before patch\n---\n\n# Body\n"
    writer.create("pat2", content)
    _ = registry.list_skills()
    writer.patch("pat2", old_string="before patch", new_string="after patch")
    skills = registry.list_skills()
    descs = {s.name: s.description for s in skills}
    assert descs.get("pat2") == "after patch"


# ---------------------------------------------------------------------------
# R2.7  Atomic write — SKILL.md produced atomically
# ---------------------------------------------------------------------------


def test_create_produces_complete_file(writer: SkillWriter, skill_root: Path) -> None:
    writer.create("atomic-skill", _VALID_FRONTMATTER.replace("test-skill", "atomic-skill"))
    file_path = skill_root / "atomic-skill" / "SKILL.md"
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert content.startswith("---")
