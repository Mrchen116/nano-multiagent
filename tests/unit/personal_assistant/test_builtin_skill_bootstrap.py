from __future__ import annotations

from pathlib import Path
import tomllib

from personal_assistant.builtin_skills.bootstrap import install_builtin_skills


def test_install_builtin_skills_copies_missing_feishu_doc(tmp_path: Path) -> None:
    target_root = tmp_path / "home" / ".nanoassistant" / "skills"

    installed = install_builtin_skills(target_root=target_root)

    target = target_root / "feishu-doc" / "SKILL.md"
    assert target.is_file()
    assert "feishu-cli" in target.read_text(encoding="utf-8")
    assert installed["feishu-doc"] == target


def test_install_builtin_skills_does_not_overwrite_existing_user_skill(
    tmp_path: Path,
) -> None:
    target = tmp_path / "home" / ".nanoassistant" / "skills" / "feishu-doc"
    target.mkdir(parents=True)
    skill_file = target / "SKILL.md"
    skill_file.write_text("user customized skill\n", encoding="utf-8")

    installed = install_builtin_skills(target_root=target.parent)

    assert skill_file.read_text(encoding="utf-8") == "user customized skill\n"
    assert installed == {}


def test_builtin_skills_are_included_as_package_data() -> None:
    pyproject_path = Path(__file__).parents[3] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    package_data = payload["tool"]["setuptools"]["package-data"]

    assert "personal_assistant" in package_data
    assert "builtin_skills/**" in package_data["personal_assistant"]
