"""Unit tests for core/memory MemoryStore.

Covers: add / replace / remove / format_for_prompt / file lock + atomic write /
source index presence (L61) / fixed two-file contract (L60).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from agent.core.memory.store import MemoryEntry, MemorySource, MemoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_root(tmp_path: Path) -> Path:
    root = tmp_path / "memory"
    root.mkdir()
    return root


@pytest.fixture()
def store(memory_root: Path) -> MemoryStore:
    return MemoryStore(memory_root=memory_root)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source(session_id: str = "s1") -> MemorySource:
    return MemorySource(session_id=session_id, timestamp=time.time())


def _entry(text: str, session_id: str = "s1") -> MemoryEntry:
    return MemoryEntry(text=text, source=_source(session_id))


# ---------------------------------------------------------------------------
# R1.1  Two fixed files only — no extra files created (spec L60)
# ---------------------------------------------------------------------------


def test_no_extra_files_created(store: MemoryStore, memory_root: Path) -> None:
    store.add("memory", _entry("fact 1"))
    store.add("user", _entry("user pref"))
    files = {p.name for p in memory_root.iterdir() if not p.name.endswith(".lock") and not p.name.endswith(".tmp")}
    assert files == {"MEMORY.md", "USER.md"}


# ---------------------------------------------------------------------------
# R1.2  add / read
# ---------------------------------------------------------------------------


def test_add_and_read_memory(store: MemoryStore) -> None:
    store.add("memory", _entry("first entry"))
    entries = store.read("memory")
    assert len(entries) == 1
    assert entries[0].text == "first entry"


def test_add_multiple_memory(store: MemoryStore) -> None:
    store.add("memory", _entry("entry A"))
    store.add("memory", _entry("entry B"))
    entries = store.read("memory")
    assert len(entries) == 2
    texts = [e.text for e in entries]
    assert "entry A" in texts
    assert "entry B" in texts


def test_add_user(store: MemoryStore) -> None:
    store.add("user", _entry("user likes Python"))
    entries = store.read("user")
    assert len(entries) == 1
    assert entries[0].text == "user likes Python"


# ---------------------------------------------------------------------------
# R1.3  Source index stored and retrieved (spec L61)
# ---------------------------------------------------------------------------


def test_source_index_stored(store: MemoryStore) -> None:
    src = MemorySource(session_id="sess-abc", timestamp=1_700_000_000.0)
    entry = MemoryEntry(text="important fact", source=src)
    store.add("memory", entry)
    loaded = store.read("memory")
    assert loaded[0].source.session_id == "sess-abc"
    assert loaded[0].source.timestamp == pytest.approx(1_700_000_000.0, abs=1)


# ---------------------------------------------------------------------------
# R1.4  replace
# ---------------------------------------------------------------------------


def test_replace_existing_entry(store: MemoryStore) -> None:
    store.add("memory", _entry("old value"))
    new_entry = _entry("new value")
    store.replace("memory", old_text="old value", new_entry=new_entry)
    entries = store.read("memory")
    assert len(entries) == 1
    assert entries[0].text == "new value"


def test_replace_missing_raises(store: MemoryStore) -> None:
    with pytest.raises(ValueError, match="not found"):
        store.replace("memory", old_text="does not exist", new_entry=_entry("x"))


# ---------------------------------------------------------------------------
# R1.5  remove
# ---------------------------------------------------------------------------


def test_remove_entry(store: MemoryStore) -> None:
    store.add("memory", _entry("to keep"))
    store.add("memory", _entry("to remove"))
    store.remove("memory", "to remove")
    entries = store.read("memory")
    assert len(entries) == 1
    assert entries[0].text == "to keep"


def test_remove_missing_raises(store: MemoryStore) -> None:
    with pytest.raises(ValueError, match="not found"):
        store.remove("memory", "not there")


# ---------------------------------------------------------------------------
# R1.6  § delimiter — files use § separator, not newlines only
# ---------------------------------------------------------------------------


def test_section_separator_in_file(store: MemoryStore, memory_root: Path) -> None:
    store.add("memory", _entry("alpha"))
    store.add("memory", _entry("beta"))
    content = (memory_root / "MEMORY.md").read_text(encoding="utf-8")
    assert "§" in content


# ---------------------------------------------------------------------------
# R1.7  Persistence — reload from disk
# ---------------------------------------------------------------------------


def test_entries_persist_across_instances(memory_root: Path) -> None:
    s1 = MemoryStore(memory_root=memory_root)
    s1.add("memory", _entry("persisted"))
    s2 = MemoryStore(memory_root=memory_root)
    entries = s2.read("memory")
    assert any(e.text == "persisted" for e in entries)


def test_source_index_persists(memory_root: Path) -> None:
    src = MemorySource(session_id="session-xyz", timestamp=1_600_000_000.0)
    s1 = MemoryStore(memory_root=memory_root)
    s1.add("memory", MemoryEntry(text="reload test", source=src))

    s2 = MemoryStore(memory_root=memory_root)
    entries = s2.read("memory")
    assert entries[0].source.session_id == "session-xyz"


# ---------------------------------------------------------------------------
# R1.8  format_for_prompt — contains header + usage%
# ---------------------------------------------------------------------------


def test_format_for_prompt_includes_header(store: MemoryStore) -> None:
    store.add("memory", _entry("some note"))
    block = store.format_for_prompt("memory")
    assert "MEMORY" in block
    assert "%" in block


def test_format_for_prompt_user_includes_header(store: MemoryStore) -> None:
    store.add("user", _entry("Alice loves Rust"))
    block = store.format_for_prompt("user")
    assert "USER" in block
    assert "%" in block


def test_format_for_prompt_empty(store: MemoryStore) -> None:
    block = store.format_for_prompt("memory")
    # Empty store should still return a prompt block (could be empty content)
    assert isinstance(block, str)


# ---------------------------------------------------------------------------
# R1.9  Char limit enforcement
# ---------------------------------------------------------------------------


def test_char_limit_enforced(memory_root: Path) -> None:
    # Limit is large enough to hold one entry but not two. Each serialized
    # entry is roughly len(text) + ~70 bytes for the source comment line.
    store = MemoryStore(memory_root=memory_root, memory_char_limit=200, user_char_limit=200)
    store.add("memory", _entry("a" * 50))
    with pytest.raises(ValueError, match="char limit"):
        store.add("memory", _entry("b" * 200))


# ---------------------------------------------------------------------------
# R1.10  Atomic write — file is complete even under concurrent writes
# ---------------------------------------------------------------------------


def test_atomic_write_no_partial_file(memory_root: Path) -> None:
    """Concurrent adds should not corrupt the file."""

    async def _do_adds() -> None:
        stores = [MemoryStore(memory_root=memory_root) for _ in range(3)]
        tasks = [asyncio.to_thread(s.add, "memory", _entry(f"entry {i}", f"s{i}")) for i, s in enumerate(stores)]
        await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(_do_adds())
    # File must be parseable — no corruption
    s_final = MemoryStore(memory_root=memory_root)
    entries = s_final.read("memory")
    # At least one succeeded
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# R1.11  invalid target raises
# ---------------------------------------------------------------------------


def test_invalid_target_raises(store: MemoryStore) -> None:
    with pytest.raises((ValueError, KeyError)):
        store.add("unknown_target", _entry("x"))  # type: ignore[arg-type]
