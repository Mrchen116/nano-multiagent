from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import httpx
import pytest

from nano_multiagent.core.types import ToolSpec
from nano_multiagent.core.errors import ModelError
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from nano_multiagent.llm.protocols.anthropic import AnthropicClient, AnthropicMapper
from nano_multiagent.llm.protocols.openai_compat import OpenAICompatClient, OpenAICompatMapper
from nano_multiagent.llm.protocols.anthropic.client import _should_trust_env as anthropic_should_trust_env
from nano_multiagent.llm.protocols.openai_compat.client import _should_trust_env as openai_should_trust_env


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
                model="codexOAuth:gpt-5.2-codex",
                api_key="test-openai-key",
                transport=transport,
            ),
            expected_path="/v1/chat/completions",
            request_assertion=_assert_openai_request,
            sample_response={
                "model": "codexOAuth:gpt-5.2-codex",
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
            model="claude-3-5-sonnet-20241022",
            api_key="test-anthropic-key",
            transport=transport,
        ),
        expected_path="/v1/messages",
        request_assertion=_assert_anthropic_request,
        sample_response={
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "pong"}],
        },
        response_assertion=_assert_anthropic_response,
    )


def _build_request(*, stream: bool = False) -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_provider_contract",
        model="codexOAuth:gpt-5.2-codex",
        messages=(
            LLMMessage(role="system", content="You are concise."),
            LLMMessage(role="user", content="reply with one word: pong"),
        ),
        stream=stream,
        temperature=0.2,
        max_tokens=64,
    )


def _build_tool_request() -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_provider_contract",
        model="codexOAuth:gpt-5.2-codex",
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
        stream=False,
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


def test_provider_mapper_tool_response_contract(provider_case: ProviderContractCase) -> None:
    if provider_case.provider == "openai_compat":
        payload = {
            "model": "codexOAuth:gpt-5.2-codex",
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
            "model": "claude-3-5-sonnet-20241022",
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


def test_provider_client_contract_non_stream_and_headers(provider_case: ProviderContractCase) -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["headers"] = dict(request.headers)
        observed["body"] = json.loads(request.read().decode("utf-8"))
        return httpx.Response(200, json=provider_case.sample_response)

    client = provider_case.make_client(httpx.MockTransport(handler))
    result = client.generate(_build_request())

    assert observed["path"] == provider_case.expected_path
    assert observed["headers"]["x-session-id"] == "sess_provider_contract"
    provider_case.request_assertion(observed["body"])
    provider_case.response_assertion(result)

    if provider_case.provider == "openai_compat":
        assert observed["headers"]["authorization"] == "Bearer test-openai-key"
    else:
        assert observed["headers"]["x-api-key"] == "test-anthropic-key"
        assert observed["headers"]["anthropic-version"] == "2023-06-01"


def test_provider_client_contract_streaming_not_supported(provider_case: ProviderContractCase) -> None:
    client = provider_case.make_client(httpx.MockTransport(lambda _: httpx.Response(500)))

    with pytest.raises(ModelError, match="streaming generation is not implemented yet"):
        client.generate(_build_request(stream=True))


def test_provider_clients_bypass_env_proxy_for_local_base_url() -> None:
    assert openai_should_trust_env("http://127.0.0.1:4000") is False
    assert anthropic_should_trust_env("http://localhost:4000") is False


def test_provider_clients_keep_env_proxy_for_remote_base_url() -> None:
    assert openai_should_trust_env("https://api.example.com") is True
    assert anthropic_should_trust_env("https://api.example.com") is True


def _assert_openai_request(payload: dict[str, Any]) -> None:
    assert payload["model"] == "codexOAuth:gpt-5.2-codex"
    assert payload["stream"] is False
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 64
    assert payload["messages"][0] == {"role": "system", "content": "You are concise."}
    assert payload["messages"][1] == {"role": "user", "content": "reply with one word: pong"}


def _assert_anthropic_request(payload: dict[str, Any]) -> None:
    assert payload["model"] == "codexOAuth:gpt-5.2-codex"
    assert payload["stream"] is False
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


def _assert_anthropic_response(response: LLMGenerateResponse) -> None:
    assert response.message.role == "assistant"
    assert response.message.content == "pong"
    assert response.finish_reason == "end_turn"
