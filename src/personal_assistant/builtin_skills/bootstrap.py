"""Install packaged personal assistant built-in skills into user runtime roots."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import fcntl
from importlib import resources
import logging
import os
from pathlib import Path
import shutil
import tempfile


DEFAULT_BUILTIN_SKILL_TARGET_ROOT = Path("~/.nanoassistant/skills")
"""Default user-global skill root consumed by the PA kernel resolver."""

_BUILTIN_SKILLS_PACKAGE = "personal_assistant.builtin_skills"
_SYNC_LOCK_FILENAME = ".builtin-skills-sync.lock"
_log = logging.getLogger(__name__)


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


@contextmanager
def _builtin_skill_sync_lock(destination_root: Path) -> Iterator[None]:
    """Serialize replacement of one user-global built-in skill root."""
    lock_path = destination_root / _SYNC_LOCK_FILENAME
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _sync_skill_directory(*, source: Path, destination: Path) -> None:
    destination_root = destination.parent
    skill_name = destination.name
    scratch_root = destination_root / ".archive"
    scratch_root.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{skill_name}.staging-", dir=scratch_root))
    backup: Path | None = None
    try:
        shutil.copytree(source, staging, dirs_exist_ok=True)
        if _path_exists(destination):
            backup = Path(
                tempfile.mkdtemp(prefix=f".{skill_name}.backup-", dir=scratch_root)
            )
            backup.rmdir()
            destination.replace(backup)
        try:
            staging.replace(destination)
        except Exception:
            if backup is not None and _path_exists(backup):
                if _path_exists(destination):
                    _remove_path(destination)
                backup.replace(destination)
            raise
        if backup is not None and _path_exists(backup):
            try:
                _remove_path(backup)
            except Exception:  # noqa: BLE001
                _log.warning(
                    "failed to remove built-in skill backup '%s'",
                    backup,
                    exc_info=True,
                )
    finally:
        if _path_exists(staging):
            try:
                _remove_path(staging)
            except Exception:  # noqa: BLE001
                _log.warning(
                    "failed to remove built-in skill staging directory '%s'",
                    staging,
                    exc_info=True,
                )


def install_builtin_skills(*, target_root: Path | str | None = None) -> dict[str, Path]:
    """Synchronize packaged built-in skills into the user runtime root.

    Args:
        target_root: Skill root to install into. Defaults to
            ``~/.nanoassistant/skills``. Tests may pass a temporary root.

    Returns:
        Mapping of every successfully synchronized built-in skill name to its
        destination ``SKILL.md`` path.

    Side Effects:
        Creates the target root and replaces each packaged built-in skill directory
        with the current package version. Names not declared by the package remain
        untouched. A failed skill keeps its previous complete directory when one
        exists, is logged, and does not prevent other skills from synchronizing.
    """

    destination_root = (
        Path(target_root)
        if target_root is not None
        else DEFAULT_BUILTIN_SKILL_TARGET_ROOT
    ).expanduser()
    destination_root.mkdir(parents=True, exist_ok=True)

    root = resources.files(_BUILTIN_SKILLS_PACKAGE)
    synchronized: dict[str, Path] = {}
    with _builtin_skill_sync_lock(destination_root):
        for source in sorted(root.iterdir(), key=lambda item: item.name):
            if not source.is_dir():
                continue
            source_skill = source.joinpath("SKILL.md")
            if not source_skill.is_file():
                continue
            skill_name = source.name
            destination = destination_root / skill_name
            target_skill = destination / "SKILL.md"
            try:
                with resources.as_file(source) as source_path:
                    _sync_skill_directory(source=source_path, destination=destination)
            except Exception:  # noqa: BLE001
                _log.warning(
                    "failed to synchronize built-in personal assistant skill '%s'",
                    skill_name,
                    exc_info=True,
                )
                continue
            synchronized[skill_name] = target_skill
    return synchronized
