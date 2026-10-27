"""Explicit and timeout-promoted jobs execute, wake, and deliver through IM."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._im_client import IMClient
from ._recording import StubLLMStack, _load_records, stub_im_user, stub_llm_stack


@pytest.mark.parametrize(
    "promote", [False, True], ids=["explicit-background", "foreground-timeout"]
)
@pytest.mark.parametrize(
    "stub_llm_stack",
    [
        {
            "script": "anthropic_sse_events_recording.py",
            "env": {"NANO_FIXTURE_SCENARIO": "bash"},
        }
    ],
    indirect=True,
)
def test_background_job_completion_sends_distinct_followup(
    stub_im_user: IMClient,
    stub_llm_stack: StubLLMStack,
    promote: bool,
) -> None:
    client = stub_im_user
    agent = "e2e"
    client.update_agent_config(
        agent, tool_allowlist=["bash", "job_output", "job_kill", "send_message"]
    )
    conversation = client.create_direct_conversation(agent)
    args = {
        "description": "Run a short isolated background command",
        "command": "sleep 2; printf EVENTS-JOB-RESULT",
        "timeoutMs": 100 if promote else 10000,
        "run_in_background": not promote,
    }
    client.send_message(conversation, "EVENTS-COMMAND " + json.dumps(args))
    initial = client.wait_for_agent_reply_with(conversation, "JOB-LAUNCHED", timeout=30)
    completed = client.wait_for_agent_reply_with(
        conversation, "JOB-FINISHED", timeout=30
    )
    assert completed["id"] != initial["id"]
    assert "EVENTS-JOB-RESULT" in completed["content"]
    records = _load_records(Path(stub_llm_stack.record_path))
    results = [
        block
        for request in records
        for message in request.get("messages", [])
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if block.get("type") == "tool_result"
    ]
    bash = next(result for result in results if result["tool_use_id"] == "event-bash")
    expected = "moved to background job" if promote else "started background job"
    assert expected in json.dumps(bash["content"])
    output = next(
        result for result in results if result["tool_use_id"] == "event-output"
    )
    assert "EVENTS-JOB-RESULT" in json.dumps(output["content"])
    assert "completed" in json.dumps(output["content"])
    assert not output.get("is_error")
