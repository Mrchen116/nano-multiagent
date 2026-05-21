"""AnthropicClient streaming 单元测试，验证 thinking 块 reasoning_content round-trip。

kimi K2.6 走 anthropic provider（model_registry: provider="anthropic"）。thinking
模式下上游返回独立的 thinking 内容块，必须把它的文本挂到同一轮的 tool_use 消息上，
否则 loop 回传历史时丢失 reasoning_content，follow-up 请求被上游拒（bugfix-373）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.platform.llm.providers.anthropic.client import AnthropicClient


def _make_anthropic_sse(events: list[dict[str, Any]]) -> bytes:
    lines = []
    for event in events:
        lines.append(f"event:{event['type']}\n")
        lines.append(f"data:{json.dumps(event)}\n\n")
    return "".join(lines).encode()


async def _collect(client: AnthropicClient, request: LLMGenerateRequest) -> list[LLMMessage]:
    messages: list[LLMMessage] = []
    async for msg in client.generate(request):
        messages.append(msg)
    return messages


async def test_stream_response_carries_thinking_into_tool_call() -> None:
    thinking_text = "运行 `pwd && ls -la` 命令，我需要使用 bash 工具"
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": thinking_text}},
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {"type": "tool_use", "id": "tool_1", "name": "bash", "input": {}},
        },
        {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"command":"pwd && ls -la"}'}},
        {"type": "content_block_stop", "index": 1},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"input_tokens": 10, "output_tokens": 5}},
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect(
        client,
        LLMGenerateRequest(
            session_id="sess_anthropic_stream",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="请运行 pwd 和 ls -la"),),
        ),
    )

    tool_call_msg = next((m for m in messages if m.tool_calls), None)
    assert tool_call_msg is not None, "应该有 tool_call 消息"
    assert tool_call_msg.tool_calls[0].name == "bash"
    assert tool_call_msg.reasoning_content == thinking_text, (
        f"thinking 块未 round-trip 到 tool_call 消息: 实际 {tool_call_msg.reasoning_content!r}"
    )


async def test_stream_response_shares_thinking_across_parallel_tool_calls() -> None:
    """一个 assistant 轮里多个 tool_use 共享同一个 thinking 块时，每个都要带上 reasoning_content。

    loop 会把多 tool_use 的一轮拆成多条独立 assistant 消息，kimi K2.6 要求其中
    每一条都携带 reasoning_content，否则后续 tool_use 消息被上游拒（bugfix-373）。
    """
    thinking_text = "我需要并行运行两个命令"
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": thinking_text}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "tool_1", "name": "bash", "input": {}}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"command":"pwd"}'}},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "tool_2", "name": "bash", "input": {}}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": '{"command":"ls -la"}'}},
        {"type": "content_block_stop", "index": 2},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"input_tokens": 10, "output_tokens": 8}},
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect(
        client,
        LLMGenerateRequest(
            session_id="sess_anthropic_parallel",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="请运行 pwd 和 ls -la"),),
        ),
    )

    tool_call_msgs = [m for m in messages if m.tool_calls]
    assert len(tool_call_msgs) == 2, "应该有两条 tool_call 消息"
    for msg in tool_call_msgs:
        assert msg.reasoning_content == thinking_text, (
            f"tool_call {msg.tool_calls[0].name} 缺 reasoning_content: {msg.reasoning_content!r}"
        )


async def test_stream_response_omits_reasoning_when_no_thinking_block() -> None:
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 3, "output_tokens": 1}},
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect(
        client,
        LLMGenerateRequest(
            session_id="sess_anthropic_no_think",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="hi"),),
        ),
    )

    text_msg = next((m for m in messages if m.content), None)
    assert text_msg is not None
    assert text_msg.reasoning_content is None
