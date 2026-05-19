from pathlib import Path

from agent.core.session.entries import CompactionEntry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.service import SessionService


def test_compaction_replay_audit_contract(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)

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

    manager.append_compaction(
        session.session_id,
        first_kept_event_id="",
        summary="summary: replay anchor",
        data={"reason": "threshold"},
    )

    # Flush the async writer before reading back from disk.
    manager.writer.flush()

    all_entries = manager.list_entries(session.session_id)
    compactions = [e for e in all_entries if isinstance(e, CompactionEntry)]
    assert len(compactions) == 1
    # (A) compact_boundary does not persist the caller-supplied entry_id; only content is auditable.
    assert compactions[0].data["reason"] == "threshold"

    replayed = manager.list_turn_messages(session.session_id)
    # In the full-compact design, old history is replaced by a summary user message.
    # No original messages are kept (kept_events is empty).
    assert len(replayed) == 1
    assert replayed[0].role == "user"
    assert "summary: replay anchor" in replayed[0].content
    # (A) stores the summary text verbatim; the resume instruction prefix is added by the
    # compaction layer when constructing the LLM prompt, not at persistence time.
    assert first.entry_id != second.entry_id
