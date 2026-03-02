from __future__ import annotations

import httpx
import pytest

from nano_multiagent.llm.factory import LLMFactoryConfig, create_llm_client
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMMessage


def _llm_proxy_available() -> bool:
    try:
        response = httpx.get("http://127.0.0.1:4000/health", timeout=1.5)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


@pytest.mark.e2e
def test_anthropic_non_stream_generate_against_local_proxy() -> None:
    if not _llm_proxy_available():
        pytest.skip("LLM_PROXY is unavailable on http://127.0.0.1:4000")

    with create_llm_client(
        config=LLMFactoryConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
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
