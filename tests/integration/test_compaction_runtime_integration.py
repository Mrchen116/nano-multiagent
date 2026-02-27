from pathlib import Path

from nano_multiagent.session.entries import CompactionEntry
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


def test_compaction_entry_is_persisted_with_audit_anchor_and_replayable(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-baseline.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()

    first = manager.append_turn_message(
        session.session_id,
        turn_id="turn_1",
        role="user",
        content="old-question",
        message_id="msg_1",
    )
    second = manager.append_turn_message(
        session.session_id,
        turn_id="turn_1",
        role="assistant",
        content="old-answer",
        message_id="msg_2",
    )
    third = manager.append_turn_message(
        session.session_id,
        turn_id="turn_2",
        role="user",
        content="new-question",
        message_id="msg_3",
    )
    manager.append_compaction(
        session.session_id,
        first_kept_event_id=second.entry_id,
        summary="summary: old context compacted",
        data={"reason": "manual"},
    )

    loaded = store.load_session(session.session_id)
    assert loaded is not None
    compaction_entries = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert len(compaction_entries) == 1
    compaction = compaction_entries[0]
    assert compaction.first_kept_event_id == second.entry_id
    assert compaction.summary == "summary: old context compacted"
    assert compaction.data["reason"] == "manual"

    replayed = manager.list_turn_messages(session.session_id)
    assert [message.role for message in replayed] == ["system", "assistant", "user"]
    assert replayed[0].content == "summary: old context compacted"
    assert [message.content for message in replayed[1:]] == ["old-answer", "new-question"]
    assert first.entry_id != third.entry_id
