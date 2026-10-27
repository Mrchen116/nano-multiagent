"""Human -> Agent -> Agent group routing and the unmentioned-member gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._im_client import IMClient
from ._im_polling import assert_absent_within, poll_until
from ._recording import (
    StubLLMStack,
    _load_records,
    _message_blob,
    _system_blob,
    stub_im_user,
    stub_llm_stack,
)


@pytest.mark.parametrize(
    "stub_llm_stack", [{"script": "anthropic_sse_group_recording.py"}], indirect=True
)
def test_group_mentions_route_to_peer_and_leave_unmentioned_peer_idle(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    """Both positive relay and negative admission cross real IM/Node/provider seams."""
    client = stub_im_user
    node = client.wait_for_online_node()
    client.create_agent(
        node,
        "group-b",
        custom_prompt="FIXTURE_GROUP_B",
        default_model=stub_llm_stack.llm_model,
    )
    user_b = next(
        a["user_id"] for a in client.list_agents() if a["agent_id"] == "group-b"
    )
    client.create_agent(
        node,
        "group-a",
        custom_prompt=f"FIXTURE_GROUP_A target={user_b}",
        default_model=stub_llm_stack.llm_model,
    )
    chat = client.create_group_conversation(["group-a", "group-b"])
    client.send_message(chat, "GROUP_START", mentions=["group-a"])
    replies = poll_until(
        lambda: client.list_messages(chat),
        lambda rows: any(
            (m.get("sender") or {}).get("id") == "group-b"
            and "GROUP_B_RECEIVED" in m.get("content", "")
            for m in rows
        ),
        timeout=40,
        desc="group B wakes from A's actual mention",
    )
    a = [m for m in replies if (m.get("sender") or {}).get("id") == "group-a"]
    assert len(a) == 1
    assert f'target_id="{user_b}"' in a[0]["content"]
    record = Path(stub_llm_stack.record_path)
    b_requests = [
        r for r in _load_records(record) if "FIXTURE_GROUP_B" in _system_blob(r)
    ]
    assert b_requests and "GROUP_RELAY" in _message_blob(b_requests[-1])

    # A second group prevents the first conversation's peer history from hiding admission.
    solo = client.create_group_conversation(["group-a", "group-b"])
    client.send_message(solo, "GROUP_SOLO", mentions=["group-a"])
    client.wait_for_agent_reply_with(solo, "GROUP_A_ONLY", timeout=40)
    assert_absent_within(
        lambda: client.agent_messages(solo, "group-b"),
        bool,
        window=3,
        desc="unmentioned B must not reply",
    )
    # No provider request is stronger than merely observing no public message.
    assert not any(
        "GROUP_SOLO" in _message_blob(r)
        for r in _load_records(record)
        if "FIXTURE_GROUP_B" in _system_blob(r)
    )
