"""Round-trip tests for Message.tool_calls / token_usage persistence (feat-340-M2 R1)."""

from pathlib import Path

import pytest

from IM.domain.models import ToolCall, TokenUsage
from IM.infra.db import connect, initialize_schema
from IM.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)


def _build(tmp_path: Path) -> tuple[UserRepository, ConversationRepository, MessageRepository]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return UserRepository(connection), ConversationRepository(connection), MessageRepository(connection)


def test_create_message_persists_tool_calls_and_token_usage(tmp_path: Path) -> None:
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="t", participant_ids=[alice.id])

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


def test_create_message_default_tool_calls_and_token_usage_are_none(tmp_path: Path) -> None:
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="t", participant_ids=[alice.id])

    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hi",
    )
    assert created.tool_calls is None
    assert created.token_usage is None


def test_update_runtime_state_appends_content_and_upserts_tool_call(tmp_path: Path) -> None:
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="t", participant_ids=[alice.id])
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
            ToolCall(id="tc1", name="read_file", status="running", duration_ms=None, input={"p": "x"}, output=None)
        ],
    )
    # Complete the tool call, append more text, set token usage and delivery
    messages.update_runtime_state(
        message_id=created.id,
        content_append=" Done.",
        tool_calls_upsert=[
            ToolCall(id="tc1", name="read_file", status="completed", duration_ms=22, input={"p": "x"}, output="ok")
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


def test_tool_call_validates_status() -> None:
    with pytest.raises(ValueError):
        ToolCall(id="x", name="t", status="bogus", duration_ms=None, input={}, output=None)
