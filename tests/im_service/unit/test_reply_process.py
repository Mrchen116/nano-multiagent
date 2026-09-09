"""Reply process persistence through the public bridge and history seams."""

from tests.im_service.unit.test_event_bridge import _make_bridge
from IM.domain.models import ReplyProcessItem, ToolCall


def test_reply_process_survives_terminal_history_and_replay(tmp_path):
    bridge, conv_id, agent_uid, messages, captured = _make_bridge(tmp_path)
    message = bridge.on_turn_start(
        conversation_id=conv_id, agent_user_id=agent_uid, agent_id="planner"
    )
    draft = ReplyProcessItem(
        item_id="draft-1",
        kind="draft",
        run_id="run-1",
        text="complete old draft\n" * 300,
        draft_id="d1",
        source="assistant",
    )
    bridge.on_reply_process(message_id=message.id, item=draft)
    bridge.on_reply_process(message_id=message.id, item=draft)
    bridge.on_tool_call_upserted(
        message_id=message.id,
        tool_call=ToolCall(id="t1", name="read", status="running", input={}),
    )
    bridge.on_reply_process(
        message_id=message.id,
        item=ReplyProcessItem(
            item_id="r1",
            kind="revalidation",
            run_id="run-1",
            status="running",
            source_messages=[
                {
                    "message_id": "source-1",
                    "sender": "Alice",
                    "timestamp": "2026-09-09T00:00:00Z",
                }
            ],
        ),
    )
    bridge.on_message_completed(
        message_id=message.id, final_content="", delivery_status="failed"
    )
    saved = messages.list_messages(conversation_id=conv_id)[0]
    assert saved.content == ""
    assert len(saved.reply_process) == 2
    assert saved.reply_process[0].text == draft.text
    assert [
        saved.reply_process[0].seq,
        saved.tool_calls[0].seq,
        saved.reply_process[1].seq,
    ] == [0, 1, 2]
    assert saved.reply_process[1].status == "failed"
    assert not any(event.event_type == "message.delta" for event in captured)


def test_silent_completion_keeps_process_and_api_snapshot(tmp_path):
    from IM.api.routes.messages import to_message_response
    from IM.ws.gateway.protocol import parse_streaming_delta_event

    bridge, conv_id, agent_uid, messages, captured = _make_bridge(tmp_path)
    message = bridge.on_turn_start(
        conversation_id=conv_id, agent_user_id=agent_uid, agent_id="planner"
    )
    event = parse_streaming_delta_event(
        {
            "kind": "reply_process",
            "message_id": message.id,
            "item": {
                "item_id": "draft-1",
                "kind": "draft",
                "run_id": "run",
                "text": "  original text\n",
            },
        }
    )
    bridge.on_reply_process(message_id=event.message_id, item=event.reply_process_item)
    bridge.on_message_discarded(message_id=message.id, reason="no_reply_token")
    saved = messages.get_message(message_id=message.id)
    payload = to_message_response(saved).model_dump(mode="json")
    assert payload["reply_process"][0]["text"] == "  original text\n"
    assert payload["content"] == ""
    assert payload["delivery_status"] == "completed"
    assert not any(event.event_type == "message.discarded" for event in captured)


import pytest


@pytest.mark.asyncio
async def test_fork_preserves_process_sequence_and_remaps_source_references(tmp_path):
    from tests.im_service.unit.test_fork_conversation_edges import (
        _setup,
        _online,
        _ok_fork,
    )

    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    source = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=human.id,
        content="update",
        sender_type="user",
    )
    reply = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="answer",
        sender_type="agent",
        kernel_message_id="kernel-1",
    )
    messages.append_thinking_segment(message_id=reply.id, text="thinking")
    messages.upsert_reply_process(
        message_id=reply.id,
        item=ReplyProcessItem(
            item_id="r1",
            kind="revalidation",
            run_id="run",
            status="completed",
            source_messages=[
                {
                    "message_id": source.id,
                    "sender": "Alice",
                    "timestamp": source.created_at,
                }
            ],
        ),
    )
    branch = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=reply.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork([], id_map={"kernel-1": "branch-1"}),
    )
    copied = messages.list_all_messages(conversation_id=branch.id)
    assert copied[1].thinking[0].seq == 0
    assert copied[1].reply_process[0].seq == 1
    assert copied[1].reply_process[0].source_messages[0]["message_id"] == copied[0].id
