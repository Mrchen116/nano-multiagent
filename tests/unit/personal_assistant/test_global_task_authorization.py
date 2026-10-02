"""Prove global task consent comes from this run's committed Inbox input."""

import asyncio

from personal_assistant.gateway.global_inbox import GlobalInboxStore
from personal_assistant.gateway.task_graphs import TaskGraphBridge

from .test_task_graph_bridge import stack


def test_global_delete_forwards_only_actual_current_run_inbox_sources(tmp_path):
    from personal_assistant.gateway.global_inbox import GlobalInboxService
    from personal_assistant.tools.inbox import content_digest, serialize_inbox_page

    _, _, binder, manager, _ = stack(tmp_path, "global")
    store = GlobalInboxStore(tmp_path / "inbox.sqlite3")
    store.save_global_session("pa", "session", str(tmp_path))
    inbox = GlobalInboxService(store)
    inbox.receive(
        agent_id="pa",
        target="c_one",
        ingress_key="event",
        source_message_id="provider-id",
        im_message_id="im-id",
        sender={"id": "human", "kind": "user"},
        content=[{"type": "text", "text": "删除 tg_one"}],
    )
    page = asyncio.run(
        inbox.execute(
            "inbox",
            agent_id="pa",
            session_id="session",
            tool_call_id="read",
            args={"action": "read", "target": "c_one"},
        )
    )
    bridge = TaskGraphBridge(manager=manager, binder=binder, inbox=inbox)
    payload = {
        "source_agent_id": "pa",
        "origin_kernel_session_id": "session",
        "origin_run_id": "run",
        "tool_call_id": "delete",
        "args": {
            "action": "delete",
            "graph_id": "tg_one",
            "base_revision": 1,
            "request_key": "delete",
        },
    }
    assert (
        asyncio.run(bridge.execute(payload))["error"]["code"] == "confirmation_required"
    )
    manager.send_json_await_ack.assert_not_called()
    assert inbox.confirm_committed_read(
        {
            "session_id": "session",
            "run_id": "run",
            "tool_call_id": "read",
            "name": "inbox",
            "is_error": False,
            "serialization_status": "succeeded",
            "content_digest": content_digest(serialize_inbox_page(page)),
        }
    )
    assert asyncio.run(bridge.execute(payload))["ok"]
    assert manager.send_json_await_ack.call_args.args[1]["source_message_ids"] == [
        "im-id"
    ]
    assert (
        asyncio.run(bridge.execute({**payload, "origin_run_id": "later"}))["error"][
            "code"
        ]
        == "confirmation_required"
    )
    store.close()
