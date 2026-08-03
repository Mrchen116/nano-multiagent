from __future__ import annotations

import pytest

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.platform.llm.providers.anthropic.mapper import AnthropicMapper


def _request(
    *, messages: tuple[LLMMessage, ...], max_tokens: int | None = None
) -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess_anthropic_mapper",
        model="kimiCoding:K2.6",
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
    assert payload["max_tokens"] == 32768
    assert payload["messages"] == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
        }
    ]


def test_map_generate_request_merges_extra_body() -> None:
    mapper = AnthropicMapper()

    payload = mapper.map_generate_request(
        LLMGenerateRequest(
            session_id="sess_anthropic_mapper",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="hello"),),
            extra_body={"thinking": {"type": "adaptive"}},
        )
    )

    assert payload["thinking"] == {"type": "adaptive"}


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
            "model": "kimiCoding:K2.6",
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
            "model": "kimiCoding:K2.6",
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
        mapper.map_generate_response({"model": "kimiCoding:K2.6"})


def test_map_message_assistant_tool_call_round_trips_thinking_block() -> None:
    """带 reasoning_content + reasoning_signature 的 assistant tool-call 消息出站时必须回写真实 thinking 块。

    kimi K2.6 在 thinking 开启时要求历史里每条带 tool_call 的 assistant 消息携带它当时
    的 reasoning_content（bugfix-373），且 signature 必须是真实值（bugfix-375）：
    空签名导致上游每轮重放同一段 reasoning 死循环。
    """
    from agent.core.llm.interfaces import LLMToolCall

    mapper = AnthropicMapper()
    real_sig = "EqoBCkgIARgCIkD_real_mapper_sig_abc"

    payload = mapper.map_generate_request(
        _request(
            messages=(
                LLMMessage(role="user", content="run pwd"),
                LLMMessage(
                    role="assistant",
                    content="",
                    reasoning_content="我需要使用 bash 工具",
                    reasoning_signature=real_sig,
                    tool_calls=(
                        LLMToolCall(
                            call_id="tool_1", name="bash", arguments={"command": "pwd"}
                        ),
                    ),
                ),
                LLMMessage(role="tool", content="/repo", tool_call_id="tool_1"),
            ),
        )
    )

    assistant_msg = payload["messages"][1]
    blocks = assistant_msg["content"]
    assert blocks[0] == {
        "type": "thinking",
        "thinking": "我需要使用 bash 工具",
        "signature": real_sig,
    }
    assert any(b.get("type") == "tool_use" and b.get("id") == "tool_1" for b in blocks)


def test_map_message_assistant_tool_call_uses_empty_signature_when_none() -> None:
    """reasoning_signature 为 None 时 thinking 块 signature 用空串（兼容 bugfix-373 的路径）。"""
    from agent.core.llm.interfaces import LLMToolCall

    mapper = AnthropicMapper()

    payload = mapper.map_generate_request(
        _request(
            messages=(
                LLMMessage(role="user", content="run pwd"),
                LLMMessage(
                    role="assistant",
                    content="",
                    reasoning_content="我需要使用 bash 工具",
                    reasoning_signature=None,
                    tool_calls=(
                        LLMToolCall(
                            call_id="tool_1", name="bash", arguments={"command": "pwd"}
                        ),
                    ),
                ),
                LLMMessage(role="tool", content="/repo", tool_call_id="tool_1"),
            ),
        )
    )

    assistant_msg = payload["messages"][1]
    blocks = assistant_msg["content"]
    assert blocks[0] == {
        "type": "thinking",
        "thinking": "我需要使用 bash 工具",
        "signature": "",
    }


def test_map_message_assistant_without_reasoning_omits_thinking_block() -> None:
    mapper = AnthropicMapper()

    payload = mapper.map_generate_request(
        _request(
            messages=(
                LLMMessage(role="user", content="hi"),
                LLMMessage(role="assistant", content="hello"),
            ),
        )
    )

    assistant_msg = payload["messages"][1]
    assert all(b.get("type") != "thinking" for b in assistant_msg["content"])


def test_map_generate_request_merges_consecutive_parallel_tool_results() -> None:
    """并行 tool 的多条 role=tool 必须合成一条 user，content 含全部 tool_result。

    Anthropic Messages 要求：含多个 tool_use 的 assistant 之后，紧跟的那一条 user
    必须立刻带齐对应 tool_result；拆成多条 user 会 400（bugfix-490 / #226）。
    内部 transcript 仍可拆条；合并只发生在 Anthropic 上线映射。
    """
    from agent.core.llm.interfaces import LLMToolCall

    mapper = AnthropicMapper()

    payload = mapper.map_generate_request(
        _request(
            messages=(
                LLMMessage(role="user", content="read both"),
                LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_A", name="read", arguments={"path": "/a"}
                        ),
                        LLMToolCall(
                            call_id="call_B", name="read", arguments={"path": "/b"}
                        ),
                    ),
                ),
                LLMMessage(role="tool", content="content-a", tool_call_id="call_A"),
                LLMMessage(role="tool", content="content-b", tool_call_id="call_B"),
                LLMMessage(role="user", content="thanks"),
            ),
        )
    )

    wire = payload["messages"]
    # user → assistant(tool_use×2) → user(tool_result×2) → user(thanks)
    assert len(wire) == 4
    assert wire[1]["role"] == "assistant"
    assert [b["id"] for b in wire[1]["content"] if b["type"] == "tool_use"] == [
        "call_A",
        "call_B",
    ]
    assert wire[2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "call_A",
                "content": [{"type": "text", "text": "content-a"}],
            },
            {
                "type": "tool_result",
                "tool_use_id": "call_B",
                "content": [{"type": "text", "text": "content-b"}],
            },
        ],
    }
    assert wire[3] == {
        "role": "user",
        "content": [{"type": "text", "text": "thanks"}],
    }


def test_map_generate_response_surfaces_cache_hit_fields() -> None:
    """feat-439-M1: Anthropic 缓存读取量单独暴露为 cache_read_tokens；
    cache_total_input_tokens 跨家归一为本次总 input(== prompt_tokens)。
    prompt_tokens 不得改动(驱动「已用上下文」)。"""
    mapper = AnthropicMapper()

    response = mapper.map_generate_response(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "kimiCoding:K2.6",
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
    # prompt_tokens 一字不改：input + cache_creation + cache_read = 107
    assert response.usage.prompt_tokens == 107
    assert response.usage.cache_read_tokens == 2
    # 归一：逐请求 cache_total_input_tokens == prompt_tokens
    assert response.usage.cache_total_input_tokens == 107


def test_map_generate_response_cache_fields_default_zero_without_cache() -> None:
    """无缓存命中时 cache_read_tokens=0，cache_total_input_tokens 仍== prompt_tokens。"""
    mapper = AnthropicMapper()

    response = mapper.map_generate_response(
        {
            "id": "msg_2",
            "type": "message",
            "role": "assistant",
            "model": "kimiCoding:K2.6",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 50, "output_tokens": 10},
            "content": [{"type": "text", "text": "ok"}],
        }
    )

    assert response.usage is not None
    assert response.usage.prompt_tokens == 50
    assert response.usage.cache_read_tokens == 0
    assert response.usage.cache_total_input_tokens == 50
