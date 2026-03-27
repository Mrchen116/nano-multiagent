from __future__ import annotations

import pytest

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.platform.llm.providers.anthropic.mapper import AnthropicMapper


def _request(*, messages: tuple[LLMMessage, ...], max_tokens: int | None = None) -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_anthropic_mapper",
        model="moonshotAnthropic:kimi-k2.5",
        messages=messages,
        temperature=0.2,
        max_tokens=max_tokens,
    )


def test_map_generate_request_joins_system_and_applies_default_max_tokens() -> None:
    mapper = AnthropicMapper()

    payload = mapper.map_generate_request(
        _request(
            messages=(
                LLMMessage(role="system", content="S1"),
                LLMMessage(role="system", content="S2"),
                LLMMessage(role="user", content="hello"),
            ),
            max_tokens=None,
        )
    )

    assert payload["system"] == "S1\n\nS2"
    assert payload["max_tokens"] == 1024
    assert payload["messages"] == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
        }
    ]


def test_map_generate_request_requires_non_system_messages() -> None:
    mapper = AnthropicMapper()

    with pytest.raises(ModelError, match="requires at least one non-system message"):
        mapper.map_generate_request(
            _request(
                messages=(
                    LLMMessage(role="system", content="S1"),
                    LLMMessage(role="system", content="S2"),
                )
            )
        )


def test_map_generate_response_coerces_non_string_text_chunks() -> None:
    mapper = AnthropicMapper()

    response = mapper.map_generate_response(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "moonshotAnthropic:kimi-k2.5",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": 123}],
        }
    )

    assert response.message.content == "123"


def test_map_generate_response_normalizes_usage_to_canonical_fields() -> None:
    mapper = AnthropicMapper()

    response = mapper.map_generate_response(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "moonshotAnthropic:kimi-k2.5",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 30,
                "cache_creation_input_tokens": 5,
                "cache_read_input_tokens": 2,
            },
            "content": [{"type": "text", "text": "ok"}],
        }
    )

    assert response.usage is not None
    assert response.usage.prompt_tokens == 107
    assert response.usage.completion_tokens == 30
    assert response.usage.total_tokens == 137


def test_map_generate_response_requires_content_blocks() -> None:
    mapper = AnthropicMapper()

    with pytest.raises(ModelError, match="missing content blocks"):
        mapper.map_generate_response({"model": "moonshotAnthropic:kimi-k2.5"})
