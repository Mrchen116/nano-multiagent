from pathlib import Path

from agent.core.session.conversation import ConversationSession
from agent.core.session.directory import SessionDirectory
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.types import NewSession, SessionRef


class _UnusedEngine:
    async def execute_turn(self, state, request):  # noqa: ANN001, ANN201
        raise AssertionError("turn execution is not part of this persistence test")

    async def compact(self, state):  # noqa: ANN001, ANN201
        raise AssertionError("compaction is not part of this persistence test")


def _directory(data_dir: Path) -> SessionDirectory:
    files = JsonlSessionFiles(data_dir=data_dir)
    writer = JsonlWriter()
    return SessionDirectory(
        files=files,
        writer=writer,
        conversation_factory=lambda ref, transcript: ConversationSession(
            ref=ref, transcript=transcript, engine=_UnusedEngine()
        ),
    )


def test_directory_can_rebuild_session_after_files_reopen(tmp_path: Path) -> None:
    data_dir = tmp_path / "sessions"
    first = _directory(data_dir)
    created = first.create(NewSession(workspace_root=tmp_path))

    second = _directory(data_dir)
    loaded = second.get(
        SessionRef(session_id=created.ref.session_id, workspace_root=tmp_path)
    )

    assert loaded is not None
    assert loaded.session_id == created.ref.session_id
    assert loaded.status == "active"
