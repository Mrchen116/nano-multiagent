"""feat-409-M1/R3: IM ToolCall.detail vertical (parse / serialize / persist).

detail is the presenter-produced structured dict forwarded by the Gateway. It must
survive every IM hop: streaming_delta parse → WS payload serialize → SQLite
persist/round-trip. Historical rows without detail must decode without error
(detail → None), so the front-end can fall back to the output string.
"""

from __future__ import annotations

from pathlib import Path

from IM.api.ws.event_types import (
    build_tool_call_completed_payload,
    tool_call_to_dict,
)
from IM.domain.models import ToolCall
from IM.infra.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
    _decode_tool_calls,
    _encode_tool_calls,
)
from IM.infra.db import connect, initialize_schema
from IM.ws.gateway_handler import _parse_tool_call


_SAMPLE_DETAIL = {
    "command": "pytest -q",
    "exit_code": 0,
    "stdout": "OK",
    "stderr": "",
    "truncated": False,
}


def _build(tmp_path: Path):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
    )


# --- parse (streaming_delta dict → ToolCall) ----------------------------------


def test_parse_tool_call_reads_detail() -> None:
    tc = _parse_tool_call(
        {
            "id": "tc1",
            "name": "bash",
            "status": "completed",
            "input": {"command": "pytest -q"},
            "output": "跑测试",
            "duration_ms": 12,
            "detail": _SAMPLE_DETAIL,
        }
    )
    assert tc.detail == _SAMPLE_DETAIL


def test_parse_tool_call_without_detail_is_none() -> None:
    tc = _parse_tool_call(
        {"id": "tc1", "name": "read", "status": "completed", "output": "42 lines"}
    )
    assert tc.detail is None


# --- serialize (ToolCall → WS payload) ----------------------------------------


def test_tool_call_to_dict_includes_detail() -> None:
    tc = ToolCall(
        id="tc1",
        name="bash",
        status="completed",
        duration_ms=12,
        input={"command": "x"},
        output="跑测试",
        detail=_SAMPLE_DETAIL,
    )
    payload = tool_call_to_dict(tc)
    assert payload["detail"] == _SAMPLE_DETAIL


def test_tool_call_to_dict_omits_detail_when_absent() -> None:
    tc = ToolCall(id="tc1", name="read", status="completed", output="42 lines")
    payload = tool_call_to_dict(tc)
    assert "detail" not in payload


def test_completed_payload_carries_detail() -> None:
    tc = ToolCall(
        id="tc1",
        name="bash",
        status="completed",
        duration_ms=12,
        input={},
        output="跑测试",
        detail=_SAMPLE_DETAIL,
    )
    payload = build_tool_call_completed_payload(
        conversation_id="c1", message_id="m1", tool_call=tc
    )
    assert payload["tool_call"]["detail"] == _SAMPLE_DETAIL


# --- encode/decode (SQLite JSON) ----------------------------------------------


def test_encode_decode_round_trip_with_detail() -> None:
    tc = ToolCall(
        id="tc1",
        name="bash",
        status="completed",
        duration_ms=12,
        input={"command": "x"},
        output="跑测试",
        detail=_SAMPLE_DETAIL,
    )
    encoded = _encode_tool_calls([tc])
    decoded = _decode_tool_calls(encoded)
    assert decoded is not None
    assert decoded[0].detail == _SAMPLE_DETAIL


def test_decode_legacy_row_without_detail() -> None:
    # Historical persisted JSON has no detail key — must decode to detail=None.
    legacy = '[{"id":"tc1","name":"read","status":"completed","output":"42 lines","input":{}}]'
    decoded = _decode_tool_calls(legacy)
    assert decoded is not None
    assert decoded[0].detail is None


# --- full persist round-trip --------------------------------------------------


def test_persist_round_trip_with_detail(tmp_path: Path) -> None:
    users, conversations, messages = _build(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="t", participant_ids=[alice.id]
    )
    tc = ToolCall(
        id="call_1",
        name="bash",
        status="completed",
        duration_ms=48,
        input={"command": "pytest"},
        output="跑测试",
        detail=_SAMPLE_DETAIL,
    )
    messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
        tool_calls=[tc],
    )
    listed = messages.list_messages(conversation_id=conversation.id)
    assert listed[-1].tool_calls is not None
    assert listed[-1].tool_calls[0].detail == _SAMPLE_DETAIL
