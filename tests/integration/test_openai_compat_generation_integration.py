import asyncio
from typing import Any

import httpx

from agent.core.llm.factory import LLMFactoryConfig, create_llm_client
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage


def test_factory_openai_compat_generation_wires_translator_and_header() -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["headers"] = dict(request.headers)
        observed["body"] = request.read().decode("utf-8")
        # OpenAICompatClient._stream_response expects SSE-formatted lines.
        sse_body = (
            'data: {"id":"chatcmpl_test","object":"chat.completion.chunk","model":"codex_oauth:gpt-5.5",'
            '"choices":[{"index":0,"delta":{"role":"assistant","content":"pong"},"finish_reason":null}]}\n\n'
            'data: {"id":"chatcmpl_test","object":"chat.completion.chunk","model":"codex_oauth:gpt-5.5",'
            '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            content=sse_body.encode(),
            headers={"content-type": "text/event-stream"},
        )

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        transport=httpx.MockTransport(handler),
    )

    # generate() now returns AsyncIterator[LLMMessage]; collect all messages.
    async def _collect():
        messages = []
        async for msg in client.generate(
            LLMGenerateRequest(
                session_id="sess_integration",
                model="codex_oauth:gpt-5.5",
                messages=(LLMMessage(role="user", content="reply with one word: pong"),),
            )
        ):
            messages.append(msg)
        return messages

    messages = asyncio.run(_collect())
    # First message carries the assistant content; last may carry finish_reason metadata.
    content_msgs = [m for m in messages if m.content]
    assert content_msgs, "expected at least one content message"
    assert content_msgs[0].content == "pong"
    assert observed["path"] == "/v1/chat/completions"
    assert observed["headers"]["x-session-id"] == "sess_integration"
    assert '"model":"codex_oauth:gpt-5.5"' in observed["body"]
