"""Unit tests for SessionFileState."""

import os
from pathlib import Path

import pytest

from agent.core.tools.session_file_state import FileReadState, SessionFileState


class TestCheckUnchanged:
    def test_returns_true_when_exact_range_unchanged(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\nworld\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=2)

        assert state.check_unchanged(str(file), 1, 2) is True

    def test_returns_false_when_range_differs(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\nworld\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=2)

        assert state.check_unchanged(str(file), 3, 2) is False

    def test_returns_false_when_file_modified(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(
            str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=None
        )

        file.write_text("changed\n", encoding="utf-8")
        assert state.check_unchanged(str(file), 1, None) is False

    def test_returns_false_when_no_record(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()

        assert state.check_unchanged(str(file), 1, None) is False


class TestCanWrite:
    def test_allows_when_read_and_unchanged(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(
            str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=None
        )

        ok, code = state.can_write(str(file))
        assert ok is True
        assert code is None

    def test_rejects_when_never_read(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()

        ok, code = state.can_write(str(file))
        assert ok is False
        assert code == 6

    def test_rejects_when_stale(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(
            str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=None
        )

        file.write_text("changed\n", encoding="utf-8")
        ok, code = state.can_write(str(file))
        assert ok is False
        assert code == 7


class TestRecordWrite:
    def test_updates_fingerprint_after_write(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=2)

        file.write_text("changed\n", encoding="utf-8")
        new_stat = file.stat()
        state.record_write(str(file), new_stat.st_mtime_ns, new_stat.st_size)

        # After record_write the state should reflect the new content.
        ok, code = state.can_write(str(file))
        assert ok is True
        assert code is None

    def test_sets_offset_limit_to_none(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(str(file), stat.st_mtime_ns, stat.st_size, offset=3, limit=5)
        state.record_write(str(file), stat.st_mtime_ns, stat.st_size)

        recorded = state._states[str(file.resolve())]
        assert recorded.offset is None
        assert recorded.limit is None


class TestRecordRead:
    def test_overwrites_last_range(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=2)
        state.record_read(str(file), stat.st_mtime_ns, stat.st_size, offset=3, limit=4)

        assert state.check_unchanged(str(file), 3, 4) is True
        assert state.check_unchanged(str(file), 1, 2) is False


class TestLRU:
    def test_evicts_oldest_when_over_capacity(self, tmp_path: Path) -> None:
        state = SessionFileState(capacity=2)
        for i in range(3):
            file = tmp_path / f"f{i}.txt"
            file.write_text("x", encoding="utf-8")
            stat = file.stat()
            state.record_read(
                str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=None
            )

        first = str((tmp_path / "f0.txt").resolve())
        assert first not in state._states
        assert len(state._states) == 2


class TestRemove:
    def test_drops_record(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("hello\n", encoding="utf-8")
        state = SessionFileState()
        stat = file.stat()
        state.record_read(
            str(file), stat.st_mtime_ns, stat.st_size, offset=1, limit=None
        )

        state.remove(str(file))
        assert state.can_write(str(file)) == (False, 6)
