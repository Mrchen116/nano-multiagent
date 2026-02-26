from pathlib import Path

from nano_multiagent.session.entries import SessionEntry, SessionEntryKind
from nano_multiagent.session.stores.jsonl_store import JsonlSessionStore
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


def test_sqlite_store_persists_events_and_snapshot_across_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    event = SessionEntry(
        entry_id="evt_sqlite_1",
        session_id="sess_sqlite",
        created_at="2026-02-27T01:30:00+00:00",
        kind=SessionEntryKind.SESSION_CREATED,
        data={"status": "active"},
    )

    store.append_event("sess_sqlite", event)
    store.save_snapshot(
        "sess_sqlite",
        {"session_id": "sess_sqlite", "status": "active", "created_at": event.created_at},
    )

    reloaded_store = SQLiteSessionStore(db_path=db_path)
    loaded = reloaded_store.load_session("sess_sqlite")

    assert loaded is not None
    assert loaded.snapshot == {
        "session_id": "sess_sqlite",
        "status": "active",
        "created_at": "2026-02-27T01:30:00+00:00",
    }
    assert [entry.entry_id for entry in loaded.events] == ["evt_sqlite_1"]


def test_jsonl_store_persists_events_and_snapshot_across_reopen(tmp_path: Path) -> None:
    base_dir = tmp_path / "session-jsonl"
    store = JsonlSessionStore(base_dir=base_dir)
    event = SessionEntry(
        entry_id="evt_jsonl_1",
        session_id="sess_jsonl",
        created_at="2026-02-27T01:35:00+00:00",
        kind=SessionEntryKind.SESSION_CREATED,
        data={"status": "active"},
    )

    store.append_event("sess_jsonl", event)
    store.save_snapshot(
        "sess_jsonl",
        {"session_id": "sess_jsonl", "status": "active", "created_at": event.created_at},
    )

    reloaded_store = JsonlSessionStore(base_dir=base_dir)
    loaded = reloaded_store.load_session("sess_jsonl")

    assert loaded is not None
    assert loaded.snapshot == {
        "session_id": "sess_jsonl",
        "status": "active",
        "created_at": "2026-02-27T01:35:00+00:00",
    }
    assert [entry.entry_id for entry in loaded.events] == ["evt_jsonl_1"]
