"""Deterministic Inbox -> native child -> revised public dispatch across two chats."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import pytest

from ._im_client import IMClient
from ._im_polling import poll_until
from ._recording import StubLLMStack, _load_records, stub_llm_stack


def _get(http: httpx.Client, path: str, **params: Any) -> dict:
    response = http.get(path, params=params)
    response.raise_for_status()
    return response.json()


def _work(http: httpx.Client, base: str) -> dict:
    """Read all main turns/items through the same pagination used by the UI."""
    view = _get(http, base, limit=50)
    turns = list(view["turns"])
    cursor = view["next_cursor"]
    while cursor:
        page = _get(http, base, before_turn=cursor, limit=50)
        turns.extend(page["turns"])
        cursor = page["next_cursor"]
    for turn in turns:
        cursor = turn["next_items_cursor"]
        while cursor:
            path = (
                f"{base}/sessions/{quote(turn['session_id'], safe='')}/turns/"
                f"{quote(turn['turn_id'], safe='')}/items"
            )
            page = _get(http, path, after_seq=cursor, limit=200)
            turn["items"].extend(page["items"])
            cursor = page["next_cursor"]
    return {**view, "turns": turns}


def _tools(view: dict, name: str) -> list[dict]:
    return sorted(
        [
            {**item["payload"], "session_id": turn["session_id"]}
            for turn in view["turns"]
            for item in turn["items"]
            if item["kind"] == "tool" and item["payload"].get("name") == name
        ],
        key=lambda item: item["seq"],
    )


def _consumed(view: dict, target: str, message_id: str) -> dict | None:
    for call in _tools(view, "inbox"):
        args = call.get("input", {})
        if (
            call.get("status") != "completed"
            or args.get("action") != "read"
            or args.get("target") != target
        ):
            continue
        messages = call.get("detail", {}).get("messages", [])
        has_body = any(message.get("id") == message_id for message in messages)
        committed = any(
            fact.get("type") == "inbox_read_committed"
            and any(
                ref.get("conversation_id") == target
                and ref.get("message_id") == message_id
                for ref in fact.get("source_refs", [])
            )
            for fact in call.get("work_facts", [])
        )
        if has_body and committed:
            return call
    return None


def _delegation(view: dict) -> dict | None:
    return next(
        (
            call
            for call in _tools(view, "subagent")
            if call.get("status") == "completed"
            and not call.get("input", {}).get("agent_id")
            and call.get("input", {}).get("run_in_background") is True
            and call.get("detail", {}).get("child_session_id")
        ),
        None,
    )


def _followup(view: dict, child_id: str, amendment: str) -> dict | None:
    return next(
        (
            call
            for call in _tools(view, "send_message")
            if call.get("status") == "completed"
            and call.get("input", {}).get("agent_id") == child_id
            and amendment in call.get("input", {}).get("message", "")
        ),
        None,
    )


def _dispatches(view: dict, target: str) -> list[dict]:
    return [
        fact
        for call in _tools(view, "send_message")
        for fact in call.get("work_facts", [])
        if fact.get("type") in {"dispatch_confirmed", "message_sent"}
        and fact.get("conversation_id") == target
    ]


@pytest.mark.parametrize(
    "stub_llm_stack",
    [
        {
            "script": "anthropic_sse_collaboration_recording.py",
            "env": {"NANO_FIXTURE_COLLABORATION": "global"},
        }
    ],
    indirect=True,
)
def test_global_agent_reads_cross_chat_amendment_and_follows_same_child(
    stub_llm_stack: StubLLMStack,
) -> None:
    """Read actual A/B bodies, follow the same native child, and deliver only to A."""
    im_user = IMClient(stub_llm_stack.im_url)
    im_user.register_or_login("nano", "nano1234")
    suffix = secrets.token_hex(4)
    agent_id = f"e2eGlobal{suffix}"
    amendment = f"AMEND{suffix.upper()}"
    try:
        node_id = im_user.wait_for_online_node(timeout=40)
        with httpx.Client(
            base_url=im_user.im_url,
            headers={"Authorization": f"Bearer {im_user.token}"},
            timeout=30,
        ) as http:
            response = http.post(
                f"/im/v1/nodes/{node_id}/agents",
                json={
                    "agent_id": agent_id,
                    "owner_id": im_user.owner_id,
                    "display_name": f"Global J2 {suffix}",
                    "work_mode": "global",
                    "group_reply_policy": "ALWAYS",
                    "default_model": stub_llm_stack.llm_model,
                    "tool_allowlist": [
                        "inbox",
                        "conversations",
                        "send_message",
                        "subagent",
                    ],
                    "skills": [],
                    "features": {
                        "memory_curation": False,
                        "skill_creation": False,
                        "task_graph": False,
                        "intelligent_ui": False,
                        "cron_scheduling": False,
                        "heartbeat": False,
                    },
                    "custom_prompt": "Isolated deterministic collaboration regression.",
                },
            )
            assert response.is_success, response.text
            im_user.wait_for_agent_listed(agent_id, timeout=40)
            chat_a = im_user.create_direct_conversation(
                agent_id, title=f"J2 A {suffix}"
            )
            chat_b = im_user.create_group_conversation(
                [agent_id], title=f"J2 B {suffix}"
            )
            base = f"/im/v1/agents/{agent_id}/work"
            message_a = im_user.send_message(
                chat_a,
                "J2_START: delegate, wait for my revision, and only then reply here.",
            )
            first = poll_until(
                lambda: _work(http, base),
                lambda view: bool(
                    _consumed(view, chat_a, message_a) and _delegation(view)
                ),
                timeout=60,
                interval=0.2,
                desc="A body committed and native background child created",
            )
            main_session = first["main_session_id"]
            delegation = _delegation(first)
            assert delegation is not None
            child_id = delegation["detail"]["child_session_id"]
            assert not im_user.agent_messages(chat_a, agent_id)
            assert not im_user.agent_messages(chat_b, agent_id)
            message_b = im_user.send_message(
                chat_b,
                f"J2_AMEND: {amendment}. Follow the same child and deliver its revised result to the original chat.",
            )
            final = poll_until(
                lambda: _work(http, base),
                lambda view: any(
                    amendment in fact.get("text", "")
                    for fact in _dispatches(view, chat_a)
                ),
                timeout=60,
                interval=0.2,
                desc="actual child revision returned and dispatched to A",
            )
            assert _consumed(final, chat_b, message_b)
            followup = _followup(final, child_id, amendment)
            assert followup is not None
            assert followup["session_id"] == delegation["session_id"] == main_session
            assert followup["seq"] > delegation["seq"]
            assert final["main_session_id"] == main_session
            assert len(_tools(final, "subagent")) == 1
            assert {turn["session_id"] for turn in final["turns"]} == {main_session}
            linked = [
                session
                for session in final["other_executions"]
                if session.get("child_agent_id") == child_id
            ]
            assert len(linked) == 1
            assert linked[0]["parent_session_id"] == main_session
            child = _get(
                http, f"{base}/sessions/{quote(linked[0]['session_id'], safe='')}/turns"
            )
            assert child["turns"], (
                "actual child session must have a readable Work trace"
            )
            deliveries = _dispatches(final, chat_a)
            messages = im_user.agent_messages(chat_a, agent_id)
            assert len(messages) == len(deliveries) == 1
            assert messages[0]["id"] == deliveries[0]["message_id"]
            assert messages[0]["content"] == f"CHILD-REVISED {amendment}"
            assert messages[0]["delivery_status"] == "completed"
            assert not messages[0].get("tool_calls")
            assert not messages[0].get("thinking")
            assert not messages[0].get("permission_requests")
            assert not im_user.agent_messages(chat_b, agent_id)
            records = _load_records(Path(stub_llm_stack.record_path))
            child_requests = [
                row["request"] for row in records if row["session"] == child_id
            ]
            assert any(
                "J2_CHILD_INITIAL" in json.dumps(request["messages"])
                for request in child_requests
            )
            assert any(
                "J2_CHILD_REVISION " + amendment in json.dumps(request["messages"])
                for request in child_requests
            )
            parent_requests = [
                row["request"] for row in records if row["session"] == main_session
            ]
            assert any(
                "CHILD-REVISED " + amendment in json.dumps(request["messages"])
                for request in parent_requests
            )
    finally:
        im_user.close()
