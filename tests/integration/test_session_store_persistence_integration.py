import json
from pathlib import Path

from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService
from agent.core.agent.prompting import build_chat_messages


def test_jsonl_store_persists_session_across_reopen(tmp_path: Path) -> None:
    data_dir = tmp_path / "session-jsonl"
    service = SessionService(store=JsonlSessionStore(data_dir=data_dir))
    created = service.create_session(workspace_root=tmp_path)
    service.manager.store.writer.flush()

    reloaded_service = SessionService(store=JsonlSessionStore(data_dir=data_dir))
    loaded = reloaded_service.get_session(created.session_id)

    assert loaded is not None
    assert loaded.session_id == created.session_id
    assert loaded.created_at == created.created_at
    assert loaded.status == "active"

    entries = reloaded_service.manager.list_entries(created.session_id)
    assert len(entries) >= 1
    assert entries[0].kind is SessionEntryKind.SESSION_CREATED


def test_prepare_transcript_idempotent_across_process_restart(tmp_path: Path) -> None:
    """两次 prepare（模拟两次进程重启）后 load 结果只含一套 recovery entry，transcript 合法。"""
    data_dir = tmp_path / "sessions"
    store = JsonlSessionStore(data_dir=data_dir)
    from agent.core.session.manager import SessionManager

    manager = SessionManager(store=store)

    session = manager.create_session(workspace_root=tmp_path)
    sid = session.session_id
    call_id = "call-cross-restart"

    # 模拟 run 中已持久化的 assistant tool_call
    path = store.resolve_path(sid)
    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "type": "turn",
                    "uuid": "msg-restart-asst",
                    "parent_uuid": None,
                    "session_id": sid,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "bash", "arguments": {}}
                    ],
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    # 第一次 prepare（模拟第一次进程重启）
    store1 = JsonlSessionStore(data_dir=data_dir)
    store1.prepare_transcript_for_run(sid, reason="orphaned")

    # 第二次 prepare（模拟第二次进程重启，幂等）
    store2 = JsonlSessionStore(data_dir=data_dir)
    store2.prepare_transcript_for_run(sid, reason="orphaned")

    # load 后 transcript 合法，只有一套 recovery
    store3 = JsonlSessionStore(data_dir=data_dir)
    result = store3.load(sid)
    messages = tuple(result.messages)

    # build_chat_messages 不抛错
    llm_msgs = build_chat_messages(history_messages=messages, user_text="再来一次")

    call_ids_with_result = {
        m.tool_call_id for m in llm_msgs if m.role == "tool" and m.tool_call_id
    }
    call_ids_in_asst = {
        tc.call_id
        for m in llm_msgs
        if m.role == "assistant" and m.tool_calls
        for tc in m.tool_calls
    }
    assert call_ids_in_asst == call_ids_with_result, (
        f"orphaned after double prepare: {call_ids_in_asst - call_ids_with_result}"
    )

    # 验证只有 1 个 recovery entry in raw JSONL
    raw: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw.append(json.loads(line))
    recovery = [e for e in raw if e.get("type") == "tool_call_recovery"]
    assert len(recovery) == 1, "两次 prepare（不同 store 实例）也只产生 1 条 recovery"
