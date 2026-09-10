"""Protect compact Inbox names, pagination and source identity."""

import asyncio

from tests.unit.personal_assistant.test_global_inbox import (
    make_service,
    proof,
    read,
    receive,
)


def test_check_defaults_to_all_sources_and_budget_cursor_loses_none(tmp_path):
    import json
    from personal_assistant.tools.inbox import InboxTool

    service, store = make_service(tmp_path)
    for i in range(35):
        service.receive(
            agent_id="a",
            target=f"room-{i}",
            name=f"Room {i}",
            ingress_key=f"m-{i}",
            source_message_id=f"m-{i}",
            sender={"id": "u", "name": "User", "kind": "user"},
            content=[{"type": "text", "text": "hello"}],
            attention_reasons=["mention"] if i == 0 else ["direct"],
        )

    def check(**args):
        page = asyncio.run(
            service.execute(
                "inbox",
                agent_id="a",
                session_id="main",
                tool_call_id="",
                args={"action": "check", **args},
            )
        )
        return json.loads(InboxTool().serialize_result(page))

    result = check()
    assert len(result["conversations"]) == 35
    assert "next_cursor" not in result and "has_more" not in result
    assert result["conversations"][0]["mentioned"] is True
    assert "mentioned" not in result["conversations"][1]
    for i in range(35):
        service.update_target("a", f"room-{i}", name="Long chat title " * 90)
    seen = []
    page = check()
    assert page.get("next_cursor")
    while True:
        seen.extend(row["target"] for row in page["conversations"])
        if not page.get("next_cursor"):
            break
        page = check(cursor=page["next_cursor"])
    assert len(seen) == len(set(seen)) == 35


def test_current_names_are_projected_without_mutating_message_identity(tmp_path):
    import json
    from personal_assistant.tools.inbox import InboxTool

    service, store = make_service(tmp_path)
    receive(service, conversation_id="room", name="room")
    current_name = "Alex renamed"
    calls = []

    async def metadata(agent, action, args):
        calls.append((action, args))
        return {
            "conversations": [
                {
                    "target": "room",
                    "name": f"与 {current_name} 的私聊",
                    "participants": [{"id": "u", "name": current_name, "kind": "user"}],
                }
            ]
        }

    service._conversation_reader = metadata
    first = read(service)
    model = json.loads(InboxTool().serialize_result(first))
    assert model["name"] == "与 Alex renamed 的私聊"
    assert model["messages"][0]["sender"] == {
        "name": current_name,
        "user_id": "u",
        "type": "user",
    }
    current_name = "Alex changed again"
    assert read(service) == first  # Same tool call replays its exact receipt page.
    next_page = read(service, "new-call")
    assert next_page["messages"][0]["sender"]["name"] == current_name
    assert calls[0] == ("describe", {"targets": ["room"]})
    assert service.confirm_committed_read(proof(first))
    assert not service.blocking_entries("a", "room")


def test_missing_source_ids_do_not_merge_distinct_messages_or_invent_partial(tmp_path):
    import json
    from personal_assistant.tools.inbox import InboxTool

    service, _ = make_service(tmp_path)
    for i in range(2):
        service.receive(
            agent_id="a",
            target="room",
            ingress_key=f"anonymous-{i}",
            source_message_id=None,
            sender={"id": "u", "kind": "user"},
            content=[
                {"type": "text", "text": f"first-{i}"},
                {"type": "text", "text": f"second-{i}"},
            ],
        )
    page = read(service)
    messages = json.loads(InboxTool().serialize_result(page))["messages"]
    assert [m["text"] for m in messages] == ["first-0second-0", "first-1second-1"]
    assert all(
        "id" not in m and "partial" not in m and "entry_seq" not in m for m in messages
    )
    assert service.confirm_committed_read(proof(page))
    assert not service.blocking_entries("a", "room")
