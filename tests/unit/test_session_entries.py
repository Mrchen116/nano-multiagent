from agent.core.session.entries import (
    SessionEntryKind,
    new_compaction_entry,
    new_session_created_entry,
)


def test_new_session_created_entry_has_expected_defaults() -> None:
    entry = new_session_created_entry(
        session_id="sess_demo",
        created_at="2026-02-27T01:00:00+00:00",
    )

    assert entry.session_id == "sess_demo"
    assert entry.kind is SessionEntryKind.SESSION_CREATED
    assert entry.data["status"] == "active"
    assert entry.created_at == "2026-02-27T01:00:00+00:00"
    assert entry.entry_id.startswith("evt_")


def test_new_compaction_entry_preserves_audit_anchor() -> None:
    entry = new_compaction_entry(
        session_id="sess_demo",
        created_at="2026-02-27T01:10:00+00:00",
        first_kept_event_id="evt_0009",
        summary="conversation compacted",
    )

    assert entry.session_id == "sess_demo"
    assert entry.kind is SessionEntryKind.COMPACTION
    assert entry.first_kept_event_id == "evt_0009"
    assert entry.summary == "conversation compacted"
    assert entry.entry_id.startswith("evt_")
