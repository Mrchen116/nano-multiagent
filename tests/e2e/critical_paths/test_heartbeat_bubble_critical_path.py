"""Heartbeat file/cadence admission reaches the canonical IM chat without a model."""

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
            "env": {"NANO_FIXTURE_SCENARIO": "heartbeat"},
        }
    ],
    indirect=True,
)
def test_heartbeat_bubbles_actionable_message(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    client = stub_im_user
    agent = "e2e"
    conversation = client.create_direct_conversation(agent)
    client.send_message(conversation, "EVENTS-READY")
    initial = client.wait_for_agent_reply_with(conversation, "READY", timeout=30)
    config = client.get_agent_config(agent)
    workspace = next(
        row["workspace_root"]
        for row in client.list_agents()
        if row["agent_id"] == agent
    )
    heartbeat = Path(workspace) / ".nanoassistant" / "HEARTBEAT.md"
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.write_text("EVENTS-HEARTBEAT-FIRED\n")
    try:
        client.update_agent_config(
            agent, features={"heartbeat": True}, heartbeat_json='{"every":"2s"}'
        )
        delivery = client.wait_for_agent_reply_with(
            conversation, "HEARTBEAT-DELIVERED", timeout=30
        )
        assert delivery["id"] != initial["id"]
        records = _load_records(Path(stub_llm_stack.record_path))
        wake = next(
            request
            for request in records
            if "EVENTS-HEARTBEAT-FIRED" in json.dumps(request["messages"])
        )
        assert "Read .nanoassistant/HEARTBEAT.md" in json.dumps(wake["messages"])
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
    finally:
        client.update_agent_config(
            agent,
            features={"heartbeat": False},
            heartbeat_json=config.get("heartbeat_json"),
        )
        heartbeat.unlink(missing_ok=True)
