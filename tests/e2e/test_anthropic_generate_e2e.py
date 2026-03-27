from __future__ import annotations

import os

import httpx
import pytest

from agent.core.llm.factory import LLMFactoryConfig, create_llm_client
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage


def _llm_proxy_available() -> bool:
    try:
        response = httpx.get("http://127.0.0.1:4000/health", timeout=1.5)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


@pytest.mark.e2e
def test_anthropic_non_stream_generate_against_local_proxy() -> None:
    if os.getenv("NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E") != "1":
        pytest.skip("set NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 to run live proxy e2e tests")

    if not _llm_proxy_available():
        pytest.skip("LLM_PROXY is unavailable on http://127.0.0.1:4000")

    with create_llm_client(
        config=LLMFactoryConfig(
            provider="anthropic",
            model="codex_oauth:gpt-5.4",
            base_url="http://127.0.0.1:4000",
            api_key=None,
        )
    ) as client:
        result = client.generate(
            LLMGenerateRequest(
                session_id="sess_e2e_anthropic",
                model="",
                messages=(
                    LLMMessage(role="user", content="reply with one word: pong"),
                ),
            )
        )

    assert result.message.role == "assistant"
    assert "pong" in result.message.content.lower()
