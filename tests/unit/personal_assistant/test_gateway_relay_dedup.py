"""Unit tests for RelayDeduplicationStore persistence and eviction."""

from __future__ import annotations

import sqlite3
import time
from collections import deque
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import RelayDeduplicationStore


def test_relay_dedup_store_contains_after_add(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")

    store.add("idem-1")

    assert store.contains("idem-1") is True


def test_relay_dedup_store_load_from_db_populates_deque(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path)
    store.add("idem-1")

    reloaded = RelayDeduplicationStore(db_path=db_path)
    reloaded.load_from_db()

    assert reloaded.contains("idem-1") is True


def test_relay_dedup_store_expired_keys_not_loaded(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path, ttl_seconds=1)
    store.add("idem-expired")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE relay_deduplication_keys SET expires_at = ?", (time.time() - 10,)
        )
        conn.commit()

    reloaded = RelayDeduplicationStore(db_path=db_path)
    reloaded.load_from_db()

    assert reloaded.contains("idem-expired") is False


def test_relay_dedup_store_purge_removes_expired_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path, ttl_seconds=30)
    store.add("idem-expired")
    store.add("idem-live")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE relay_deduplication_keys SET expires_at = ? WHERE idempotency_key = ?",
            (time.time() - 10, "idem-expired"),
        )
        conn.commit()

    deleted = store.purge_expired()

    assert deleted == 1
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT idempotency_key FROM relay_deduplication_keys ORDER BY idempotency_key"
        ).fetchall()
    assert rows == [("idem-live",)]


def test_relay_dedup_store_deque_rolls_over_at_max(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(
        db_path=tmp_path / "relay-dedup.sqlite3", seen_keys=deque(["old"])
    )
    store._seen_idempotency_keys = deque([str(index) for index in range(1000)])  # noqa: SLF001

    store.add("overflow")

    assert store.contains("0") is False
    assert store.contains("overflow") is True
    assert len(store._seen_idempotency_keys) == 1000  # noqa: SLF001
