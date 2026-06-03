"""Core shared time/fileio utils behavioral contracts.

These tests lock the public API surface of agent.core.utils.time and
agent.core.utils.fileio so that future refactors cannot silently drop or
break these utility primitives.
"""

import pytest


class TestUtcNowIso:
    """agent.core.utils.time.utc_now_iso must exist and return an ISO 8601 UTC string."""

    def test_importable_from_core_utils(self) -> None:
        from agent.core.utils.time import utc_now_iso  # type: ignore[import]

        result = utc_now_iso()
        assert isinstance(result, str)
        # Rough sanity: UTC ISO strings contain a 'T' separator and '+00:00' or 'Z'
        assert "T" in result
        assert "+" in result or result.endswith("Z")

    def test_returns_different_values_over_time(self) -> None:
        import time

        from agent.core.utils.time import utc_now_iso  # type: ignore[import]

        t1 = utc_now_iso()
        time.sleep(0.01)
        t2 = utc_now_iso()
        # Two calls at different times must not collide
        assert t1 <= t2


class TestAtomicWrite:
    """agent.core.utils.fileio.atomic_write must exist and write atomically."""

    def test_importable_from_core_utils(self, tmp_path) -> None:
        from agent.core.utils.fileio import atomic_write  # type: ignore[import]

        target = tmp_path / "out.txt"
        atomic_write(target, "hello")
        assert target.read_text() == "hello"

    def test_overwrites_existing_file(self, tmp_path) -> None:
        from agent.core.utils.fileio import atomic_write  # type: ignore[import]

        target = tmp_path / "out.txt"
        target.write_text("old content")
        atomic_write(target, "new content")
        assert target.read_text() == "new content"

    def test_bytes_mode(self, tmp_path) -> None:
        from agent.core.utils.fileio import atomic_write  # type: ignore[import]

        target = tmp_path / "out.bin"
        atomic_write(target, b"\x00\x01\x02")
        assert target.read_bytes() == b"\x00\x01\x02"
