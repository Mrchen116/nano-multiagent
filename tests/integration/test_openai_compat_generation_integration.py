from typing import Any

import httpx

from nano_multiagent.core.llm.factory import LLMFactoryConfig, create_llm_client
from nano_multiagent.core.llm.interfaces import LLMGenerateRequest, LLMMessage


def test_factory_openai_compat_generation_wires_translator_and_header() -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["headers"] = dict(request.headers)
        observed["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "object": "chat.completion",
                "model": "codexOAuth:gpt-5.2-codex",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "pong"},
                    }
                ],
            },
        )

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="openai_compat",
            model="codexOAuth:gpt-5.2-codex",
            base_url="http://127.0.0.1:4000",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = client.generate(
        LLMGenerateRequest(
            session_id="sess_integration",
            model="codexOAuth:gpt-5.2-codex",
            messages=(LLMMessage(role="user", content="reply with one word: pong"),),
        )
    )

    assert result.message.content == "pong"
    assert observed["path"] == "/v1/chat/completions"
    assert observed["headers"]["x-session-id"] == "sess_integration"
    assert '"model":"codexOAuth:gpt-5.2-codex"' in observed["body"]
