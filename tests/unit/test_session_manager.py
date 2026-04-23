import tempfile
from pathlib import Path

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


def test_create_session_appends_session_created_event() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonlSessionStore(data_dir=Path(tmpdir))
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=Path.cwd())

        assert session.session_id.startswith("sess_")
        assert session.status == "active"

        # Verify JSONL file was created and contains session_created
        result = manager.load(session.session_id)
        assert result.config.session_id == session.session_id
        assert result.config.workspace_root == Path.cwd()


def test_get_session_rebuilds_state_from_jsonl() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonlSessionStore(data_dir=Path(tmpdir))
        manager = SessionManager(store=store)

        created = manager.create_session(
            workspace_root=Path("/tmp/workspace"),
            system_prompt="You are a helpful assistant.",
            skills=("bash_runner",),
            tool_allowlist=("read", "write"),
            metadata={"conversation_type": "pair"},
        )

        session = manager.get_session(created.session_id)

        assert session is not None
        assert session.session_id == created.session_id
        assert session.status == "active"
        assert session.workspace_root == Path("/tmp/workspace")
        assert session.system_prompt == "You are a helpful assistant."
        assert session.skills == ("bash_runner",)
        assert session.tool_allowlist == ("read", "write")
        assert session.metadata == {"conversation_type": "pair"}


def test_list_turn_messages_returns_messages_from_jsonl() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonlSessionStore(data_dir=Path(tmpdir))
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=Path.cwd())
        manager.append_turn_message(
            session.session_id,
            turn_id="turn_1",
            role="user",
            content="hello",
            message_id="msg_1",
        )
        manager.append_turn_message(
            session.session_id,
            turn_id="turn_1",
            role="assistant",
            content="hi there",
            message_id="msg_2",
        )
        manager.writer.flush()

        messages = manager.list_turn_messages(session.session_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "hello"
        assert messages[1].role == "assistant"
        assert messages[1].content == "hi there"


def test_append_compaction_writes_compact_boundary_and_summary() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonlSessionStore(data_dir=Path(tmpdir))
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=Path.cwd())
        manager.append_turn_message(
            session.session_id,
            turn_id="turn_1",
            role="user",
            content="hello",
            message_id="msg_1",
        )

        manager.append_compaction(
            session.session_id,
            first_kept_event_id="msg_1",
            summary="Summary of previous conversation.",
        )
        manager.writer.flush()

        # After compaction, list_turn_messages should skip pre-boundary messages
        messages = manager.list_turn_messages(session.session_id)
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Summary of previous conversation."
        assert messages[0].metadata.get("is_compact_summary") is True


def test_list_sessions_returns_sessions_ordered_by_mtime() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonlSessionStore(data_dir=Path(tmpdir))
        manager = SessionManager(store=store)

        session1 = manager.create_session(workspace_root=Path.cwd())
        session2 = manager.create_session(workspace_root=Path.cwd())

        sessions, has_more = manager.list_sessions(limit=10, offset=0)
        assert len(sessions) == 2
        assert not has_more
        # Most recently created first
        assert sessions[0].session_id == session2.session_id
        assert sessions[1].session_id == session1.session_id


def test_append_run_status_is_no_op() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonlSessionStore(data_dir=Path(tmpdir))
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=Path.cwd())
        entry = manager.append_run_status(
            session.session_id,
            run_id="run_1",
            status="running",
        )
        # Should return a dummy entry without writing to JSONL
        assert entry.data["run_id"] == "run_1"
        assert entry.data["status"] == "running"
        # JSONL should still only have session_created
        result = manager.load(session.session_id)
        assert len(result.messages) == 0
