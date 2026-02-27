from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    name: str
    description: str
    location: Path
    base_dir: Path


class SkillRegistry:
    def __init__(self, *, search_roots: Sequence[Path]) -> None:
        self._search_roots = tuple(root.expanduser().resolve() for root in search_roots)
        self._cache: tuple[SkillMetadata, ...] | None = None

    def list_skills(self, *, refresh: bool = False) -> tuple[SkillMetadata, ...]:
        if self._cache is None or refresh:
            self._cache = self._discover_skills()
        return self._cache

    def _discover_skills(self) -> tuple[SkillMetadata, ...]:
        skills_by_name: dict[str, SkillMetadata] = {}
        for root in self._search_roots:
            if not root.exists():
                continue
            for skill_file in sorted(root.rglob("SKILL.md")):
                metadata = _parse_skill_metadata(skill_file)
                if metadata.name in skills_by_name:
                    continue
                skills_by_name[metadata.name] = metadata
        return tuple(sorted(skills_by_name.values(), key=lambda item: item.name))


def _parse_skill_metadata(skill_file: Path) -> SkillMetadata:
    resolved_file = skill_file.expanduser().resolve()
    frontmatter, body_lines = _extract_frontmatter_and_body(resolved_file)
    name = frontmatter.get("name") or resolved_file.parent.name
    description = frontmatter.get("description") or _extract_description(body_lines)
    return SkillMetadata(
        name=name,
        description=description,
        location=resolved_file,
        base_dir=resolved_file.parent,
    )


def _extract_frontmatter_and_body(skill_file: Path) -> tuple[Mapping[str, str], tuple[str, ...]]:
    text = skill_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return {}, ()
    if lines[0].strip() != "---":
        return {}, tuple(lines)

    metadata: dict[str, str] = {}
    body_start = 1
    for index, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "---":
            body_start = index + 1
            break
        if ":" not in line:
            continue
        key, value = line.split(":", maxsplit=1)
        metadata[key.strip().lower()] = value.strip()
    return metadata, tuple(lines[body_start:])


def _extract_description(lines: Sequence[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped
    return ""
