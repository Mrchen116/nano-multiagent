"""Provider accounting reaches public chat bubbles and owner-scoped usage metrics."""

from __future__ import annotations

import httpx
import pytest

from ._im_client import IMClient
from ._im_polling import poll_until
from .test_agent_config_context_continuity_critical_path import (
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
def test_native_token_usage_reaches_bubble_and_metrics(
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

            def metrics() -> list[dict]:
                response = http.get(
                    "/im/v1/metrics/usage", params={"agent_id": agent_id}
                )
                response.raise_for_status()
                return response.json()

            rows = poll_until(
                metrics,
                lambda values: bool(values),
                timeout=30,
                interval=0.2,
                desc="native usage metrics",
            )
            assert rows[0]["prompt_tokens"] == 31_001
            assert rows[0]["completion_tokens"] == 1
            assert rows[0]["total_tokens"] == 31_002
    finally:
        client.close()
