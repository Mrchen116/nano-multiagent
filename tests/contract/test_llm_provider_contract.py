from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Callable

import httpx
import pytest

from agent.core.types import ToolSpec
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from agent.platform.llm.providers.anthropic import AnthropicClient, AnthropicMapper
from agent.platform.llm.providers.openai_compat import OpenAICompatClient, OpenAICompatMapper
from agent.platform.llm.providers.anthropic.client import _should_trust_env as anthropic_should_trust_env
from agent.platform.llm.providers.openai_compat.client import _should_trust_env as openai_should_trust_env


@dataclass(frozen=True, slots=True)
class ProviderContractCase:
    provider: str
    mapper: Any
    make_client: Callable[[httpx.BaseTransport], Any]
    expected_path: str
    request_assertion: Callable[[dict[str, Any]], None]
    sample_response: dict[str, Any]
    response_assertion: Callable[[LLMGenerateResponse], None]


@pytest.fixture(params=["openai_compat", "anthropic"])
def provider_case(request: pytest.FixtureRequest) -> ProviderContractCase:
    if request.param == "openai_compat":
        return ProviderContractCase(
            provider="openai_compat",
            mapper=OpenAICompatMapper(),
            make_client=lambda transport: OpenAICompatClient(
                base_url="http://127.0.0.1:4000",
                model="codex_oauth:gpt-5.4",
                api_key="test-openai-key",
                transport=transport,
            ),
            expected_path="/v1/chat/completions",
            request_assertion=_assert_openai_request,
            sample_response={
                "model": "codex_oauth:gpt-5.4",
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 4,
                    "total_tokens": 15,
                },
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "pong"},
                        "finish_reason": "stop",
                    }
                ],
            },
            response_assertion=_assert_openai_response,
        )
    return ProviderContractCase(
        provider="anthropic",
        mapper=AnthropicMapper(),
        make_client=lambda transport: AnthropicClient(
            base_url="http://127.0.0.1:4000",
            model="moonshotAnthropic:kimi-k2.5",
            api_key="test-anthropic-key",
            transport=transport,
        ),
        expected_path="/v1/messages",
        request_assertion=_assert_anthropic_request,
        sample_response={
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "moonshotAnthropic:kimi-k2.5",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 11,
                "output_tokens": 4,
            },
            "content": [{"type": "text", "text": "pong"}],
        },
        response_assertion=_assert_anthropic_response,
    )


async def _consume_generate(client, request):  # noqa: ANN001, ANN201
    """Consume async generator and return collected messages."""
    messages = []
    async for msg in client.generate(request):
        messages.append(msg)
    return messages


def _build_request() -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_provider_contract",
        model="codex_oauth:gpt-5.4",
        messages=(
            LLMMessage(role="system", content="You are concise."),
            LLMMessage(role="user", content="reply with one word: pong"),
        ),
        temperature=0.2,
        max_tokens=64,
    )


def _build_tool_request() -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_provider_contract",
        model="codex_oauth:gpt-5.4",
        messages=(
            LLMMessage(role="system", content="You are concise."),
            LLMMessage(role="user", content="read README"),
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=(LLMToolCall(call_id="call_1", name="read", arguments={"path": "README.md"}),),
            ),
            LLMMessage(role="tool", content="file content", tool_call_id="call_1"),
        ),
        temperature=0.2,
        max_tokens=64,
        tools=(
            ToolSpec(
                name="read",
                description="Read a file",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),
        ),
    )


def _build_tool_image_request() -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_provider_contract",
        model="codex_oauth:gpt-5.4",
        messages=(
            LLMMessage(role="system", content="You are concise."),
            LLMMessage(role="user", content="what is in the image?"),
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=(LLMToolCall(call_id="call_1", name="read", arguments={"path": "pixel.png"}),),
            ),
            LLMMessage(
                role="tool",
                tool_call_id="call_1",
                content=json.dumps(
                    {
                        "call_id": "call_1",
                        "name": "read",
                        "output": {
                            "content": [
                                {"type": "text", "text": "Image: pixel.png (image/png, 68 bytes)"},
                                {
                                    "type": "image",
                                    "mime_type": "image/png",
                                    "image_url": "data:image/png;base64,abcd",
                                },
                            ]
                        },
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
            ),
        ),
        temperature=0.2,
        max_tokens=64,
        tools=(
            ToolSpec(
                name="read",
                description="Read a file",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),
        ),
    )


def test_provider_mapper_request_contract(provider_case: ProviderContractCase) -> None:
    payload = provider_case.mapper.map_generate_request(_build_request())

    assert isinstance(payload, dict)
    provider_case.request_assertion(dict(payload))


def test_provider_mapper_response_contract(provider_case: ProviderContractCase) -> None:
    response = provider_case.mapper.map_generate_response(provider_case.sample_response)

    provider_case.response_assertion(response)


def test_provider_mapper_tool_request_contract(provider_case: ProviderContractCase) -> None:
    payload = provider_case.mapper.map_generate_request(_build_tool_request())

    assert isinstance(payload, dict)
    if provider_case.provider == "openai_compat":
        assert payload["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ]
        assert payload["tool_choice"] == "auto"
        assert payload["messages"][2] == {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "read",
                        "arguments": "{\"path\":\"README.md\"}",
                    },
                }
            ],
        }
        assert payload["messages"][3] == {
            "role": "tool",
            "content": "file content",
            "tool_call_id": "call_1",
        }
    else:
        assert payload["tools"] == [
            {
                "name": "read",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            }
        ]
        assert payload["messages"][1] == {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "read",
                    "input": {"path": "README.md"},
                }
            ],
        }
        assert payload["messages"][2] == {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": [{"type": "text", "text": "file content"}],
                }
            ],
        }


def test_provider_mapper_tool_request_preserves_image_parts(provider_case: ProviderContractCase) -> None:
    payload = provider_case.mapper.map_generate_request(_build_tool_image_request())

    if provider_case.provider == "openai_compat":
        tool_message = payload["messages"][3]
        assert tool_message == {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": [
                {"type": "text", "text": "Image: pixel.png (image/png, 68 bytes)"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abcd"}},
            ],
        }
    else:
        tool_message = payload["messages"][2]
        assert tool_message["role"] == "user"
        tool_result = tool_message["content"][0]
        assert tool_result["type"] == "tool_result"
        assert tool_result["tool_use_id"] == "call_1"
        blocks = tool_result["content"]
        assert blocks[0] == {"type": "text", "text": "Image: pixel.png (image/png, 68 bytes)"}
        assert blocks[1] == {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "abcd",
            },
        }


def test_provider_mapper_tool_response_contract(provider_case: ProviderContractCase) -> None:
    if provider_case.provider == "openai_compat":
        payload = {
            "model": "codex_oauth:gpt-5.4",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "read",
                                    "arguments": "{\"path\":\"README.md\"}",
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
    else:
        payload = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "moonshotAnthropic:kimi-k2.5",
            "stop_reason": "tool_use",
            "content": [
                {"type": "text", "text": "checking"},
                {"type": "tool_use", "id": "call_1", "name": "read", "input": {"path": "README.md"}},
            ],
        }

    response = provider_case.mapper.map_generate_response(payload)

    assert response.message.role == "assistant"
    assert response.message.tool_calls == (
        LLMToolCall(call_id="call_1", name="read", arguments={"path": "README.md"}),
    )
    if provider_case.provider == "openai_compat":
        assert response.message.content == ""
        assert response.finish_reason == "tool_calls"
    else:
        assert response.message.content == "checking"
        assert response.finish_reason == "tool_use"


async def test_provider_client_contract_non_stream_and_headers(provider_case: ProviderContractCase) -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["headers"] = dict(request.headers)
        observed["body"] = json.loads(request.read().decode("utf-8"))
        return httpx.Response(200, json=provider_case.sample_response)

    client = provider_case.make_client(httpx.MockTransport(handler))
    # generate() returns an async iterator; iterate to trigger the HTTP request
    try:
        async for _ in client.generate(_build_request()):
            pass
    except Exception:
        pass  # Mock response is not valid SSE; we only care about the request

    assert observed["path"] == provider_case.expected_path
    assert observed["headers"]["x-session-id"] == "sess_provider_contract"
    provider_case.request_assertion(observed["body"])

    if provider_case.provider == "openai_compat":
        assert observed["headers"]["authorization"] == "Bearer test-openai-key"
    else:
        assert observed["headers"]["x-api-key"] == "test-anthropic-key"
        assert observed["headers"]["anthropic-version"] == "2023-06-01"


async def test_provider_client_contract_streaming_supported(provider_case: ProviderContractCase) -> None:
    """Streaming is now the default; clients return AsyncIterator[LLMMessage]."""
    client = provider_case.make_client(httpx.MockTransport(lambda _: httpx.Response(500)))

    # generate() returns an async iterator, not a response directly
    result = client.generate(_build_request())
    assert hasattr(result, "__aiter__")


def test_provider_clients_bypass_env_proxy_for_local_base_url() -> None:
    assert openai_should_trust_env("http://127.0.0.1:4000") is False
    assert anthropic_should_trust_env("http://localhost:4000") is False


def test_provider_clients_keep_env_proxy_for_remote_base_url() -> None:
    assert openai_should_trust_env("https://api.example.com") is True
    assert anthropic_should_trust_env("https://api.example.com") is True


def _assert_openai_request(payload: dict[str, Any]) -> None:
    assert payload["model"] == "codex_oauth:gpt-5.4"
    assert payload["stream"] is True
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 64
    assert payload["messages"][0] == {"role": "system", "content": "You are concise."}
    assert payload["messages"][1] == {"role": "user", "content": "reply with one word: pong"}


def _assert_anthropic_request(payload: dict[str, Any]) -> None:
    assert payload["model"] == "codex_oauth:gpt-5.4"
    assert payload["stream"] is True
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 64
    assert payload["system"] == "You are concise."
    assert payload["messages"] == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "reply with one word: pong"}],
        }
    ]


def _assert_openai_response(response: LLMGenerateResponse) -> None:
    assert response.message.role == "assistant"
    assert response.message.content == "pong"
    assert response.finish_reason == "stop"
    assert response.usage is not None
    assert response.usage.prompt_tokens == 11
    assert response.usage.completion_tokens == 4
    assert response.usage.total_tokens == 15


def _assert_anthropic_response(response: LLMGenerateResponse) -> None:
    assert response.message.role == "assistant"
    assert response.message.content == "pong"
    assert response.finish_reason == "end_turn"
    assert response.usage is not None
    assert response.usage.prompt_tokens == 11
    assert response.usage.completion_tokens == 4
    assert response.usage.total_tokens == 15
