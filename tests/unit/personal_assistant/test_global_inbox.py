"""Protect durable attention, exact content consumption and query isolation."""

import asyncio
from pathlib import Path

import pytest

from personal_assistant.gateway.global_inbox import GlobalInboxService, GlobalInboxStore
from personal_assistant.tools.inbox import content_digest, serialize_page


def make_service(tmp_path: Path):
    store = GlobalInboxStore(tmp_path / "global_agent.sqlite3")
    store.save_global_session("a", "main", str(tmp_path))
    return GlobalInboxService(store), store


def receive(service, key="one", **kwargs):
    return service.receive(
        agent_id="a",
        target="room",
        ingress_key=key,
        source_message_id=key,
        sender={"id": "u", "name": "User", "kind": "user"},
        content=kwargs.pop("content", [{"type": "text", "text": "hello"}]),
        **kwargs,
    )


def read(service, call="call", **kwargs):
    return asyncio.run(
        service.execute(
            "inbox",
            agent_id="a",
            session_id="main",
            tool_call_id=call,
            args={"action": "read", "target": "room", **kwargs},
        )
    )


def proof(page, call="call", **kwargs):
    return {
        "session_id": "main",
        "tool_call_id": call,
        "name": "inbox",
        "is_error": False,
        "serialization_status": "succeeded",
        "content_digest": content_digest(serialize_page(page)),
        **kwargs,
    }


def test_attention_watermark_dedup_and_stop_survive_reopen(tmp_path):
    service, store = make_service(tmp_path)
    receive(service)
    receive(service, "passive", should_process=False)
    receive(service, "history", normal_live_input=False)
    receive(service)
    assert receive(service, "echo", self_echo=True) is None
    assert store.get_signal_state("a")["latest_signal_seq"] == 1
    store.update_signal_state("a", stop_through_seq=1)
    store.close()
    service = GlobalInboxService(GlobalInboxStore(tmp_path / "global_agent.sqlite3"))
    assert len(read(service)["messages"]) == 3
    assert service.store.get_signal_state("a")["stop_through_seq"] == 1
    receive(service, "fresh")
    assert service.store.get_signal_state("a")["latest_signal_seq"] == 4


def test_only_durable_matching_content_consumes_each_long_message_part(tmp_path):
    service, store = make_service(tmp_path)
    receive(
        service,
        content=[
            {"type": "text", "text": "中" * 25000},
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": "YWJj"},
            },
        ],
    )
    page = read(service)
    assert len(page["messages"][0]["content"][0]["text"]) <= 24000
    assert page["has_more"]
    assert service.blocking_entries("a", "room")
    for invalid in (
        {"content_digest": "sha256:bad"},
        {"serialization_status": "fallback"},
        {"is_error": True},
        {"session_id": "child"},
    ):
        assert not service.confirm_committed_read(proof(page, **invalid))
    assert service.confirm_committed_read(proof(page))
    assert service.blocking_entries("a", "room")
    rest = read(service, "second")
    assert any(
        block["type"] == "image"
        for item in rest["messages"]
        for block in item["content"]
    )
    assert any(block["type"] == "image" for block in serialize_page(rest))
    assert service.confirm_committed_read(proof(rest, "second"))
    assert not service.blocking_entries("a", "room")
    assert len(store.read_unacked_events()) == 2
    assert not service.confirm_committed_read(proof(rest, "second"))


def test_cursor_scope_snapshot_and_history_never_consume(tmp_path):
    service, _ = make_service(tmp_path)
    receive(service)
    receive(service, "two")
    page = read(service, limit=1)
    receive(service, "three")
    rest = read(service, "second", cursor=page["next_cursor"])
    assert [m["message_id"] for m in rest["messages"]] == ["two"]
    with pytest.raises(ValueError, match="invalid_cursor"):
        asyncio.run(
            service.execute(
                "inbox",
                agent_id="a",
                session_id="main",
                tool_call_id="bad",
                args={
                    "action": "read",
                    "target": "other",
                    "cursor": page["next_cursor"],
                },
            )
        )
    with pytest.raises(ValueError, match="scope_not_allowed"):
        asyncio.run(
            service.execute(
                "inbox",
                agent_id="a",
                session_id="child",
                tool_call_id="bad",
                args={"action": "check"},
            )
        )
    history = asyncio.run(
        service.execute(
            "conversations",
            agent_id="a",
            session_id="main",
            tool_call_id="history",
            args={"action": "read", "target": "room"},
        )
    )
    assert history["history_scope"] == "received_only"
    assert len(service.blocking_entries("a", "room")) == 3


def test_work_journal_identity_ack_and_session_mapping_survive_restart(tmp_path):
    _, store = make_service(tmp_path)
    store.register_work_session("main", "a", "global_main")
    store.register_work_session(
        "child", "a", "subagent", parent_session_id="main", child_agent_id="child1"
    )
    kwargs = dict(
        event_id="event",
        root_agent_id="a",
        session_id="child",
        event_type="tool_start",
        payload={"name": "bash"},
    )
    event = store.append_work_event(**kwargs)
    assert store.append_work_event(**kwargs)["seq"] == event["seq"]
    journal_id = store.journal_id
    store.acknowledge_events(event["seq"])
    store.close()
    reopened = GlobalInboxStore(tmp_path / "global_agent.sqlite3")
    assert reopened.journal_id == journal_id
    assert reopened.get_work_session("child")["parent_session_id"] == "main"
    assert reopened.read_unacked_events() == []


def test_duplicate_work_event_does_not_leave_a_relay_sequence_gap(tmp_path):
    _, store = make_service(tmp_path)
    event = dict(
        event_id="one",
        root_agent_id="a",
        session_id="main",
        event_type="turn_started",
        payload={},
    )
    store.append_work_event(**event)
    store.append_work_event(**event)
    store.append_work_event(**{**event, "event_id": "two"})
    assert [row["seq"] for row in store.read_unacked_events()] == [1, 2]


def test_unavailable_image_keeps_its_part_pending_without_hiding_later_messages(
    tmp_path,
):
    service, _ = make_service(tmp_path)
    receive(service, content=[{"type": "text", "text": "visible"}, {"type": "image"}])
    receive(service, "later")
    page = read(service)
    assert page["errors"][0]["code"] == "attachment_unavailable"
    assert [m["message_id"] for m in page["messages"]] == ["one", "later"]
    assert service.confirm_committed_read(proof(page))
    assert [e["message_id"] for e in service.blocking_entries("a", "room")] == ["one"]


def test_online_conversation_discovery_includes_unmaterialized_local_sources(tmp_path):
    async def native(agent, action, args):
        return {
            "conversations": [
                {
                    "target": "native",
                    "name": "Native",
                    "kind": "group",
                    "channel": "web",
                    "participants": [],
                    "latest_message_at": "2020",
                    "history_availability": "im_history",
                }
            ],
            "has_more": False,
            "next_cursor": None,
        }

    _, store = make_service(tmp_path)
    service = GlobalInboxService(store, conversation_reader=native)
    service.receive(
        agent_id="a",
        target="local:one",
        ingress_key="ext",
        source_message_id="external",
        sender={},
        content=[{"type": "text", "text": "external"}],
        channel="feishu",
    )
    page = asyncio.run(
        service.execute(
            "conversations",
            agent_id="a",
            session_id="main",
            tool_call_id="list",
            args={"action": "list", "limit": 1},
        )
    )
    assert page["conversations"][0]["target"] == "local:one"
    page2 = asyncio.run(
        service.execute(
            "conversations",
            agent_id="a",
            session_id="main",
            tool_call_id="next",
            args={"action": "list", "limit": 1, "cursor": page["next_cursor"]},
        )
    )
    assert page2["conversations"][0]["target"] == "native"
