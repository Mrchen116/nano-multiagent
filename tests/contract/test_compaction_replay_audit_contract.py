from pathlib import Path

from agent.core.session.entries import CompactionEntry
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


def test_compaction_replay_audit_contract(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-audit-contract.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)

    first = manager.append_turn_message(
        session.session_id,
        turn_id="turn_1",
        role="user",
        content="legacy question",
        message_id="msg_1",
    )
    second = manager.append_turn_message(
        session.session_id,
        turn_id="turn_1",
        role="assistant",
        content="legacy answer",
        message_id="msg_2",
    )

    entry = manager.append_compaction(
        session.session_id,
        first_kept_event_id="",
        summary="summary: replay anchor",
        data={"reason": "threshold"},
    )

    loaded = store.load_session(session.session_id)
    assert loaded is not None
    compactions = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert len(compactions) == 1
    assert compactions[0].entry_id == entry.entry_id
    assert compactions[0].first_kept_event_id == ""
    assert compactions[0].data["reason"] == "threshold"

    replayed = manager.list_turn_messages(session.session_id)
    # In the full-compact design, old history is replaced by a summary user message.
    # No original messages are kept (kept_events is empty).
    assert len(replayed) == 1
    assert replayed[0].role == "user"
    assert "summary: replay anchor" in replayed[0].content
    assert "Continue the conversation" in replayed[0].content
    assert first.entry_id != second.entry_id
