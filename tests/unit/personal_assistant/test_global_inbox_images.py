"""Protect authorized retryable image materialization and frozen read receipts."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from personal_assistant.gateway.global_inbox import GlobalInboxService, GlobalInboxStore
from personal_assistant.tools.inbox import (
    content_digest,
    serialize_inbox_page as serialize_page,
)


IMAGE = {
    "type": "image",
    "source": {"type": "base64", "media_type": "image/png", "data": "aW1hZ2U="},
}
LOCATOR = {
    "type": "image",
    "attachment": {"url": "/im/v1/files/image", "content_type": "image/png"},
    "error": "temporarily unavailable",
}


async def query(service, call, tool="inbox", **kwargs):
    return await service.execute(
        tool,
        agent_id="agent",
        session_id="main",
        tool_call_id=call,
        args={"action": "read", "target": "room", **kwargs},
    )


def committed(call, page):
    return {
        "name": "inbox",
        "session_id": "main",
        "tool_call_id": call,
        "is_error": False,
        "serialization_status": "succeeded",
        "content_digest": content_digest(serialize_page(page)),
    }


@pytest.mark.asyncio
async def test_image_retry_runs_without_database_lock_and_never_changes_old_receipt(
    tmp_path,
):
    store = GlobalInboxStore(tmp_path / "global.sqlite3")
    store.save_global_session("agent", "main", str(tmp_path))
    attempts = []

    async def materialize(block):
        attempts.append(block)
        # A recorder thread can still append while image IO is suspended.
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(store.get_signal_state, "agent")
            state = await asyncio.wait_for(asyncio.wrap_future(future), timeout=1)
        finally:
            executor.shutdown(wait=False)
        assert state["latest_signal_seq"] == 1
        return None if len(attempts) == 1 else IMAGE

    service = GlobalInboxService(store, image_materializer=materialize)
    service.receive(
        agent_id="agent",
        target="room",
        ingress_key="message",
        source_message_id="message",
        sender={},
        content=[{"type": "text", "text": "caption"}, LOCATOR],
    )
    first = await query(service, "first")
    assert first["errors"][0]["code"] == "attachment_unavailable"
    assert service.confirm_committed_read(committed("first", first))
    assert service.blocking_entries("agent", "room")
    assert await query(service, "first") == first
    assert len(attempts) == 1
    second = await query(service, "second")
    assert second["messages"][0]["part_key"] == first["errors"][0]["part_key"]
    assert second["messages"][0]["content"][0]["source"] == IMAGE["source"]
    assert len(attempts) == 2
    assert service.blocking_entries("agent", "room")
    assert service.confirm_committed_read(committed("second", second))
    assert service.blocking_entries("agent", "room") == []
    assert await query(service, "first") == first
    assert attempts == [LOCATOR, LOCATOR]


@pytest.mark.asyncio
async def test_native_history_materializes_actual_images_without_inbox_consumption(
    tmp_path,
):
    store = GlobalInboxStore(tmp_path / "global.sqlite3")
    store.save_global_session("agent", "main", str(tmp_path))
    calls = []
    native_image = {
        "type": "image",
        "url": "/im/v1/files/native",
        "content_type": "image/png",
    }

    async def native(agent, action, args):
        return {
            "target": "room",
            "messages": [
                {
                    "message_id": "message",
                    "part_key": "image",
                    "content": [native_image],
                    "complete_message": True,
                }
            ],
            "next_cursor": None,
            "has_more": False,
            "history_scope": "im_history",
        }

    async def materialize(block):
        calls.append(block)
        return IMAGE

    service = GlobalInboxService(
        store, conversation_reader=native, image_materializer=materialize
    )
    service.receive(
        agent_id="agent",
        target="room",
        conversation_id="room",
        ingress_key="message",
        source_message_id="message",
        sender={},
        content=[LOCATOR],
    )
    page = await query(service, "history", tool="conversations")
    assert page["messages"][0]["content"][0]["source"] == IMAGE["source"]
    assert serialize_page(page)[1] == {
        "type": "image",
        "data": IMAGE["source"]["data"],
        "mimeType": "image/png",
    }
    assert calls == [native_image]
    assert service.blocking_entries("agent", "room")
    assert not service.confirm_committed_read(committed("history", page))
    with pytest.raises(ValueError, match="scope_not_allowed"):
        await service.execute(
            "inbox",
            agent_id="agent",
            session_id="child",
            tool_call_id="bad",
            args={"action": "read", "target": "room"},
        )
    assert calls == [native_image]


@pytest.mark.asyncio
async def test_concurrent_image_retries_cannot_replace_content_bound_to_a_receipt(
    tmp_path,
):
    store = GlobalInboxStore(tmp_path / "global.sqlite3")
    store.save_global_session("agent", "main", str(tmp_path))
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    attempts = 0

    async def materialize(block):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            first_entered.set()
            await release_first.wait()
            return {"type": "image", "source": {**IMAGE["source"], "data": "b3RoZXI="}}
        return IMAGE

    service = GlobalInboxService(store, image_materializer=materialize)
    service.receive(
        agent_id="agent",
        target="room",
        ingress_key="one",
        source_message_id="one",
        sender={},
        content=[LOCATOR],
    )
    slow = asyncio.create_task(query(service, "slow"))
    await asyncio.wait_for(first_entered.wait(), timeout=1)
    fast = await query(service, "fast")
    release_first.set()
    slow_page = await asyncio.wait_for(slow, timeout=1)
    assert fast["messages"][0]["content"][0]["source"] == IMAGE["source"]
    assert slow_page["messages"][0]["content"][0]["source"] == IMAGE["source"]
    assert service.confirm_committed_read(committed("fast", fast))
    assert not service.blocking_entries("agent", "room")
