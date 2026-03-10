from nano_multiagent.core.session.entries import SessionEntryKind, new_session_created_entry
from nano_multiagent.core.session.manager import SessionManager
from nano_multiagent.core.session.store import LoadedSession, SessionStore


class RecordingSessionStore(SessionStore):
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.loaded: dict[str, LoadedSession] = {}

    def append_event(self, session_id: str, entry: object) -> None:
        self.events.append((session_id, entry))

    def load_session(self, session_id: str) -> LoadedSession | None:
        return self.loaded.get(session_id)

    def save_snapshot(self, session_id: str, snapshot: dict[str, object]) -> None:
        return None


def test_create_session_appends_session_created_event() -> None:
    store = RecordingSessionStore()
    manager = SessionManager(store=store)

    session = manager.create_session()

    assert session.session_id.startswith("sess_")
    assert session.status == "active"
    assert len(store.events) == 1
    written_session_id, entry = store.events[0]
    assert written_session_id == session.session_id
    assert entry.kind is SessionEntryKind.SESSION_CREATED
    assert entry.data["status"] == "active"


def test_get_session_rebuilds_state_from_events() -> None:
    store = RecordingSessionStore()
    entry = new_session_created_entry(
        session_id="sess_rebuild",
        entry_id="evt_rebuild",
        created_at="2026-02-27T02:20:00+00:00",
    )
    store.loaded["sess_rebuild"] = LoadedSession(
        session_id="sess_rebuild",
        events=(entry,),
        snapshot=None,
    )
    manager = SessionManager(store=store)

    session = manager.get_session("sess_rebuild")

    assert session is not None
    assert session.session_id == "sess_rebuild"
    assert session.created_at == "2026-02-27T02:20:00+00:00"
    assert session.status == "active"
