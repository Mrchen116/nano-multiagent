"""Provider accounting reaches public chat bubbles and persisted Global Work records."""

from __future__ import annotations

import httpx
import pytest

from ._im_client import IMClient
from ._im_polling import poll_until
from ._recording import (
    StubLLMStack,
    stub_llm_stack,
)


@pytest.mark.e2e
@pytest.mark.parametrize(
    "stub_llm_stack",
    (
        {
            "message_start_usage": {
                "input_tokens": 30_001,
                "cache_read_input_tokens": 1_000,
            },
            "message_delta_usage": {"output_tokens": 1},
        },
    ),
    indirect=True,
)
def test_native_token_usage_reaches_bubble_and_work(
    stub_llm_stack: StubLLMStack,
) -> None:
    """Disjoint input, cached input and output retain their meaning through the complete stack."""
    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    try:
        agent_id = client.first_agent_id()
        conversation_id = client.create_direct_conversation(agent_id)
        client.send_message(conversation_id, "USAGE-PROBE")
        reply = client.wait_for_agent_reply_with(conversation_id, "ACK-1", timeout=90)
        assert reply["token_usage"]["context_used"] == 31_001
        assert reply["token_usage"]["output"] == 1
        assert reply["token_usage"]["cache_read_tokens"] == 1_000
        with httpx.Client(
            base_url=client.im_url,
            headers={"Authorization": f"Bearer {client.token}"},
            timeout=30,
        ) as http:
            # The retired cumulative API has no product consumer. Global Work
            # retains its independent native -> journal -> HTTP projection path.
            assert http.get("/im/v1/metrics/usage").status_code == 404
            agents = http.get("/im/v1/agents").json()
            global_id = next(
                agent["agent_id"]
                for agent in agents
                if client.get_agent_config(agent["agent_id"])["work_mode"] == "global"
            )
            global_chat = client.create_direct_conversation(global_id)
            client.send_message(global_chat, "WORK-USAGE-PROBE")

            def work() -> dict:
                response = http.get(f"/im/v1/agents/{global_id}/work")
                response.raise_for_status()
                return response.json()

            view = poll_until(
                work,
                lambda value: bool(value.get("latest_main_usage")),
                timeout=30,
                interval=0.2,
                desc="persisted Work token usage",
            )
            assert view["latest_main_usage"]["context_used"] == 31_001
            assert view["latest_main_usage"]["output"] == 1
            assert view["latest_main_usage"]["cache_read_tokens"] == 1_000
    finally:
        client.close()
