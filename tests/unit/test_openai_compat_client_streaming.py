"""OpenAICompatClient streaming 单元测试，验证 reasoning_content 解析。"""

from __future__ import annotations

import json
from typing import Any
from collections.abc import AsyncIterator

import httpx
import pytest

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.platform.llm.providers.openai_compat.client import OpenAICompatClient


def _make_sse_body(chunks: list[dict[str, Any]]) -> bytes:
    """构造 OpenAI SSE 格式的响应体。"""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


async def _collect_messages(client: OpenAICompatClient, request: LLMGenerateRequest) -> list[LLMMessage]:
    messages: list[LLMMessage] = []
    async for msg in client.generate(request):
        messages.append(msg)
    return messages


async def test_stream_response_parses_reasoning_content() -> None:
    """delta.reasoning_content 必须被解析到 LLMMessage.reasoning_content。

    kimi K2.6 在 thinking 模式下，streaming delta 里的 reasoning_content 字段
    需要被收集并挂到 LLMMessage，这样 loop 才能在历史里保留它并 round-trip 回传。
    """
    thinking_text = "Let me think about the command..."
    chunks = [
        # 第一个 chunk: reasoning_content（无 content）
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "model": "kimi-k2",
            "choices": [{"index": 0, "delta": {"role": "assistant", "reasoning_content": thinking_text}, "finish_reason": None}],
        },
        # 第二个 chunk: tool_call
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "model": "kimi-k2",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "id": "call_abc", "type": "function", "function": {"name": "bash", "arguments": '{"command":"pwd"}'}},
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        # finish chunk
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "model": "kimi-k2",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
        },
    ]

    body = _make_sse_body(chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "text/event-stream"},
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect_messages(
        client,
        LLMGenerateRequest(
            session_id="sess_stream_test",
            model="kimi-k2",
            messages=(LLMMessage(role="user", content="run pwd"),),
        ),
    )

    # 找到带 tool_calls 的 assistant 消息
    tool_call_msg = next((m for m in messages if m.tool_calls), None)
    assert tool_call_msg is not None, "应该有 tool_call 消息"
    assert tool_call_msg.tool_calls[0].name == "bash"
    # reasoning_content 必须被保留在 tool_call 消息里
    assert tool_call_msg.reasoning_content == thinking_text, (
        f"reasoning_content 丢失: 期望 {thinking_text!r}, 实际 {tool_call_msg.reasoning_content!r}"
    )
