"""OpenAICompatMapper 单元测试，重点覆盖 reasoning_content round-trip。"""

from __future__ import annotations

import json

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.platform.llm.providers.openai_compat.mapper import OpenAICompatMapper


def _request(messages: tuple[LLMMessage, ...]) -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_mapper_test",
        model="kimi-k2",
        messages=messages,
    )


def test_map_message_assistant_with_tool_calls_and_reasoning_content() -> None:
    """开 thinking 时 assistant+tool_calls 消息出站必须携带 reasoning_content。

    kimi K2.6 要求历史里每条带 tool_call 的 assistant 消息都必须有 reasoning_content，
    否则请求被拒。
    """
    mapper = OpenAICompatMapper()
    thinking_text = "I need to run the command step by step."

    payload = mapper.map_generate_request(
        _request(
            messages=(
                LLMMessage(role="system", content="you are helpful"),
                LLMMessage(role="user", content="run pwd"),
                LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_xyz",
                            name="bash",
                            arguments={"command": "pwd"},
                        ),
                    ),
                    reasoning_content=thinking_text,
                ),
                LLMMessage(
                    role="tool",
                    content='{"call_id":"call_xyz","name":"bash","output":{"stdout":"/home/user"}}',
                    tool_call_id="call_xyz",
                ),
            )
        )
    )

    messages = payload["messages"]
    # [system, user, assistant, tool]
    assert len(messages) == 4
    assistant_msg = messages[2]
    assert assistant_msg["role"] == "assistant"
    assert "tool_calls" in assistant_msg
    # reasoning_content 必须出现在出站 assistant 消息里
    assert "reasoning_content" in assistant_msg, (
        "开 thinking 的 assistant+tool_calls 消息出站时必须携带 reasoning_content"
    )
    assert assistant_msg["reasoning_content"] == thinking_text


def test_map_message_assistant_without_reasoning_content_omits_field() -> None:
    """不带 thinking 的 assistant 消息出站时不应多余地加 reasoning_content 字段。"""
    mapper = OpenAICompatMapper()

    payload = mapper.map_generate_request(
        _request(
            messages=(
                LLMMessage(role="user", content="hi"),
                LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_abc",
                            name="echo",
                            arguments={"text": "hello"},
                        ),
                    ),
                    reasoning_content=None,
                ),
            )
        )
    )

    messages = payload["messages"]
    assistant_msg = messages[1]
    assert assistant_msg["role"] == "assistant"
    assert "reasoning_content" not in assistant_msg


def test_map_generate_response_reads_cached_tokens() -> None:
    """feat-439-M1: OpenAI prompt_tokens_details.cached_tokens 读出为
    cache_read_tokens；OpenAI prompt_tokens 本就含 cached，故
    cache_total_input_tokens == prompt_tokens，且 prompt_tokens 不变。"""
    mapper = OpenAICompatMapper()

    response = mapper.map_generate_response(
        {
            "id": "chatcmpl-1",
            "model": "kimi-k2",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hi"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "prompt_tokens_details": {"cached_tokens": 80},
            },
        }
    )

    assert response.usage is not None
    assert response.usage.prompt_tokens == 120
    assert response.usage.cache_read_tokens == 80
    assert response.usage.cache_total_input_tokens == 120


def test_map_generate_response_cache_zero_without_details() -> None:
    """无 prompt_tokens_details 时 cache_read_tokens=0，分母仍== prompt_tokens。"""
    mapper = OpenAICompatMapper()

    response = mapper.map_generate_response(
        {
            "id": "chatcmpl-2",
            "model": "kimi-k2",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hi"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 40, "completion_tokens": 5, "total_tokens": 45},
        }
    )

    assert response.usage is not None
    assert response.usage.prompt_tokens == 40
    assert response.usage.cache_read_tokens == 0
    assert response.usage.cache_total_input_tokens == 40
