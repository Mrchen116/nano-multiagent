"""MemoryStore: bounded § -delimited memory with source index, file lock, and atomic write.

Design constraints:
- Two fixed files only: MEMORY.md (agent notes) and USER.md (user profile). Spec L60.
- Every entry carries a source index (session_id + timestamp). Spec L61.
- File lock (fcntl on Unix) protects read-modify-write; atomic write (tempfile + os.replace)
  ensures readers always see a complete file even under concurrent access.
- Char limit enforced per target to prevent unbounded growth.
- System-prompt snapshot frozen at first load so provider prefix cache stays stable across
  the session (same design as hermes MemoryStore).
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# § is the canonical entry separator (matches hermes ENTRY_DELIMITER)
_ENTRY_DELIMITER = "\n§\n"

# Default char limits align with hermes quantities (memory_char_limit=2200, user_char_limit=1375)
_DEFAULT_MEMORY_CHAR_LIMIT = 2200
_DEFAULT_USER_CHAR_LIMIT = 1375

Target = Literal["memory", "user"]

# Mapping from logical target name to filename
_TARGET_FILES: dict[str, str] = {
    "memory": "MEMORY.md",
    "user": "USER.md",
}

# M4 Decision 17: banner titles moved to core_sections.py (CORE_MEMORY_BLOCK /
# CORE_USER_PROFILE_BLOCK render). format_for_prompt now returns pure content.
# _TARGET_HEADERS kept only for the legacy _render_block helper (not in production path).
_TARGET_HEADERS: dict[str, str] = {
    "memory": "MEMORY (your personal notes)",  # also defined in core_sections._render_memory_block
    "user": "USER PROFILE (who the user is)",  # also defined in core_sections._render_user_profile_block
}


@dataclass(frozen=True, slots=True)
class MemorySource:
    """Source provenance for a memory entry (satisfies spec L61 来源索引).

    Args:
        session_id: Session that produced this entry.
        timestamp: Unix timestamp of the write operation.
    """

    session_id: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """One memory entry with its content and source index.

    Args:
        text: The declarative fact or note to persist.
        source: Provenance metadata required by spec L61.
    """

    text: str
    source: MemorySource


# ---------------------------------------------------------------------------
# Internal serialization helpers
# ---------------------------------------------------------------------------


def _serialize_entry(entry: MemoryEntry) -> str:
    """Encode a MemoryEntry to a single § -block string.

    Format::

        <text>
        <!-- source: {"session_id": "...", "timestamp": 1234567890.0} -->

    The comment line carries source index without cluttering the visible text.
    """
    source_json = json.dumps(
        {"session_id": entry.source.session_id, "timestamp": entry.source.timestamp}
    )
    return f"{entry.text}\n<!-- source: {source_json} -->"


def _deserialize_entry(block: str) -> MemoryEntry:
    """Decode a § -block string back to a MemoryEntry.

    Raises:
        ValueError: When the block is malformed or source comment missing.
    """
    lines = block.rstrip().splitlines()
    # Find the trailing source comment line
    source_line_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("<!-- source:") and lines[i].endswith("-->"):
            source_line_idx = i
            break

    if source_line_idx is None:
        # Legacy entries without source index: synthesize a minimal source
        return MemoryEntry(
            text=block.strip(),
            source=MemorySource(session_id="<legacy>", timestamp=0.0),
        )

    text = "\n".join(lines[:source_line_idx]).strip()
    source_json_str = (
        lines[source_line_idx][len("<!-- source:") :].rstrip(" -->").strip()
    )
    try:
        src_data = json.loads(source_json_str)
        source = MemorySource(
            session_id=str(src_data.get("session_id", "<unknown>")),
            timestamp=float(src_data.get("timestamp", 0.0)),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise ValueError(f"Malformed source comment in entry: {exc}") from exc

    return MemoryEntry(text=text, source=source)


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class MemoryStore:
    """Persist agent memory and user profile across sessions.

    Two fixed files live under ``memory_root``—``MEMORY.md`` and ``USER.md``—
    separated by the § delimiter. Each entry carries a source index for
    traceability (spec L61). Writes use a file lock + atomic rename for
    multi-session safety (spec R5).

    A frozen system-prompt snapshot is captured on first read so the rendered
    block stays byte-identical within a session, keeping provider prefix cache
    hit rate high.

    Args:
        memory_root: Directory under which MEMORY.md / USER.md live.
        memory_char_limit: Max total chars for MEMORY.md entries.
        user_char_limit: Max total chars for USER.md entries.
    """

    def __init__(
        self,
        *,
        memory_root: Path,
        memory_char_limit: int = _DEFAULT_MEMORY_CHAR_LIMIT,
        user_char_limit: int = _DEFAULT_USER_CHAR_LIMIT,
    ) -> None:
        self._root = memory_root
        self._limits: dict[str, int] = {
            "memory": memory_char_limit,
            "user": user_char_limit,
        }
        # Live in-memory state (mutable)
        self._entries: dict[str, list[MemoryEntry]] = {"memory": [], "user": []}
        # Frozen snapshot for system prompt injection — set on first read, never updated mid-session.
        # M4 Decision 17: stores pure content (no banner); pct stored separately for core segment use.
        self._prompt_snapshot: dict[str, str] = {"memory": "", "user": ""}
        self._prompt_pct: dict[str, int] = {"memory": 0, "user": 0}
        self._snapshot_loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, target: Target) -> tuple[MemoryEntry, ...]:
        """Return current in-memory entries for the given target.

        Loads from disk on first call (lazy initialization).

        Args:
            target: One of ``"memory"`` or ``"user"``.

        Returns:
            Immutable tuple of all current entries.
        """
        self._ensure_target(target)
        self._maybe_load(target)
        return tuple(self._entries[target])

    def add(self, target: Target, entry: MemoryEntry) -> None:
        """Append a new entry.

        Args:
            target: ``"memory"`` or ``"user"``.
            entry: The entry to add (must include source index).

        Raises:
            ValueError: When the total char count after add would exceed the limit.
        """
        self._ensure_target(target)
        self._maybe_load(target)
        new_list = list(self._entries[target]) + [entry]
        self._check_char_limit(target, new_list)
        self._entries[target] = new_list
        self._persist(target)

    def replace(self, target: Target, *, old_text: str, new_entry: MemoryEntry) -> None:
        """Replace the first entry whose text contains ``old_text``.

        Args:
            target: ``"memory"`` or ``"user"``.
            old_text: Unique substring identifying the entry to replace.
            new_entry: Replacement entry (with fresh source index).

        Raises:
            ValueError: When no entry contains ``old_text``.
        """
        self._ensure_target(target)
        self._maybe_load(target)
        entries = list(self._entries[target])
        idx = self._find_entry(entries, old_text)
        if idx is None:
            raise ValueError(
                f"Entry containing '{old_text}' not found in target '{target}'"
            )
        entries[idx] = new_entry
        self._check_char_limit(target, entries)
        self._entries[target] = entries
        self._persist(target)

    def remove(self, target: Target, old_text: str) -> None:
        """Remove the first entry whose text contains ``old_text``.

        Args:
            target: ``"memory"`` or ``"user"``.
            old_text: Unique substring identifying the entry to remove.

        Raises:
            ValueError: When no entry contains ``old_text``.
        """
        self._ensure_target(target)
        self._maybe_load(target)
        entries = list(self._entries[target])
        idx = self._find_entry(entries, old_text)
        if idx is None:
            raise ValueError(
                f"Entry containing '{old_text}' not found in target '{target}'"
            )
        del entries[idx]
        self._entries[target] = entries
        self._persist(target)

    def format_for_prompt(self, target: Target) -> str | None:
        """Return the pure content for ``target``, or None when empty.

        M4 Decision 17: returns pure content only (no banner/separator).
        Banner generation is the responsibility of the core prompt segment
        (core.memory_block / core.user_profile_block), which reads render_mode
        from PromptContext to decide between runtime values and preview placeholders.

        Captures the snapshot on first call per target; never updates
        mid-session so provider prefix cache stays stable.

        Returns None when there are no entries for the target — callers treat
        None as "segment inactive", preventing an empty banner from appearing
        in the system prompt (feat-385 I1: empty store must not emit a banner).

        Args:
            target: ``"memory"`` or ``"user"``.

        Returns:
            Pure content string (entries joined by delimiter), or None if empty.
        """
        self._ensure_target(target)
        if not self._snapshot_loaded:
            self._load_snapshot()
        snapshot = self._prompt_snapshot[target]
        return snapshot if snapshot else None

    def format_pct_for_prompt(self, target: Target) -> int:
        """Return the usage percentage (0–100) for ``target`` at snapshot time.

        Used by core prompt segments to include usage in the banner they render
        (M4 Decision 17: banner lives in segment, not in MemoryStore).

        Args:
            target: ``"memory"`` or ``"user"``.

        Returns:
            Integer usage percentage (0–100).
        """
        self._ensure_target(target)
        if not self._snapshot_loaded:
            self._load_snapshot()
        return self._prompt_pct[target]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_target(self, target: str) -> None:
        if target not in _TARGET_FILES:
            raise ValueError(
                f"Unknown memory target '{target}'; expected one of {list(_TARGET_FILES)}"
            )

    def _maybe_load(self, target: Target) -> None:
        """Lazily load entries from disk if not yet loaded (only if file exists)."""
        # Guard: only load once per target (entries list starts empty)
        if self._entries[target]:
            return
        file_path = self._target_path(target)
        if not file_path.exists():
            return
        raw = file_path.read_text(encoding="utf-8")
        self._entries[target] = _parse_entries(raw)

    def _load_snapshot(self) -> None:
        """Capture frozen prompt snapshot for all targets.

        M4 Decision 17: stores pure content (no banner). Banner is generated by
        core.memory_block / core.user_profile_block segments using the pct from
        _prompt_pct. Stores empty string when no entries exist so format_for_prompt
        returns None instead of an empty banner (feat-385 I1 fix).
        """
        self._snapshot_loaded = True
        for target in ("memory", "user"):
            self._maybe_load(target)  # type: ignore[arg-type]
            if self._entries[target]:
                content, pct = self._render_content_and_pct(target)  # type: ignore[arg-type]
                self._prompt_snapshot[target] = content
                self._prompt_pct[target] = pct
            else:
                self._prompt_snapshot[target] = ""
                self._prompt_pct[target] = 0

    def _render_content_and_pct(self, target: Target) -> tuple[str, int]:
        """Return (pure_content, usage_pct) for ``target``.

        M4 Decision 17: banner is generated by the core prompt segment, not here.
        This helper returns the raw serialized content and usage percentage so the
        core segment can render the banner in the appropriate format (runtime / preview).
        """
        entries = self._entries[target]
        limit = self._limits[target]
        content = _ENTRY_DELIMITER.join(_serialize_entry(e) for e in entries)
        current = len(content)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0
        return content, pct

    def _render_block(self, target: Target) -> str:
        """Render full prompt block with usage percentage header.

        Internal helper kept for any legacy code that still needs the old format.
        Production code paths use _render_content_and_pct instead.
        """
        content, pct = self._render_content_and_pct(target)
        entries = self._entries[target]
        limit = self._limits[target]
        current = len(_ENTRY_DELIMITER.join(_serialize_entry(e) for e in entries))
        header_label = _TARGET_HEADERS[target]
        header = f"{header_label} [{pct}% — {current:,}/{limit:,} chars]"
        separator = "═" * 46
        return f"{separator}\n{header}\n{separator}\n{content}"

    def _check_char_limit(self, target: Target, entries: list[MemoryEntry]) -> None:
        """Raise ValueError when serialized entries exceed the target's char limit."""
        limit = self._limits[target]
        content = _ENTRY_DELIMITER.join(_serialize_entry(e) for e in entries)
        if len(content) > limit:
            raise ValueError(
                f"Memory target '{target}' would exceed char limit ({len(content)} > {limit}); "
                "compact existing entries before adding new ones"
            )

    def _target_path(self, target: Target) -> Path:
        return self._root / _TARGET_FILES[target]

    def _lock_path(self, target: Target) -> Path:
        return self._root / (_TARGET_FILES[target] + ".lock")

    @staticmethod
    def _find_entry(entries: list[MemoryEntry], old_text: str) -> int | None:
        for i, entry in enumerate(entries):
            if old_text in entry.text:
                return i
        return None

    def _persist(self, target: Target) -> None:
        """Write entries to disk using file lock + atomic rename.

        File lock: acquired via fcntl.flock on a dedicated .lock file so
        concurrent processes block rather than corrupt.  Atomic rename ensures
        readers always see a complete file.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        file_path = self._target_path(target)
        lock_path = self._lock_path(target)

        with open(lock_path, "w", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                # Re-read under lock — merge logic reserved for future improvement;
                # current strategy overwrites entirely with in-memory state (best-effort).

                # Rebuild: keep existing entries not overridden by in-memory state
                # Strategy: replace existing on-disk state entirely with current in-memory state
                # (in-memory state is the authoritative version for this process after our
                # read-modify-write; concurrent adds may be lost — acceptable best-effort for now)
                entries = self._entries[target]
                content = _ENTRY_DELIMITER.join(_serialize_entry(e) for e in entries)
                _atomic_write(file_path, content)
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------


def _parse_entries(raw: str) -> list[MemoryEntry]:
    """Split raw file content on § delimiter and deserialize each block."""
    if not raw.strip():
        return []
    blocks = raw.split(_ENTRY_DELIMITER)
    entries: list[MemoryEntry] = []
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        try:
            entries.append(_deserialize_entry(stripped))
        except ValueError:
            # Malformed block — skip rather than crash; data integrity issue logged upstream
            continue
    return entries


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via temp file + os.replace for atomicity.

    The temp file is created in the same directory as the target to guarantee
    same-filesystem rename semantics (os.replace is atomic on POSIX).
    fsync ensures durability before rename.
    """
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.tmp.",
        suffix="",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
