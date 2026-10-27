"""A real one-shot Schedule wakes its owning chat and delivers a separate reply."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._im_client import IMClient
from ._recording import StubLLMStack, _load_records, stub_im_user, stub_llm_stack


@pytest.mark.slow
@pytest.mark.parametrize(
    "stub_llm_stack",
    [
        {
            "script": "anthropic_sse_events_recording.py",
            "env": {"NANO_FIXTURE_SCENARIO": "cron"},
        }
    ],
    indirect=True,
)
def test_cron_job_auto_pushes_message(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    client = stub_im_user
    client.update_agent_config("e2e", features={"cron_scheduling": True})
    conversation = client.create_direct_conversation("e2e")
    client.send_message(conversation, "EVENTS-REGISTER")
    registration = client.wait_for_agent_reply_with(
        conversation, "SCHEDULE-REGISTERED", timeout=30
    )
    delivery = client.wait_for_agent_reply_with(
        conversation, "SCHEDULE-DELIVERED", timeout=30
    )
    assert delivery["id"] != registration["id"]
    records = _load_records(Path(stub_llm_stack.record_path))
    results = [
        block
        for request in records
        for message in request.get("messages", [])
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if block.get("type") == "tool_result"
        and block.get("tool_use_id") == "event-schedule"
    ]
    assert results and not results[0].get("is_error")
    assert "EVENTS-SCHEDULE-FIRED" in json.dumps(records[-1]["messages"][-1])
    # Only the tool creates the one-shot schedule; the test never sends its wake prompt.
    assert (
        len(
            [
                message
                for message in client.list_messages(conversation)
                if message.get("sender", {}).get("type") == "user"
            ]
        )
        == 1
    )
