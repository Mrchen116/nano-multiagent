from __future__ import annotations

import json
from typing import Any

import httpx

from agent.core.llm.factory import LLMFactoryConfig, create_llm_client
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage


def test_factory_anthropic_generation_wires_translator_and_header() -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["headers"] = dict(request.headers)
        observed["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "kimiCoding:K2.6",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "pong"}],
            },
        )

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="anthropic",
            model="kimiCoding:K2.6",
            base_url="http://127.0.0.1:4000",
            api_key="test-anthropic-key",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = client.generate(
        LLMGenerateRequest(
            session_id="sess_integration_anthropic",
            model="kimiCoding:K2.6",
            messages=(
                LLMMessage(role="system", content="You are concise."),
                LLMMessage(role="user", content="reply with one word: pong"),
            ),
        )
    )

    body = json.loads(observed["body"])
    assert result.message.content == "pong"
    assert observed["path"] == "/v1/messages"
    assert observed["headers"]["x-session-id"] == "sess_integration_anthropic"
    assert observed["headers"]["x-api-key"] == "test-anthropic-key"
    assert observed["headers"]["anthropic-version"] == "2023-06-01"
    assert body["system"] == "You are concise."
    assert body["messages"] == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "reply with one word: pong"}],
        }
    ]
