from pathlib import Path

from agent.core.session.entries import SessionEntry, SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


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


def test_jsonl_store_persists_session_across_reopen(tmp_path: Path) -> None:
    data_dir = tmp_path / "session-jsonl"
    service = SessionService(store=JsonlSessionStore(data_dir=data_dir))
    created = service.create_session(workspace_root=tmp_path)
    service.manager.store.writer.flush()

    reloaded_service = SessionService(store=JsonlSessionStore(data_dir=data_dir))
    loaded = reloaded_service.get_session(created.session_id)

    assert loaded is not None
    assert loaded.session_id == created.session_id
    assert loaded.created_at == created.created_at
    assert loaded.status == "active"

    entries = reloaded_service.manager.list_entries(created.session_id)
    assert len(entries) >= 1
    assert entries[0].kind is SessionEntryKind.SESSION_CREATED
