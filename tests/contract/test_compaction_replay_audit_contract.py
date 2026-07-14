from pathlib import Path

from agent.core.session.entries import CompactionEntry
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.transcript import JsonlTranscript
from agent.core.session.types import NewSession, SessionRef
from agent.core.types import Message


def test_compaction_replay_audit_contract(tmp_path: Path) -> None:
    files = JsonlSessionFiles(data_dir=tmp_path / "sessions")
    writer = JsonlWriter()
    ref = SessionRef(session_id="sess-audit", workspace_root=tmp_path)
    transcript = JsonlTranscript.create(
        ref=ref,
        spec=NewSession(workspace_root=tmp_path),
        files=files,
        writer=writer,
    )
    transcript.append_messages(
        [
            Message(message_id="msg-1", role="user", content="legacy question"),
            Message(message_id="msg-2", role="assistant", content="legacy answer"),
        ],
        durable=True,
    )

    assert transcript.append_compaction(
        summary=Message(
            message_id="msg-summary",
            role="user",
            content="summary: replay anchor",
            metadata={"is_compact_summary": True},
        ),
        reason="threshold",
    )

    compactions = [
        entry
        for entry in transcript.list_event_entries()
        if isinstance(entry, CompactionEntry)
    ]
    assert len(compactions) == 1
    assert compactions[0].data["reason"] == "threshold"

    replayed = transcript.load().messages
    assert len(replayed) == 1
    assert replayed[0].role == "user"
    assert "summary: replay anchor" in replayed[0].content
