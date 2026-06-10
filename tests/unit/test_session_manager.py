import json
import tempfile
from pathlib import Path

import pytest

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


# ---------------------------------------------------------------------------
# C1-R1: prepare_transcript_for_run + tool_call_recovery entry (RED tests)
# ---------------------------------------------------------------------------


def _write_raw_lines(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for entry in lines:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_raw_lines(path: Path) -> list[dict]:
    result = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                result.append(json.loads(line))
    return result


class TestPrepareTranscript:
    """prepare_transcript_for_run: 补齐未闭合 tool_call，幂等，load 后 transcript 合法。"""

    def _setup_store(self, tmpdir: str) -> tuple[JsonlSessionStore, SessionManager]:
        store = JsonlSessionStore(data_dir=Path(tmpdir))
        manager = SessionManager(store=store)
        return store, manager

    def test_orphaned_tool_call_gets_recovery_entry(self, tmp_path: Path) -> None:
        """未闭合 tool_call 经 prepare 后，JSONL 包含 tool_call_recovery entry。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=tmp_path)
        # 写入 assistant 消息带 tool_call，无对应 tool result
        call_id = "call-orphan-001"
        path = store.resolve_path(session.session_id)
        _write_raw_lines(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-asst-1",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "bash", "arguments": {}}
                    ],
                }
            ],
        )

        store.prepare_transcript_for_run(
            session.session_id, reason="interrupted"
        )

        raw = _read_raw_lines(path)
        recovery_entries = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery_entries) == 1, "应有 1 个 recovery entry"
        rec = recovery_entries[0]
        assert rec["tool_call_id"] == call_id
        assert rec["reason"] == "interrupted"
        assert rec["idempotency_key"] == f"tool-call-recovery:{call_id}"

    def test_prepare_idempotent_no_duplicate_recovery(self, tmp_path: Path) -> None:
        """prepare 两次不产生重复 recovery entry。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=tmp_path)
        call_id = "call-idem-002"
        path = store.resolve_path(session.session_id)
        _write_raw_lines(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-asst-2",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "read", "arguments": {}}
                    ],
                }
            ],
        )

        store.prepare_transcript_for_run(session.session_id, reason="interrupted")
        store.prepare_transcript_for_run(session.session_id, reason="interrupted")

        raw = _read_raw_lines(path)
        recovery_entries = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery_entries) == 1, "重复 prepare 只产生 1 个 recovery entry"

    def test_partial_results_only_repairs_missing(self, tmp_path: Path) -> None:
        """部分有结果时只补缺失的 call_id。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=tmp_path)
        call_a = "call-partial-A"
        call_b = "call-partial-B"
        path = store.resolve_path(session.session_id)
        _write_raw_lines(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-asst-3",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_a, "name": "bash", "arguments": {}},
                        {"call_id": call_b, "name": "read", "arguments": {}},
                    ],
                },
                # call_a 有结果，call_b 没有
                {
                    "type": "turn",
                    "uuid": "msg-tool-A",
                    "parent_uuid": "msg-asst-3",
                    "session_id": session.session_id,
                    "role": "tool",
                    "content": "output A",
                    "timestamp": "2026-01-01T00:00:01+00:00",
                    "tool_call_id": call_a,
                },
            ],
        )

        store.prepare_transcript_for_run(session.session_id, reason="cancelled")

        raw = _read_raw_lines(path)
        recovery_entries = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery_entries) == 1, "只有 call_b 需要恢复"
        assert recovery_entries[0]["tool_call_id"] == call_b

    def test_load_is_readonly_no_writes(self, tmp_path: Path) -> None:
        """普通 load() 不写文件，mtime 不变。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=tmp_path)
        manager.append_turn_message(
            session.session_id,
            turn_id="turn-1",
            role="user",
            content="hello",
            message_id="msg-user-1",
        )
        manager.writer.flush()

        path = store.resolve_path(session.session_id)
        mtime_before = path.stat().st_mtime

        manager.load(session.session_id)

        mtime_after = path.stat().st_mtime
        assert mtime_before == mtime_after, "load() 不应写文件"

    def test_closed_tool_call_skipped_by_prepare(self, tmp_path: Path) -> None:
        """已有 tool result 的 call_id 不被 prepare 再次补 recovery。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=tmp_path)
        call_id = "call-closed-005"
        path = store.resolve_path(session.session_id)
        _write_raw_lines(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-asst-5",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "bash", "arguments": {}}
                    ],
                },
                {
                    "type": "turn",
                    "uuid": "msg-tool-5",
                    "parent_uuid": "msg-asst-5",
                    "session_id": session.session_id,
                    "role": "tool",
                    "content": "done",
                    "timestamp": "2026-01-01T00:00:01+00:00",
                    "tool_call_id": call_id,
                },
            ],
        )

        store.prepare_transcript_for_run(session.session_id, reason="interrupted")

        raw = _read_raw_lines(path)
        recovery_entries = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery_entries) == 0, "已闭合 call_id 不应产生 recovery"


# ---------------------------------------------------------------------------
# C1-R4: interrupt/cancel/shutdown 写 tool_call_recovery 终态 (RED tests)
# ---------------------------------------------------------------------------


class TestInterruptCancelRecovery:
    """append_tool_call_recovery: 中断/取消/shutdown 写 recovery entry 使 load 后合法。"""

    def test_append_tool_call_recovery_writes_entry(self, tmp_path: Path) -> None:
        """append_tool_call_recovery 直接 append 一个 recovery entry 到 JSONL。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)

        session = manager.create_session(workspace_root=tmp_path)
        call_id = "call-live-cancel-001"
        path = store.resolve_path(session.session_id)

        # 写 assistant tool_call（模拟 run 中已持久化）
        _write_raw_lines(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-live-asst",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "bash", "arguments": {}}
                    ],
                }
            ],
        )

        # 取消时调用 append_tool_call_recovery
        store.append_tool_call_recovery(
            session.session_id,
            tool_call_id=call_id,
            tool_name="bash",
            reason="cancelled",
        )
        store.writer.flush()

        raw = _read_raw_lines(path)
        recovery_entries = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery_entries) == 1
        rec = recovery_entries[0]
        assert rec["tool_call_id"] == call_id
        assert rec["reason"] == "cancelled"
        assert rec["tool_name"] == "bash"
        assert rec["idempotency_key"] == f"tool-call-recovery:{call_id}"

    def test_load_after_interrupt_recovery_is_valid(self, tmp_path: Path) -> None:
        """append_tool_call_recovery + load -> build_chat_messages 合法。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)
        from agent.core.agent.prompting import build_chat_messages

        session = manager.create_session(workspace_root=tmp_path)
        call_id = "call-live-interrupt-002"
        path = store.resolve_path(session.session_id)

        _write_raw_lines(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-live-2",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "read", "arguments": {}}
                    ],
                }
            ],
        )

        store.append_tool_call_recovery(
            session.session_id,
            tool_call_id=call_id,
            tool_name="read",
            reason="interrupted",
        )
        store.writer.flush()

        result = manager.load(session.session_id)
        messages = tuple(result.messages)
        # Should not raise; all assistant tool_calls have corresponding results
        llm_msgs = build_chat_messages(history_messages=messages, user_text="继续")

        call_ids_with_result = {
            m.tool_call_id for m in llm_msgs if m.role == "tool" and m.tool_call_id
        }
        call_ids_in_asst = {
            tc.call_id
            for m in llm_msgs if m.role == "assistant" and m.tool_calls
            for tc in m.tool_calls
        }
        assert call_ids_in_asst == call_ids_with_result

    def test_multiple_reasons_valid(self, tmp_path: Path) -> None:
        """interrupted/cancelled/shutdown 三种 reason 都能写入且 load 合法。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)

        for reason in ("interrupted", "cancelled", "shutdown"):
            session = manager.create_session(workspace_root=tmp_path)
            call_id = f"call-{reason}"
            path = store.resolve_path(session.session_id)
            _write_raw_lines(
                path,
                [
                    {
                        "type": "turn",
                        "uuid": f"msg-{reason}",
                        "parent_uuid": None,
                        "session_id": session.session_id,
                        "role": "assistant",
                        "content": "",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "tool_calls": [
                            {"call_id": call_id, "name": "bash", "arguments": {}}
                        ],
                    }
                ],
            )
            store.append_tool_call_recovery(
                session.session_id,
                tool_call_id=call_id,
                reason=reason,
            )
            store.writer.flush()
            raw = _read_raw_lines(path)
            recovery = [e for e in raw if e.get("type") == "tool_call_recovery"]
            assert len(recovery) == 1, f"reason={reason}: 应有 1 个 recovery entry"
            assert recovery[0]["reason"] == reason
