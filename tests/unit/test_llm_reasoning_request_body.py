"""Packet-level reasoning rendering through registered provider clients."""

from __future__ import annotations

import json

import httpx

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.llm.model_registry import _reset_for_tests, init_model_registry
from agent.platform.llm.providers.anthropic.client import AnthropicClient
from agent.platform.llm.providers.openai_compat.client import OpenAICompatClient


async def test_anthropic_client_merges_static_body_then_renders_dynamic_effort() -> (
    None
):
    _reset_for_tests()
    init_model_registry(
        LLMConfigPayload(
            default_model="test:anthropic",
            providers=(
                LLMProviderPayload(
                    name="anthropic",
                    base_url="http://127.0.0.1:1",
                    models=(
                        LLMModelPayload(
                            name="test:anthropic",
                            extra_request_body={
                                "thinking": {"type": "enabled"},
                                "output_config": {
                                    "trace": "keep",
                                    "effort": "static",
                                },
                            },
                        ),
                    ),
                ),
            ),
        )
    )
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        body = (
            'data:{"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n'
            'data:{"type":"message_stop"}\n\n'
        )
        return httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:1",
        model="test:anthropic",
        transport=httpx.MockTransport(handler),
    )
    try:
        async for _ in client.generate(
            LLMGenerateRequest(
                session_id="session-a",
                model="test:anthropic",
                messages=(LLMMessage(role="user", content="hello"),),
                reasoning_effort="high",
            )
        ):
            pass
    finally:
        await client.close()

    assert captured["thinking"] == {"type": "enabled"}
    assert captured["output_config"] == {"trace": "keep", "effort": "high"}


async def test_openai_client_merges_static_body_then_renders_dynamic_effort() -> None:
    _reset_for_tests()
    init_model_registry(
        LLMConfigPayload(
            default_model="test:openai",
            providers=(
                LLMProviderPayload(
                    name="openai_compat",
                    base_url="http://127.0.0.1:1",
                    models=(
                        LLMModelPayload(
                            name="test:openai",
                            extra_request_body={
                                "thinking": {"type": "adaptive"},
                                "reasoning_effort": "static",
                            },
                        ),
                    ),
                ),
            ),
        )
    )
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        body = (
            'data: {"choices":[{"delta":{"content":"ok"},'
            '"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:1",
        model="test:openai",
        transport=httpx.MockTransport(handler),
    )
    try:
        async for _ in client.generate(
            LLMGenerateRequest(
                session_id="session-o",
                model="test:openai",
                messages=(LLMMessage(role="user", content="hello"),),
                reasoning_effort="max",
            )
        ):
            pass
    finally:
        await client.close()

    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["reasoning_effort"] == "max"
