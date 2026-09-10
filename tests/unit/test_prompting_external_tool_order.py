"""External notifications must not split tool exchanges in replayed model input."""

from pathlib import Path

import pytest

from agent.core.agent.prompting import build_chat_messages
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.transcript import JsonlTranscript
from agent.core.session.types import ExternalMessage, NewSession, SessionRef
from agent.core.types import Message


@pytest.mark.parametrize("count", [1, 2])
def test_notification_during_tools_survives_reload_without_splitting_results(
    tmp_path: Path, count: int
) -> None:
    files = JsonlSessionFiles(data_dir=tmp_path)
    writer = JsonlWriter()
    ref = SessionRef(session_id="sess_overlap", workspace_root=tmp_path)
    transcript = JsonlTranscript.create(
        ref=ref, spec=NewSession(workspace_root=tmp_path), files=files, writer=writer
    )
    try:
        for i in range(count):
            transcript.append_messages(
                [
                    Message(
                        message_id=f"call-row-{i}",
                        role="assistant",
                        content="",
                        group_id="response",
                        metadata={
                            "tool_calls": [
                                {
                                    "call_id": f"call-{i}",
                                    "name": "bash",
                                    "arguments": {},
                                }
                            ]
                        },
                    )
                ]
            )
            transcript.append_external(
                ExternalMessage(role="user", content=f"Cron result {i}")
            )
        for i in reversed(range(count)):
            transcript.append_messages(
                [
                    Message(
                        message_id=f"result-{i}",
                        role="tool",
                        content=f"result {i}",
                        tool_call_id=f"call-{i}",
                        group_id="response",
                    )
                ],
                durable=True,
            )
        loaded = JsonlTranscript(ref=ref, files=files, writer=writer).load().messages
        # Persistence retains the actual arrival order for audit.
        assert loaded[1].content == "Cron result 0"
        messages = build_chat_messages(
            history_messages=tuple(loaded), user_text="follow-up"
        )
        assert [m.role for m in messages] == ["assistant"] + ["tool"] * count + [
            "user"
        ] * (count + 1)
        assert {m.tool_call_id for m in messages[1 : 1 + count]} == {
            f"call-{i}" for i in range(count)
        }
        assert [m.content for m in messages[1 + count :]] == [
            f"Cron result {i}" for i in range(count)
        ] + ["follow-up"]
    finally:
        writer.close()
