"""Canonical skill metadata model and filesystem-backed discovery registry."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Describe one discovered skill file and its resolved metadata."""

    name: str
    description: str
    location: Path
    base_dir: Path


class SkillRegistry:
    """Discover and cache skills from configured root directories."""

    def __init__(self, *, search_roots: Sequence[Path]) -> None:
        self._search_roots = tuple(root.expanduser().resolve() for root in search_roots)
        self._cache: tuple[SkillMetadata, ...] | None = None

    def list_skills(self, *, refresh: bool = False) -> tuple[SkillMetadata, ...]:
        """Return discovered skills, optionally refreshing the filesystem scan."""

        if self._cache is None or refresh:
            self._cache = self._discover_skills()
        return self._cache

    def _discover_skills(self) -> tuple[SkillMetadata, ...]:
        skills_by_name: dict[str, SkillMetadata] = {}
        for root in self._search_roots:
            if not root.exists():
                continue
            discovered_files: list[Path] = []
            for dir_path, _, file_names in os.walk(root, followlinks=True):
                if "SKILL.md" not in file_names:
                    continue
                discovered_files.append(Path(dir_path) / "SKILL.md")
            for skill_file in sorted(discovered_files):
                metadata = _parse_skill_metadata(skill_file)
                if metadata.name in skills_by_name:
                    continue
                skills_by_name[metadata.name] = metadata
        return tuple(sorted(skills_by_name.values(), key=lambda item: item.name))


_BLOCK_SCALAR_MARKERS = frozenset({"|", "|-", "|+", ">", ">-", ">+"})


def _parse_skill_metadata(skill_file: Path) -> SkillMetadata:
    resolved_file = skill_file.expanduser().resolve()
    frontmatter, body_lines = _extract_frontmatter_and_body(resolved_file)
    name = _normalize_frontmatter_text(frontmatter.get("name")) or resolved_file.parent.name
    raw_desc = _normalize_frontmatter_text(frontmatter.get("description"))
    # 历史 bug：`description: |` 被误解析为字面量 "|"；块标量需在 frontmatter 内吞后续缩进行的正文
    if raw_desc in _BLOCK_SCALAR_MARKERS:
        raw_desc = ""
    description = raw_desc or _extract_description(body_lines)
    return SkillMetadata(
        name=name,
        description=description,
        location=resolved_file,
        base_dir=resolved_file.parent,
    )


def _looks_like_root_frontmatter_key_line(line: str) -> bool:
    """判定是否为 `key:` 形式的顶层 frontmatter 行（非正文续行）。"""
    if not line.strip() or line[0].isspace():
        return False
    if ":" not in line:
        return False
    key_part = line.split(":", 1)[0].strip()
    if not key_part:
        return False
    return all(ch.isalnum() or ch in "-_" for ch in key_part)


def _dedent_indented_block(lines: Sequence[str]) -> str:
    """去掉块标量共有前导空格，合并为一段文本。"""
    if not lines:
        return ""
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return ""
    cut = min(len(ln) - len(ln.lstrip(" ")) for ln in non_empty)
    parts: list[str] = []
    for ln in lines:
        if not ln.strip():
            parts.append("")
            continue
        parts.append(ln[cut:].rstrip() if len(ln) >= cut else ln.strip())
    return "\n".join(parts).strip()


def _extract_frontmatter_and_body(skill_file: Path) -> tuple[Mapping[str, str], tuple[str, ...]]:
    text = skill_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return {}, ()
    if lines[0].strip() != "---":
        return {}, tuple(lines)

    metadata: dict[str, str] = {}
    i = 1
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped == "---":
            return metadata, tuple(lines[i + 1 :])
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if ":" not in line or line[0].isspace():
            i += 1
            continue
        key, rest = line.split(":", 1)
        key = key.strip().lower()
        value = rest.strip()
        if "#" in value:
            value = value.split("#", 1)[0].strip()

        if value in _BLOCK_SCALAR_MARKERS:
            i += 1
            block_lines: list[str] = []
            while i < n:
                nxt = lines[i]
                if nxt.strip() == "---":
                    break
                if _looks_like_root_frontmatter_key_line(nxt):
                    break
                block_lines.append(nxt)
                i += 1
            metadata[key] = _dedent_indented_block(block_lines)
            continue

        metadata[key] = value
        i += 1

    return metadata, ()


def _normalize_frontmatter_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    return normalized


def _is_markdown_table_separator_row(line: str) -> bool:
    """识别 `| --- | --- |` 一类表格分隔行，避免当作正文摘要。"""
    s = line.strip()
    if not s.startswith("|") or "|" not in s[1:]:
        return False
    inner = s.strip("|").split("|")
    cells = [c.strip() for c in inner if c.strip() or c == ""]
    if not cells:
        return False
    return all(set(cell) <= set("-: ") for cell in cells if cell)


def _extract_description(lines: Sequence[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped == "|" or _is_markdown_table_separator_row(stripped):
            continue
        return stripped
    return ""
