"""SKILL.md frontmatter：YAML 块标量 description: | 与正文摘要兜底。"""

from pathlib import Path

from agent.core.skills.registry import SkillRegistry


def test_description_literal_block_not_single_pipe(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: demo-skill
description: |
  Line one of skill
  Line two
---
# Title

Body paragraph.
""",
        encoding="utf-8",
    )
    reg = SkillRegistry(search_roots=(tmp_path,))
    skills = reg.list_skills(refresh=True)
    assert len(skills) == 1
    assert skills[0].name == "demo-skill"
    assert "Line one" in skills[0].description
    assert "Line two" in skills[0].description
    assert skills[0].description.strip() != "|"


def test_description_pipe_only_falls_back_to_body(tmp_path: Path) -> None:
    """旧解析器会把 `description: |` 存成 "|"；应改从正文取第一段。"""
    skill_dir = tmp_path / "legacy-pipe"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: legacy-pipe
description: |
---
Real summary from body.
""",
        encoding="utf-8",
    )
    reg = SkillRegistry(search_roots=(tmp_path,))
    skills = reg.list_skills(refresh=True)
    assert skills[0].description == "Real summary from body."


def test_skips_markdown_table_separator_in_body(tmp_path: Path) -> None:
    skill_dir = tmp_path / "tbl"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: tbl
---

| --- | --- |

Actual text here.
""",
        encoding="utf-8",
    )
    reg = SkillRegistry(search_roots=(tmp_path,))
    skills = reg.list_skills(refresh=True)
    assert skills[0].description.startswith("Actual text")
