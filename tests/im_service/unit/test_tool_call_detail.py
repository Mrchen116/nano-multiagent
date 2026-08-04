"""Tool-call metadata persistence and public event serialization regressions."""

from pathlib import Path

from IM.api.ws.event_types import build_tool_call_completed_payload
from IM.domain.models import ToolCall
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.users import UserRepository


_DETAIL = {
    "command": "pytest -q",
    "exit_code": 0,
    "stdout": "OK",
    "stderr": "",
    "truncated": False,
}


def _tool_call() -> ToolCall:
    return ToolCall(
        id="call-1",
        name="bash",
        status="completed",
        input={"command": "pytest -q"},
        output="tests passed",
        detail=_DETAIL,
        emoji="🧪",
        approval="user_allow",
    )


def _repositories(
    tmp_path: Path,
) -> tuple[UserRepository, ConversationRepository, MessageRepository]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
    )


def test_completed_event_preserves_tool_call_metadata() -> None:
    payload = build_tool_call_completed_payload(
        conversation_id="conversation-1",
        message_id="message-1",
        tool_call=_tool_call(),
    )

    assert payload["tool_call"]["detail"] == _DETAIL
    assert payload["tool_call"]["emoji"] == "🧪"
    assert payload["tool_call"]["approval"] == "user_allow"


def test_message_history_preserves_tool_call_metadata(tmp_path: Path) -> None:
    users, conversations, messages = _repositories(tmp_path)
    owner = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[owner.id]
    )
    messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="done",
        tool_calls=[_tool_call()],
    )

    listed = messages.list_messages(conversation_id=conversation.id)

    assert listed[-1].tool_calls is not None
    persisted = listed[-1].tool_calls[0]
    assert persisted.detail == _DETAIL
    assert persisted.emoji == "🧪"
    assert persisted.approval == "user_allow"


def test_legacy_tool_call_history_defaults_optional_metadata(tmp_path: Path) -> None:
    users, conversations, messages = _repositories(tmp_path)
    owner = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[owner.id]
    )
    messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="done",
        tool_calls=[ToolCall(id="call-1", name="read", status="completed")],
    )

    listed = messages.list_messages(conversation_id=conversation.id)

    assert listed[-1].tool_calls is not None
    persisted = listed[-1].tool_calls[0]
    assert persisted.detail is None
    assert persisted.emoji is None
    assert persisted.approval is None
