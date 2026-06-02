"""SkillWriter: write-side operations for the skill filesystem.

Responsibilities:
- Create / edit (full rewrite) / patch (find-and-replace) SKILL.md files.
- Validate skill name (regex), frontmatter (required fields, description length, body presence),
  and content size before any write.
- Atomic write (temp + os.replace) ensures readers always see a complete file.
- Invalidate the SkillRegistry discovery cache after every successful write.

Architecture: ``core`` layer — no ``platform`` imports.
Path injection via constructor; caller (platform/tools) resolves the path.
"""

from __future__ import annotations

import re
from pathlib import Path

from agent.core.utils.fileio import atomic_write as _atomic_write

from .registry import SkillRegistry

# ---------------------------------------------------------------------------
# Constants (align with hermes skill_manager_tool.py values)
# ---------------------------------------------------------------------------

# name regex: first char must be alphanumeric; rest allow lowercase, digits, dot, dash, underscore
_VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_MAX_NAME_LENGTH = 64
_MAX_SKILL_CONTENT_CHARS = 100_000
_MAX_DESCRIPTION_CHARS = 1024

# Support-file subdirectories a skill may carry alongside SKILL.md (align with
# hermes ALLOWED_SUBDIRS). A skill is a directory; support files turn it into a
# class-level "umbrella" with bundled detail/templates/scripts rather than a
# single flat SKILL.md.
_ALLOWED_SUBDIRS = frozenset({"references", "templates", "scripts", "assets"})


class SkillWriter:
    """Write-side operations for user skills backed by a filesystem root.

    Args:
        skill_root: Directory under which per-skill subdirectories are created.
            Each skill lives at ``skill_root/<name>/SKILL.md``.
        registry: Discovery registry to invalidate after a successful write.
    """

    def __init__(self, *, skill_root: Path, registry: SkillRegistry) -> None:
        self._root = skill_root.expanduser().resolve()
        self._registry = registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, name: str, content: str) -> Path:
        """Create a new skill directory and SKILL.md.

        Args:
            name: Skill name; must match ``^[a-z0-9][a-z0-9._-]*$``, max 64 chars.
            content: Full SKILL.md content including frontmatter + body.

        Returns:
            Absolute path to the created SKILL.md file.

        Raises:
            ValueError: On name/frontmatter/size validation failure, or duplicate.
        """
        _validate_name(name)
        _validate_frontmatter(content)
        _validate_content_size(content)

        skill_dir = self._root / name
        if skill_dir.exists():
            raise ValueError(f"Skill '{name}' already exists at {skill_dir}")

        skill_dir.mkdir(parents=True, exist_ok=False)
        skill_file = skill_dir / "SKILL.md"
        _atomic_write(skill_file, content)
        self._registry.invalidate_cache()
        return skill_file

    def edit(self, name: str, content: str) -> Path:
        """Fully replace an existing skill's SKILL.md content.

        Args:
            name: Existing skill name.
            content: New full SKILL.md content.

        Returns:
            Absolute path to the updated SKILL.md file.

        Raises:
            ValueError: When skill is not found, or validation fails.
        """
        _validate_frontmatter(content)
        _validate_content_size(content)

        skill_file = self._find_skill_file(name)
        _atomic_write(skill_file, content)
        self._registry.invalidate_cache()
        return skill_file

    def patch(self, name: str, *, old_string: str, new_string: str) -> Path:
        """Apply a find-and-replace patch to an existing SKILL.md.

        Requires ``old_string`` to appear exactly once in the current content
        (to prevent ambiguous replacements). After replacement the resulting
        content is validated for size.

        Args:
            name: Existing skill name.
            old_string: Unique substring to replace; must be non-empty.
            new_string: Replacement string (may be empty string to delete).

        Returns:
            Absolute path to the patched SKILL.md file.

        Raises:
            ValueError: When skill not found, old_string not in content, or
                old_string matches more than once without ``replace_all``.
        """
        if not old_string:
            raise ValueError("old_string must not be empty")

        skill_file = self._find_skill_file(name)
        current = skill_file.read_text(encoding="utf-8")

        count = current.count(old_string)
        if count == 0:
            raise ValueError(
                f"old_string '{old_string[:50]}' not found in skill '{name}'"
            )
        if count > 1:
            raise ValueError(
                f"old_string '{old_string[:50]}' matches {count} times in skill '{name}'; "
                "provide a longer unique substring or use replace_all=True"
            )

        new_content = current.replace(old_string, new_string, 1)
        _validate_content_size(new_content)
        _atomic_write(skill_file, new_content)
        self._registry.invalidate_cache()
        return skill_file

    def write_file(self, name: str, file_path: str, file_content: str) -> Path:
        """Write a support file under an existing skill's directory.

        Support files turn a skill into a class-level umbrella: ``references/``
        for session detail / condensed knowledge banks, ``templates/`` for
        copy-and-modify starters, ``scripts/`` for re-runnable actions, ``assets/``
        for other bundled files.

        Args:
            name: Existing skill name.
            file_path: Relative path under the skill dir; first segment must be an
                allowed subdir, at least two segments, no ``..`` traversal.
            file_content: File body.

        Returns:
            Absolute path to the written support file.

        Raises:
            ValueError: On unknown skill, invalid path, or size violation.
        """
        skill_dir = self._require_skill_dir(name)
        rel = _validate_support_file_path(file_path)
        _validate_content_size(file_content)
        target = skill_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, file_content)
        self._registry.invalidate_cache()
        return target

    def remove_file(self, name: str, file_path: str) -> Path:
        """Remove a support file from an existing skill's directory.

        Args:
            name: Existing skill name.
            file_path: Relative support-file path (same validation as write_file).

        Returns:
            Absolute path of the removed file.

        Raises:
            ValueError: On unknown skill, invalid path, or missing file.
        """
        skill_dir = self._require_skill_dir(name)
        rel = _validate_support_file_path(file_path)
        target = skill_dir / rel
        if not target.is_file():
            raise ValueError(f"Support file '{file_path}' not found in skill '{name}'")
        target.unlink()
        self._registry.invalidate_cache()
        return target

    def list_support_files(self, name: str) -> list[str]:
        """Return the skill's support-file paths (relative, sorted), excluding SKILL.md."""
        skill_dir = self._require_skill_dir(name)
        out: list[str] = []
        for sub in sorted(_ALLOWED_SUBDIRS):
            subdir = skill_dir / sub
            if not subdir.is_dir():
                continue
            for f in sorted(subdir.rglob("*")):
                if f.is_file():
                    out.append(str(f.relative_to(skill_dir)))
        return out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_skill_file(self, name: str) -> Path:
        """Locate SKILL.md for an existing skill; raises ValueError if missing."""
        skill_file = self._root / name / "SKILL.md"
        if not skill_file.exists():
            raise ValueError(f"Skill '{name}' not found at {skill_file}")
        return skill_file

    def _require_skill_dir(self, name: str) -> Path:
        """Return an existing skill's directory; raises ValueError if missing."""
        _validate_name(name)
        skill_dir = self._root / name
        if not (skill_dir / "SKILL.md").exists():
            raise ValueError(f"Skill '{name}' not found at {skill_dir}")
        return skill_dir


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_name(name: str) -> None:
    """Raise ValueError when name fails regex or length constraints."""
    if not name:
        raise ValueError("Skill name must not be empty")
    if len(name) > _MAX_NAME_LENGTH:
        raise ValueError(
            f"Skill name too long ({len(name)} > {_MAX_NAME_LENGTH} chars): '{name[:20]}...'"
        )
    if not _VALID_NAME_RE.match(name):
        raise ValueError(
            f"Invalid skill name '{name}'; must match ^[a-z0-9][a-z0-9._-]*$ "
            "(lowercase letters, digits, dots, dashes, underscores; first char alphanumeric)"
        )


def _validate_support_file_path(file_path: str) -> Path:
    """Validate a support-file relative path; return the normalized Path.

    Mirrors hermes _validate_file_path: reject ``..`` traversal and absolute
    paths, require at least two segments (subdir + filename), and require the
    first segment to be an allowed subdir. This keeps writes confined to the
    skill's own ``references/`` / ``templates/`` / ``scripts/`` / ``assets/``.
    """
    if not file_path or not file_path.strip():
        raise ValueError("write_file requires a non-empty 'file_path'")
    rel = Path(file_path)
    if rel.is_absolute():
        raise ValueError(f"Support file path must be relative, got '{file_path}'")
    parts = rel.parts
    if any(p == ".." for p in parts):
        raise ValueError(f"Support file path must not contain '..': '{file_path}'")
    if len(parts) < 2:
        raise ValueError(
            f"Support file path must be '<subdir>/<file>' with at least two segments: '{file_path}'"
        )
    if parts[0] not in _ALLOWED_SUBDIRS:
        raise ValueError(
            f"Support file must live under {sorted(_ALLOWED_SUBDIRS)}; got first segment '{parts[0]}'"
        )
    return rel


def _validate_frontmatter(content: str) -> None:
    """Raise ValueError when SKILL.md frontmatter is absent or incomplete.

    Checks (align with hermes _validate_frontmatter):
    1. Content is non-empty and starts with '---'.
    2. Closing '---' is present.
    3. 'name' and 'description' fields are present.
    4. description is not longer than 1024 chars.
    5. Body after frontmatter is non-empty.
    """
    if not content or not content.strip():
        raise ValueError("Skill frontmatter is missing: content is empty")
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Skill frontmatter is missing: content must start with '---'")

    # Find closing ---
    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        raise ValueError("Skill frontmatter is missing: no closing '---' found")

    # Parse frontmatter fields
    fm_lines = lines[1:close_idx]
    fields: dict[str, str] = {}
    for line in fm_lines:
        if ":" in line and not line[0].isspace():
            key, _, val = line.partition(":")
            fields[key.strip().lower()] = val.strip()

    if "name" not in fields:
        raise ValueError("Skill frontmatter is missing required field 'name'")
    if "description" not in fields:
        raise ValueError("Skill frontmatter is missing required field 'description'")
    if len(fields["description"]) > _MAX_DESCRIPTION_CHARS:
        raise ValueError(
            f"Skill frontmatter 'description' too long ({len(fields['description'])} > {_MAX_DESCRIPTION_CHARS} chars)"
        )

    # Body must exist and be non-empty after frontmatter
    body_lines = lines[close_idx + 1 :]
    body = "\n".join(body_lines).strip()
    if not body:
        raise ValueError(
            "Skill frontmatter is present but body is empty; SKILL.md must have content after '---'"
        )


def _validate_content_size(content: str) -> None:
    """Raise ValueError when content exceeds maximum allowed size."""
    if len(content) > _MAX_SKILL_CONTENT_CHARS:
        raise ValueError(
            f"Skill content too large ({len(content):,} > {_MAX_SKILL_CONTENT_CHARS:,} chars)"
        )


# ---------------------------------------------------------------------------
