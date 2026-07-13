import json
from pathlib import Path

from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.transcript import JsonlTranscript
from agent.core.session.types import ExternalMessage, NewSession, SessionRef
from agent.core.types import Message


def _build_transcript(tmp_path: Path, *, session_id: str = "sess_transcript"):
    files = JsonlSessionFiles(data_dir=tmp_path)
    writer = JsonlWriter()
    ref = SessionRef(session_id=session_id, workspace_root=tmp_path)
    transcript = JsonlTranscript.create(
        ref=ref,
        spec=NewSession(workspace_root=tmp_path),
        files=files,
        writer=writer,
    )
    return transcript, files, writer, ref


def _raw_entries(files: JsonlSessionFiles, ref: SessionRef) -> list[dict]:
    return [dict(entry) for entry in files.read_raw_entries(ref)]


def test_reopened_transcript_first_append_extends_persisted_tail(
    tmp_path: Path,
) -> None:
    transcript, files, writer, ref = _build_transcript(tmp_path)
    first = transcript.append_external(
        ExternalMessage(role="user", content="first", message_id="msg_first")
    )
    assert first.created is True

    reopened = JsonlTranscript(ref=ref, files=files, writer=writer)
    second = reopened.append_external(
        ExternalMessage(role="assistant", content="second", message_id="msg_second")
    )

    assert second.created is True
    turns = [entry for entry in _raw_entries(files, ref) if entry["type"] == "turn"]
    assert [entry["uuid"] for entry in turns] == ["msg_first", "msg_second"]
    assert turns[0]["parent_uuid"] is None
    assert turns[1]["parent_uuid"] == "msg_first"
    assert [message.content for message in reopened.load().messages] == [
        "first",
        "second",
    ]


def test_recovery_control_entry_never_becomes_persisted_tail(tmp_path: Path) -> None:
    transcript, files, _writer, ref = _build_transcript(tmp_path)
    transcript.append_messages(
        [
            Message(
                message_id="msg_tool_call",
                role="assistant",
                content="",
                metadata={
                    "tool_calls": [
                        {"call_id": "call_1", "name": "read", "arguments": {}}
                    ]
                },
            )
        ],
        durable=True,
    )
    transcript.append_tool_call_recovery(
        tool_call_id="call_1",
        tool_name="read",
        reason="interrupted",
        durable=True,
    )
    transcript.append_external(
        ExternalMessage(role="user", content="continue", message_id="msg_continue")
    )

    raw = _raw_entries(files, ref)
    recovery = next(entry for entry in raw if entry["type"] == "tool_call_recovery")
    final_turn = next(entry for entry in raw if entry.get("uuid") == "msg_continue")
    assert "uuid" not in recovery
    assert final_turn["parent_uuid"] == "msg_tool_call"


def test_external_append_is_durable_and_idempotent(tmp_path: Path) -> None:
    transcript, files, _writer, ref = _build_transcript(tmp_path)
    request = ExternalMessage(
        role="user",
        content="scheduled awareness",
        message_id="msg_awareness",
        idempotency_key="awareness:1",
    )

    created = transcript.append_external(request)
    duplicate = transcript.append_external(request)

    assert created.created is True
    assert duplicate.created is False
    raw = _raw_entries(files, ref)
    matches = [entry for entry in raw if entry.get("uuid") == "msg_awareness"]
    assert len(matches) == 1
    with files.resolve_path(ref).open("r", encoding="utf-8") as handle:
        persisted = [json.loads(line) for line in handle if line.strip()]
    assert any(entry.get("uuid") == "msg_awareness" for entry in persisted)


def test_repair_is_idempotent_and_materializes_one_synthetic_result(
    tmp_path: Path,
) -> None:
    transcript, files, _writer, ref = _build_transcript(tmp_path)
    transcript.append_messages(
        [
            Message(
                message_id="msg_orphan",
                role="assistant",
                content="",
                metadata={
                    "tool_calls": [
                        {"call_id": "call_orphan", "name": "bash", "arguments": {}}
                    ]
                },
            )
        ],
        durable=True,
    )

    transcript.prepare_for_run(reason="orphaned")
    transcript.prepare_for_run(reason="orphaned")

    raw = _raw_entries(files, ref)
    recoveries = [entry for entry in raw if entry["type"] == "tool_call_recovery"]
    assert len(recoveries) == 1
    recovered = [
        message
        for message in transcript.load().messages
        if message.role == "tool" and message.tool_call_id == "call_orphan"
    ]
    assert len(recovered) == 1


def test_compaction_commit_rejects_a_stale_external_epoch(tmp_path: Path) -> None:
    transcript, files, _writer, ref = _build_transcript(tmp_path)
    captured_epoch = transcript.external_epoch
    transcript.append_external(
        ExternalMessage(role="user", content="raced", message_id="msg_raced")
    )

    committed = transcript.append_compaction(
        summary=Message(message_id="msg_summary", role="user", content="summary"),
        reason="manual",
        expected_external_epoch=captured_epoch,
    )

    assert committed is False
    assert not any(
        entry["type"] == "compact_boundary" for entry in _raw_entries(files, ref)
    )
