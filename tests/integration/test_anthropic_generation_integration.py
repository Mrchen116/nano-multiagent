import asyncio
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
        # AnthropicClient._stream_response expects Anthropic SSE events.
        sse_body = (
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"pong"}}\n\n'
            'data: {"type":"content_block_stop","index":0}\n\n'
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}\n\n'
            'data: {"type":"message_stop"}\n\n'
        )
        return httpx.Response(
            200,
            content=sse_body.encode(),
            headers={"content-type": "text/event-stream"},
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

    # generate() returns AsyncIterator[LLMMessage]; collect all messages.
    async def _collect():
        messages = []
        async for msg in client.generate(
            LLMGenerateRequest(
                session_id="sess_integration_anthropic",
                model="kimiCoding:K2.6",
                messages=(
                    LLMMessage(role="system", content="You are concise."),
                    LLMMessage(role="user", content="reply with one word: pong"),
                ),
            )
        ):
            messages.append(msg)
        return messages

    messages = asyncio.run(_collect())
    # First message carries assistant content; last carries finish_reason metadata.
    content_msgs = [m for m in messages if m.content]
    assert content_msgs, "expected at least one content message"
    assert content_msgs[0].content == "pong"

    body = json.loads(observed["body"])
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
