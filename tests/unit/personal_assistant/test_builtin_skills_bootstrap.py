"""Tests for PA package builtin skill installation."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.gateway.bootstrap import install_builtin_skills


def test_install_builtin_skills_copies_missing_distiller(tmp_path: Path) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"

    installed = install_builtin_skills(target_root=target_root)

    skill_path = target_root / "conversation-skill-distiller" / "SKILL.md"
    assert skill_path.is_file()
    assert "conversation-skill-distiller" in installed
    content = skill_path.read_text(encoding="utf-8")
    assert "source_jsonl_paths" in content
    assert "target_scope" in content
    assert "skill_manage" in content


def test_install_builtin_skills_does_not_overwrite_user_skill(tmp_path: Path) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    skill_dir = target_root / "conversation-skill-distiller"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("user-owned skill", encoding="utf-8")

    installed = install_builtin_skills(target_root=target_root)

    assert "conversation-skill-distiller" not in installed
    assert skill_path.read_text(encoding="utf-8") == "user-owned skill"

