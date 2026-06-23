"""Shared AGENTS.md loader + git-root helpers (feat-428).

Two project-instruction injection mechanisms (startup system-prompt injection
and read-triggered nested loading) share these three pure-core helpers:

- ``load_agents_md``    — read an AGENTS.md and expand its ``@import`` directives.
- ``find_outermost_git_root`` — single walk-up to the outermost git root.
- ``iter_agents_md_chain``     — yield existing AGENTS.md on a directory range.

The ``@import`` syntax mirrors CC's ``claudemd.ts`` (decision 6): ``@path`` /
``@./rel`` / ``@~/home`` / ``@/abs``, recognised only in leaf text (not inside
fenced code blocks), expanded recursively up to depth 5 with a Set cycle guard,
and missing targets silently ignored.

Pure core module: only ``pathlib`` / ``re`` — no platform / products imports.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

AGENTS_MD_FILENAME = "AGENTS.md"

# Provenance: CC-aligned — MAX_INCLUDE_DEPTH in claude-code claudemd.ts.
_MAX_IMPORT_DEPTH = 5

# Provenance: CC-aligned — includeRegex in claudemd.ts extractIncludePathsFromTokens:
#   /(?:^|\s)@((?:[^\s\\]|\\ )+)/g — an @ preceded by start-of-line or whitespace,
#   capturing a path that may contain backslash-escaped spaces.
_IMPORT_RE = re.compile(r"(?:^|\s)@((?:[^\s\\]|\\ )+)")

# Fenced code block delimiters (``` or ~~~). We skip @import inside fences to
# match CC's "leaf text nodes only (not inside code blocks)" rule. A lightweight
# line scanner is used instead of a full markdown lexer — the project has no
# marked-equivalent dependency and this covers the documented case.
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")

# Inline code span (`...`). CC's leaf-text rule also excludes codespan tokens, so
# an @path written inline as `@foo` must not be treated as an import. Each
# non-fenced line has its code spans stripped before @import extraction.
_CODESPAN_RE = re.compile(r"`[^`]*`")


def _is_valid_import_path(path: str) -> bool:
    """Whether a captured @-token is an acceptable import path (CC-aligned).

    Accepts ``./rel``, ``~/home``, ``/abs`` (but not the bare root ``/``), and
    bare relative paths starting with an alphanumeric / ``.`` / ``_`` / ``-``.
    Rejects nested ``@`` and punctuation-leading garbage.
    """
    if not path:
        return False
    if path.startswith("./") or path.startswith("~/"):
        return True
    if path.startswith("/"):
        return path != "/"
    if path.startswith("@"):
        return False
    if re.match(r"^[#%^&*()]+", path):
        return False
    return bool(re.match(r"^[a-zA-Z0-9._-]", path))


def _extract_import_paths(content: str, base_dir: Path) -> list[Path]:
    """Resolve @import directives in ``content`` to absolute paths.

    Scans line by line, skipping fenced code blocks. Backslash-escaped spaces in
    the captured path are unescaped; ``#fragment`` suffixes are stripped (both
    CC-aligned). Returns resolved absolute paths in first-seen order, deduped.
    """
    resolved: list[Path] = []
    seen: set[str] = set()
    in_fence = False
    fence_marker = ""
    for line in content.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]  # ` or ~
            elif marker[0] == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        # Strip inline code spans (`...`) before extraction — CC excludes codespan
        # tokens, so an inline `@foo` is not an import. Replace with a space so a
        # span never glues neighbouring tokens into a spurious match.
        line = _CODESPAN_RE.sub(" ", line)
        for match in _IMPORT_RE.finditer(line):
            raw = match.group(1)
            hash_index = raw.find("#")
            if hash_index != -1:
                raw = raw[:hash_index]
            raw = raw.replace("\\ ", " ")
            if not _is_valid_import_path(raw):
                continue
            target = Path(raw).expanduser()
            if not target.is_absolute():
                target = base_dir / target
            target = target.resolve()
            key = str(target)
            if key not in seen:
                seen.add(key)
                resolved.append(target)
    return resolved


def load_agents_md(
    path: Path,
    *,
    _seen: set[str] | None = None,
    _depth: int = 0,
) -> str | None:
    """Read an AGENTS.md and return its content with ``@import`` expanded.

    Args:
        path: Absolute path to the AGENTS.md (or any markdown file referenced via
            @import).
        _seen: Internal cycle-guard set of already-visited absolute paths.
        _depth: Internal recursion depth counter (cap = 5).

    Returns:
        The file's text with each ``@import`` directive replaced inline by the
        expanded content of its target (recursively, up to depth 5). Returns
        ``None`` when ``path`` does not exist / is not a readable file. Missing
        @import targets are silently ignored (CC-aligned).
    """
    resolved = path.expanduser().resolve()
    key = str(resolved)

    if _seen is None:
        _seen = set()
    if key in _seen:
        return None
    _seen.add(key)

    try:
        content = resolved.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None

    if _depth >= _MAX_IMPORT_DEPTH:
        return content

    base_dir = resolved.parent
    parts = [content]
    for target in _extract_import_paths(content, base_dir):
        expanded = load_agents_md(target, _seen=_seen, _depth=_depth + 1)
        if expanded is not None:
            parts.append(expanded)
    return "\n\n".join(parts)


def find_outermost_git_root(start_dir: Path) -> Path | None:
    """Return the outermost git root at or above ``start_dir``, else None.

    Walks up from ``start_dir`` to the filesystem root in a single pass,
    recording the highest directory that contains a ``.git`` entry (either a
    directory — normal repo — or a file — worktree / submodule gitlink). The
    *outermost* (highest) such directory is returned so nested repositories'
    outer instructions are covered (decision 7). Returns None when no ``.git``
    is found anywhere on the chain.
    """
    resolved = start_dir.expanduser().resolve()
    outermost: Path | None = None
    current = resolved
    while True:
        if (current / ".git").exists():
            outermost = current  # keep climbing; last hit = outermost
        parent = current.parent
        if parent == current:
            break
        current = parent
    return outermost


def iter_agents_md_chain(file_dir: Path, *, top: Path) -> Iterator[Path]:
    """Yield existing AGENTS.md absolute paths on the ``[file_dir … top]`` range.

    Iterates from ``file_dir`` upward through each ancestor directory until
    (and including) ``top``, yielding the absolute path of each directory's
    ``AGENTS.md`` that exists. Yields nearest-first (deepest directory first).

    Args:
        file_dir: Deepest directory of the range (the read file's directory).
        top: Inclusive upper bound directory (workspace root or outermost git
            root). Iteration stops after this directory.
    """
    file_dir = file_dir.expanduser().resolve()
    top = top.expanduser().resolve()
    current = file_dir
    while True:
        candidate = current / AGENTS_MD_FILENAME
        if candidate.is_file():
            yield candidate
        if current == top:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
