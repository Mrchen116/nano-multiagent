from pathlib import Path

from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService


def test_session_service_can_rebuild_session_after_store_reopen(tmp_path: Path) -> None:
    data_dir = tmp_path / "sessions"
    first_service = SessionService(store=JsonlSessionStore(data_dir=data_dir))

    created = first_service.create_session(workspace_root=tmp_path)
    first_service.manager.store.writer.flush()

    second_store = JsonlSessionStore(data_dir=data_dir)
    second_service = SessionService(store=second_store)
    loaded = second_service.get_session(created.session_id)

    assert loaded is not None
    assert loaded.session_id == created.session_id
    assert loaded.created_at == created.created_at
    assert loaded.status == "active"

    entries = second_service.manager.list_entries(created.session_id)
    assert len(entries) >= 1
    assert entries[0].kind is SessionEntryKind.SESSION_CREATED
