"""Install packaged personal assistant built-in skills into user runtime roots."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
import shutil


DEFAULT_BUILTIN_SKILL_TARGET_ROOT = Path("~/.nanoassistant/skills")
"""Default user-global skill root consumed by the PA kernel resolver."""

_BUILTIN_SKILLS_PACKAGE = "personal_assistant.builtin_skills"


def install_builtin_skills(
    *, target_root: Path | str | None = None
) -> dict[str, Path]:
    """Install packaged built-in skills that are missing from the user root.

    Args:
        target_root: Skill root to install into. Defaults to
            ``~/.nanoassistant/skills``. Tests may pass a temporary root.

    Returns:
        Mapping of skill name to installed ``SKILL.md`` path. Existing user
        skills are omitted and left untouched.

    Side Effects:
        Creates the target root and copies each packaged ``<skill>/`` directory
        when ``<target>/<skill>/SKILL.md`` does not already exist.
    """

    destination_root = (
        Path(target_root) if target_root is not None else DEFAULT_BUILTIN_SKILL_TARGET_ROOT
    ).expanduser()
    destination_root.mkdir(parents=True, exist_ok=True)

    installed: dict[str, Path] = {}
    root = resources.files(_BUILTIN_SKILLS_PACKAGE)
    for source in root.iterdir():
        if not source.is_dir():
            continue
        source_skill = source.joinpath("SKILL.md")
        if not source_skill.is_file():
            continue
        skill_name = source.name
        destination = destination_root / skill_name
        target_skill = destination / "SKILL.md"
        if target_skill.exists():
            continue
        with resources.as_file(source) as source_path:
            shutil.copytree(source_path, destination, dirs_exist_ok=True)
        installed[skill_name] = target_skill
    return installed
