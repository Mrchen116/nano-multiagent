from agent.core.session.entries import CompactionEntry, SessionEntry, SessionEntryKind
from agent.platform.persistence.session.serializers import (
    ENTRY_SERIALIZATION_VERSION,
    deserialize_entry,
    serialize_entry,
)


def test_session_entry_serializer_contract() -> None:
    entry = SessionEntry(
        entry_id="evt_fixed",
        session_id="sess_fixed",
        created_at="2026-02-27T01:20:00+00:00",
        kind=SessionEntryKind.SESSION_CREATED,
        data={"status": "active"},
    )

    payload = serialize_entry(entry)

    assert payload == {
        "version": ENTRY_SERIALIZATION_VERSION,
        "entry_id": "evt_fixed",
        "session_id": "sess_fixed",
        "created_at": "2026-02-27T01:20:00+00:00",
        "kind": "session.created",
        "data": {"status": "active"},
    }

    restored = deserialize_entry(payload)
    assert isinstance(restored, SessionEntry)
    assert restored == entry


def test_compaction_entry_serializer_contract() -> None:
    entry = CompactionEntry(
        entry_id="evt_comp",
        session_id="sess_fixed",
        created_at="2026-02-27T01:25:00+00:00",
        first_kept_event_id="evt_anchor",
        summary="summary text",
        data={"reason": "threshold"},
    )

    payload = serialize_entry(entry)

    assert payload == {
        "version": ENTRY_SERIALIZATION_VERSION,
        "entry_id": "evt_comp",
        "session_id": "sess_fixed",
        "created_at": "2026-02-27T01:25:00+00:00",
        "kind": "session.compaction",
        "first_kept_event_id": "evt_anchor",
        "summary": "summary text",
        "data": {"reason": "threshold"},
    }

    restored = deserialize_entry(payload)
    assert isinstance(restored, CompactionEntry)
    assert restored == entry
