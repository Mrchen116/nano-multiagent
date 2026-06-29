"""Round-trip tests for Message.tool_calls / token_usage persistence (feat-340-M2 R1)."""

from pathlib import Path

import pytest

from IM.domain.models import ThinkingSegment, ToolCall, TokenUsage
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)


def _build(
    tmp_path: Path,
) -> tuple[UserRepository, ConversationRepository, MessageRepository]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
    )


def test_create_message_persists_tool_calls_and_token_usage(tmp_path: Path) -> None:
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )

    tc = ToolCall(
        id="call_1",
        name="list_files",
        status="completed",
        duration_ms=48,
        input={"path": "."},
        output="a.py\nb.py",
    )
    usage = TokenUsage(output=312, context_used=14800, context_window=200000)

    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
        tool_calls=[tc],
        token_usage=usage,
    )

    assert created.tool_calls is not None
    assert [t.id for t in created.tool_calls] == ["call_1"]
    assert created.token_usage == usage

    listed = messages.list_messages(conversation_id=conversation.id)
    assert listed[-1].tool_calls is not None
    assert listed[-1].tool_calls[0].name == "list_files"
    assert listed[-1].tool_calls[0].input == {"path": "."}
    assert listed[-1].token_usage == usage


def test_kernel_message_id_round_trip(tmp_path: Path) -> None:
    """feat-445-M1 R1: kernel message_id 经 create_message / update_runtime_state 持久化往返。

    fork 用消息行上的 kernel message_id 把「被点的 IM 气泡」对齐回「源 session 日志中那条
    assistant 消息」。该 id 必须能写入、读回、且不被无关 patch 清掉。
    """
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )

    # create_message 直接带 kernel_message_id（fork 复制展示历史走这条）
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
        kernel_message_id="kmsg-create",
    )
    assert created.kernel_message_id == "kmsg-create"
    listed = messages.list_messages(conversation_id=conversation.id)
    assert listed[-1].kernel_message_id == "kmsg-create"

    # update_runtime_state 落 kernel_message_id（relay message_completed 走这条）
    updated = messages.update_runtime_state(
        message_id=created.id, kernel_message_id="kmsg-update"
    )
    assert updated.kernel_message_id == "kmsg-update"

    # 不带 kernel_message_id 的无关 patch 不得清掉已写入的值
    after = messages.update_runtime_state(
        message_id=created.id, content_append=" world"
    )
    assert after.kernel_message_id == "kmsg-update"
    assert (
        messages.list_messages(conversation_id=conversation.id)[-1].kernel_message_id
        == "kmsg-update"
    )


def test_token_usage_cache_fields_round_trip(tmp_path: Path) -> None:
    """feat-439-M1: 缓存命中两字段经 encode/decode 持久化往返不丢。"""
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )

    usage = TokenUsage(
        output=15,
        context_used=400,
        context_window=200000,
        total=415,
        cache_read_tokens=270,
        cache_total_input_tokens=400,
    )
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hi",
        token_usage=usage,
    )
    assert created.token_usage == usage

    listed = messages.list_messages(conversation_id=conversation.id)
    assert listed[-1].token_usage is not None
    assert listed[-1].token_usage.cache_read_tokens == 270
    assert listed[-1].token_usage.cache_total_input_tokens == 400


def test_create_message_default_tool_calls_and_token_usage_are_none(
    tmp_path: Path,
) -> None:
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )

    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hi",
    )
    assert created.tool_calls is None
    assert created.token_usage is None


def test_update_runtime_state_appends_content_and_upserts_tool_call(
    tmp_path: Path,
) -> None:
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="",
        allow_empty=True,
    )

    # Append text + upsert a running tool call
    messages.update_runtime_state(
        message_id=created.id,
        content_append="Let me check...",
        tool_calls_upsert=[
            ToolCall(
                id="tc1",
                name="read_file",
                status="running",
                duration_ms=None,
                input={"p": "x"},
                output=None,
            )
        ],
    )
    # Complete the tool call, append more text, set token usage and delivery
    messages.update_runtime_state(
        message_id=created.id,
        content_append=" Done.",
        tool_calls_upsert=[
            ToolCall(
                id="tc1",
                name="read_file",
                status="completed",
                duration_ms=22,
                input={"p": "x"},
                output="ok",
            )
        ],
        token_usage=TokenUsage(output=10, context_used=100, context_window=200000),
        delivery_status="completed",
    )

    final = messages.list_messages(conversation_id=conversation.id)[-1]
    assert final.content == "Let me check... Done."
    assert final.delivery_status == "completed"
    assert final.token_usage is not None
    assert final.token_usage.output == 10
    assert final.tool_calls is not None
    assert len(final.tool_calls) == 1
    only = final.tool_calls[0]
    assert only.status == "completed"
    assert only.output == "ok"
    assert only.duration_ms == 22


def test_thinking_and_tools_share_monotonic_process_seq(
    tmp_path: Path,
) -> None:
    """feat-439-M2: 思考段与工具调用共享一个 per-message 单调递增 seq（真实到达序、唯一）。

    渲染端按 seq 把过程项 merge 成一条时间线；唯一 seq 让 live 事件可幂等去重。
    """
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="",
        allow_empty=True,
    )

    # 真实到达序：think → tool → think → tool → think
    messages.append_thinking_segment(
        message_id=created.id, text="先看 types.py"
    )  # seq 0
    messages.update_runtime_state(
        message_id=created.id,
        tool_calls_upsert=[ToolCall(id="t1", name="read", status="running")],  # seq 1
    )
    messages.append_thinking_segment(message_id=created.id, text="再归一口径")  # seq 2
    messages.update_runtime_state(
        message_id=created.id,
        tool_calls_upsert=[ToolCall(id="t2", name="edit", status="running")],  # seq 3
    )
    messages.append_thinking_segment(message_id=created.id, text="收尾总结")  # seq 4
    # 工具完成（同 id 二次 upsert）必须保留首次分配的 seq，不再 ++
    messages.update_runtime_state(
        message_id=created.id,
        tool_calls_upsert=[ToolCall(id="t1", name="read", status="completed")],
    )

    final = messages.list_messages(conversation_id=conversation.id)[-1]
    assert final.thinking is not None
    assert [(s.seq, s.text) for s in final.thinking] == [
        (0, "先看 types.py"),
        (2, "再归一口径"),
        (4, "收尾总结"),
    ]
    assert final.tool_calls is not None
    by_id = {t.id: t for t in final.tool_calls}
    assert by_id["t1"].seq == 1 and by_id["t1"].status == "completed"
    assert by_id["t2"].seq == 3
    # 全部过程项 seq 唯一
    all_seqs = [s.seq for s in final.thinking] + [t.seq for t in final.tool_calls]
    assert sorted(all_seqs) == [0, 1, 2, 3, 4]


def test_thinking_default_none_and_legacy_rows(tmp_path: Path) -> None:
    """无思考的消息 thinking 为 None（不留空壳）。"""
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hi",
    )
    assert created.thinking is None
    listed = messages.list_messages(conversation_id=conversation.id)[-1]
    assert listed.thinking is None
    # ThinkingSegment 是简单值对象
    seg = ThinkingSegment(seq=2, text="x")
    assert (seg.seq, seg.text) == (2, "x")


def test_tool_call_validates_status() -> None:
    with pytest.raises(ValueError):
        ToolCall(
            id="x", name="t", status="bogus", duration_ms=None, input={}, output=None
        )


def test_elapsed_ms_is_none_on_create(tmp_path: Path) -> None:
    """feat-414-M1: turn_start 建行时 elapsed_ms 为 NULL。"""
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="",
        allow_empty=True,
    )
    assert created.elapsed_ms is None


def test_update_runtime_state_persists_elapsed_ms(tmp_path: Path) -> None:
    """feat-414-M1: update_runtime_state 传入 elapsed_ms 时写入并能从 list_messages 读回。"""
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="",
        allow_empty=True,
    )
    messages.update_runtime_state(
        message_id=created.id,
        content_replace="final answer",
        delivery_status="completed",
        elapsed_ms=3721,
    )
    listed = messages.list_messages(conversation_id=conversation.id)
    assert listed[-1].elapsed_ms == 3721


def test_update_runtime_state_elapsed_ms_none_leaves_column_unchanged(
    tmp_path: Path,
) -> None:
    """feat-414-M1: elapsed_ms=None（默认）时不改写已有值（Sentinel 机制，同 token_usage）。"""
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="",
        allow_empty=True,
    )
    # 写入 elapsed_ms
    messages.update_runtime_state(
        message_id=created.id,
        delivery_status="completed",
        elapsed_ms=5000,
    )
    # 再次 update 不传 elapsed_ms，不应清掉已有值
    messages.update_runtime_state(
        message_id=created.id,
        content_replace="updated content",
    )
    listed = messages.list_messages(conversation_id=conversation.id)
    assert listed[-1].elapsed_ms == 5000


def test_decode_token_usage_with_null_total_derives_from_context_plus_output(
    tmp_path: Path,
) -> None:
    """bugfix-390 FIX-1: pre-M17 rows have "total": null in JSON.

    parsed.get("total", 0) returns None (key exists, value is null) not 0,
    so int(None) would raise TypeError → the old except block silently returned None
    → the entire message.token_usage became None → token chip not rendered.

    The fix moves the fallback derivation into _decode_token_usage so the decode
    layer is the single source of truth for "total is always non-None".
    """
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )

    # Persist a message with total explicitly set, then manually corrupt its JSON in DB
    # to simulate the pre-M17 "total": null persisted row.
    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="old message",
        token_usage=TokenUsage(
            output=100, context_used=5000, context_window=200000, total=5100
        ),
    )

    # Overwrite token_usage JSON with "total": null to simulate the pre-M17 row
    import json
    from IM.infra.db import connect as _connect

    conn = _connect(tmp_path / "im.db")
    null_total_json = json.dumps(
        {
            "output": 100,
            "context_used": 5000,
            "context_window": 200000,
            "total": None,
        }
    )
    conn.execute(
        "UPDATE messages SET token_usage_json = ? WHERE id = ?",
        (null_total_json, created.id),
    )
    conn.commit()

    listed = messages.list_messages(conversation_id=conversation.id)
    usage = listed[-1].token_usage

    # Must decode successfully (not None) and total must be derived as context_used + output
    assert usage is not None, (
        "token_usage must not be None for pre-M17 rows with total=null"
    )
    assert usage.total == 5100, f"expected total=5100 (5000+100), got {usage.total}"
    assert usage.output == 100
    assert usage.context_used == 5000
