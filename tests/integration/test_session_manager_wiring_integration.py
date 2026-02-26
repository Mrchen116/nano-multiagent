from pathlib import Path

from nano_multiagent.session.entries import SessionEntryKind
from nano_multiagent.session.service import SessionService
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


def test_session_service_can_rebuild_session_after_store_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "session-runtime.sqlite3"
    first_service = SessionService(store=SQLiteSessionStore(db_path=db_path))

    created = first_service.create_session()

    second_store = SQLiteSessionStore(db_path=db_path)
    second_service = SessionService(store=second_store)
    loaded = second_service.get_session(created.session_id)
    loaded_record = second_store.load_session(created.session_id)

    assert loaded is not None
    assert loaded.session_id == created.session_id
    assert loaded.created_at == created.created_at
    assert loaded.status == "active"
    assert loaded_record is not None
    assert len(loaded_record.events) == 1
    assert loaded_record.events[0].kind is SessionEntryKind.SESSION_CREATED
