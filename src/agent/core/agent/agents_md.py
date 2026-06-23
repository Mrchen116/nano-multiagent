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
from typing import Callable, Iterator

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

# Module-level compiled patterns for _is_valid_import_path (fix r1: hoisted from
# inline re.match so they compile once, not per captured token).
_PUNCT_LEADING_RE = re.compile(r"^[#%^&*()]+")
_VALID_LEADING_RE = re.compile(r"^[a-zA-Z0-9._-]")


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
    if _PUNCT_LEADING_RE.match(path):
        return False
    return bool(_VALID_LEADING_RE.match(path))


def _resolve_import_target(raw: str, base_dir: Path) -> Path | None:
    """Resolve one captured @-token to an absolute path, or None if invalid.

    Strips a trailing ``#fragment`` and unescapes backslash-escaped spaces
    (both CC-aligned), validates the leading characters, then resolves relative
    paths against ``base_dir``.
    """
    hash_index = raw.find("#")
    if hash_index != -1:
        raw = raw[:hash_index]
    raw = raw.replace("\\ ", " ")
    if not _is_valid_import_path(raw):
        return None
    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = base_dir / target
    return target.resolve()


def _expand_line_imports(
    line: str,
    base_dir: Path,
    expand: "Callable[[Path], str | None]",
) -> str:
    """Replace each @import directive on one (non-fenced) line inline (fix r1).

    Inline code spans are masked out first (CC excludes codespan tokens). Each
    valid @import token is replaced **in place** by its expanded content (or
    dropped when the target is missing / already seen), matching CC's inline
    replacement and this module's "replaced inline" docstring contract.
    """
    # Mask inline code spans so an inline `@foo` is neither an import nor able to
    # glue neighbours into a spurious match; matched offsets stay aligned because
    # the mask is the same length as the span.
    masked = _CODESPAN_RE.sub(lambda m: " " * len(m.group(0)), line)

    out: list[str] = []
    cursor = 0
    for match in _IMPORT_RE.finditer(masked):
        target = _resolve_import_target(match.group(1), base_dir)
        if target is None:
            continue
        # Keep everything up to the @ (group may include a leading space via
        # (?:^|\s)); the @path token itself is replaced by the expansion.
        at_index = line.index("@", match.start())
        out.append(line[cursor:at_index])
        expanded = expand(target)
        if expanded is not None:
            out.append(expanded)
        cursor = match.end()
    out.append(line[cursor:])
    return "".join(out)


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
        # fix r1: errors="replace" so a non-UTF-8 AGENTS.md is still surfaced
        # (lossy) rather than silently dropped to None.
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if _depth >= _MAX_IMPORT_DEPTH:
        return content

    base_dir = resolved.parent

    def _expand(target: Path) -> str | None:
        return load_agents_md(target, _seen=_seen, _depth=_depth + 1)

    # fix r1: expand @import inline (in place), tracking fenced code blocks with
    # CommonMark close semantics (close fence must be same char and length >= the
    # opening fence). @import inside a fence or inline code span is not expanded.
    out_lines: list[str] = []
    fence_char = ""  # "`" or "~" while inside a fence, else ""
    fence_len = 0
    for line in content.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            char = marker[0]
            length = len(marker)
            if not fence_char:
                fence_char = char
                fence_len = length
                out_lines.append(line)
                continue
            if char == fence_char and length >= fence_len:
                fence_char = ""
                fence_len = 0
                out_lines.append(line)
                continue
            # Same/other fence char but too short to close — stays inside fence.
            out_lines.append(line)
            continue
        if fence_char:
            out_lines.append(line)
            continue
        out_lines.append(_expand_line_imports(line, base_dir, _expand))
    return "\n".join(out_lines)


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
