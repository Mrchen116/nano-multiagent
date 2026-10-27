"""Native foreground child results and failures cross the real IM/Node boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._im_client import IMClient
from ._recording import StubLLMStack, _load_records, stub_llm_stack


@pytest.mark.parametrize(
    "stub_llm_stack",
    [{"script": "anthropic_sse_collaboration_recording.py"}],
    indirect=True,
)
def test_foreground_child_output_and_failure_are_isolated(
    stub_llm_stack: StubLLMStack,
) -> None:
    """Observe child output, an actual provider failure, and a healthy later turn."""
    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234")
    try:
        agent = client.first_agent_id()
        client.update_agent_config(
            agent,
            tool_allowlist=[
                *client.get_agent_config(agent)["tool_allowlist"],
                "subagent",
            ],
        )
        chat = client.create_direct_conversation(agent)
        for prompt, reply in [
            ("FOREGROUND_SUCCESS", "CHILD-OUTPUT-RECEIVED"),
            ("FOREGROUND_FAILURE", "FAILURE-OBSERVED"),
            ("AFTER_FAILURE", "STILL-RESPONSIVE"),
        ]:
            client.send_message(chat, prompt)
            client.wait_for_agent_reply_with(chat, reply, timeout=60)
        records = _load_records(Path(stub_llm_stack.record_path))
        results = {
            block["tool_use_id"]: block
            for row in records
            for message in row["request"]["messages"]
            if isinstance(message["content"], list)
            for block in message["content"]
            if block.get("type") == "tool_result"
        }
        assert "CHILD-OUTPUT" in json.dumps(results["spawn-success"])
        assert not results["spawn-success"].get("is_error")
        assert results["spawn-failure"].get("is_error") is True
        # A separate child request must actually reach the provider; the parent
        # reply alone could be fabricated without executing a subagent at all.
        child_sessions = {
            row["session"]
            for row in records
            if any(
                "CHILD_SUCCESS" in str(message["content"])
                or "CHILD_FAILURE" in str(message["content"])
                for message in row["request"]["messages"]
                if message["role"] == "user"
            )
            and row["session"] != row["root"]
        }
        assert len(child_sessions) == 2
    finally:
        client.close()
