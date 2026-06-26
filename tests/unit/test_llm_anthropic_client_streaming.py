"""AnthropicClient streaming 单元测试，验证 thinking 块 reasoning_content + signature round-trip。

kimi K2.6 走 anthropic provider（model_registry: provider="anthropic"）。thinking
模式下上游返回独立的 thinking 内容块（含 signature），必须把文本和真实 signature
都挂到同一轮的 tool_use 消息上，否则回传历史时：
- 丢失 reasoning_content → follow-up 请求被上游拒（bugfix-373）
- signature 为空 → 上游每轮重放同一段 reasoning，多轮死循环（bugfix-375）
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


async def _collect(
    client: AnthropicClient, request: LLMGenerateRequest
) -> list[LLMMessage]:
    messages: list[LLMMessage] = []
    async for msg in client.generate(request):
        messages.append(msg)
    return messages


async def test_stream_response_carries_thinking_into_tool_call() -> None:
    thinking_text = "运行 `pwd && ls -la` 命令，我需要使用 bash 工具"
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "thinking", "thinking": "", "signature": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": thinking_text},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "tool_use",
                "id": "tool_1",
                "name": "bash",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {
                "type": "input_json_delta",
                "partial_json": '{"command":"pwd && ls -la"}',
            },
        },
        {"type": "content_block_stop", "index": 1},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

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
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "thinking", "thinking": "", "signature": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": thinking_text},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "tool_use",
                "id": "tool_1",
                "name": "bash",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "input_json_delta", "partial_json": '{"command":"pwd"}'},
        },
        {"type": "content_block_stop", "index": 1},
        {
            "type": "content_block_start",
            "index": 2,
            "content_block": {
                "type": "tool_use",
                "id": "tool_2",
                "name": "bash",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 2,
            "delta": {
                "type": "input_json_delta",
                "partial_json": '{"command":"ls -la"}',
            },
        },
        {"type": "content_block_stop", "index": 2},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"input_tokens": 10, "output_tokens": 8},
        },
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

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
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "hi"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"input_tokens": 3, "output_tokens": 1},
        },
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

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
    assert text_msg.reasoning_signature is None


async def test_stream_response_carries_signature_into_tool_call() -> None:
    """thinking 块的 signature 必须通过 signature_delta 解析后 round-trip 到 tool_call 消息。

    Anthropic 要求 thinking 块的 signature 为原始值：空签名表示"未封存的历史推理"，
    上游每轮把同一段 reasoning 重新翻出来重放 → 多轮死循环（bugfix-375）。
    """
    thinking_text = "我需要检查仓库的最近提交"
    real_signature = "EqoBCkgIARgCIkDxyz_real_signature_token_abc123"
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "thinking", "thinking": "", "signature": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": thinking_text},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "signature_delta", "signature": real_signature},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "tool_use",
                "id": "tool_1",
                "name": "bash",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {
                "type": "input_json_delta",
                "partial_json": '{"command":"gh log --oneline -10"}',
            },
        },
        {"type": "content_block_stop", "index": 1},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"input_tokens": 15, "output_tokens": 8},
        },
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect(
        client,
        LLMGenerateRequest(
            session_id="sess_anthropic_signature",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="检查最近的提交"),),
        ),
    )

    tool_call_msg = next((m for m in messages if m.tool_calls), None)
    assert tool_call_msg is not None, "应该有 tool_call 消息"
    assert tool_call_msg.reasoning_content == thinking_text, (
        f"thinking 文本未 round-trip: {tool_call_msg.reasoning_content!r}"
    )
    assert tool_call_msg.reasoning_signature == real_signature, (
        f"thinking signature 未 round-trip，实际: {tool_call_msg.reasoning_signature!r}"
    )


# ---------------------------------------------------------------------------
# bugfix-380: SSE error 事件、流提前结束、非法 JSON 必须抛 ModelError
# ---------------------------------------------------------------------------

import pytest
from agent.core.errors import ModelError


async def test_stream_response_sse_error_event_raises_model_error() -> None:
    """Anthropic SSE {"type":"error",...} 帧必须抛 ModelError,不静默吞掉。"""
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {
            "type": "error",
            "error": {
                "type": "permission_error",
                "message": "You've reached your usage limit for this billing cycle.",
            },
        },
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect(
            client,
            LLMGenerateRequest(
                session_id="sess_sse_error",
                model="kimiCoding:K2.6",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err_str = str(exc_info.value)
    assert (
        "usage limit" in err_str
        or "permission_error" in err_str
        or "permission" in err_str.lower()
    )


async def test_stream_response_incomplete_stream_raises_model_error() -> None:
    """流提前结束(无 message_stop 且无 content block yield)必须抛 ModelError。"""
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError):
        await _collect(
            client,
            LLMGenerateRequest(
                session_id="sess_incomplete",
                model="kimiCoding:K2.6",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )


async def test_stream_response_happy_path() -> None:
    """happy path(正常完整流)正常 yield 消息。"""
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "hello"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"input_tokens": 3, "output_tokens": 1},
        },
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect(
        client,
        LLMGenerateRequest(
            session_id="sess_happy_380",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="hi"),),
        ),
    )
    text_msg = next((m for m in messages if m.content == "hello"), None)
    assert text_msg is not None, "happy path 仍应正常 yield 文本消息"


async def test_stream_response_shares_signature_across_parallel_tool_calls() -> None:
    """多个 tool_use 共享同一 thinking 块时，每个都要带上 reasoning_signature。"""
    thinking_text = "我需要并行检查两个命令"
    real_signature = "EqoBCkgIARgCIkD_parallel_sig_token_xyz789"
    events = [
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "thinking", "thinking": "", "signature": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": thinking_text},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "signature_delta", "signature": real_signature},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "tool_use",
                "id": "tool_1",
                "name": "bash",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "input_json_delta", "partial_json": '{"command":"pwd"}'},
        },
        {"type": "content_block_stop", "index": 1},
        {
            "type": "content_block_start",
            "index": 2,
            "content_block": {
                "type": "tool_use",
                "id": "tool_2",
                "name": "bash",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 2,
            "delta": {
                "type": "input_json_delta",
                "partial_json": '{"command":"ls -la"}',
            },
        },
        {"type": "content_block_stop", "index": 2},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"input_tokens": 10, "output_tokens": 10},
        },
        {"type": "message_stop"},
    ]
    body = _make_anthropic_sse(events)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect(
        client,
        LLMGenerateRequest(
            session_id="sess_anthropic_parallel_sig",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="请并行运行两个命令"),),
        ),
    )

    tool_call_msgs = [m for m in messages if m.tool_calls]
    assert len(tool_call_msgs) == 2, "应该有两条 tool_call 消息"
    for msg in tool_call_msgs:
        assert msg.reasoning_signature == real_signature, (
            f"tool_call {msg.tool_calls[0].name} 缺 reasoning_signature: {msg.reasoning_signature!r}"
        )


# ---------------------------------------------------------------------------
# FIX 2: HTTP 4xx/5xx 专项测试 — raise_for_status() → ModelError
# ---------------------------------------------------------------------------


async def test_http_401_raises_model_error() -> None:
    """HTTP 401 鉴权失败必须 raise ModelError，状态码体现在 error details。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, text="Unauthorized", headers={"content-type": "application/json"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect(
            client,
            LLMGenerateRequest(
                session_id="sess_401",
                model="kimiCoding:K2.6",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err = exc_info.value
    assert err.details.get("status_code") == 401 or "401" in str(err), (
        f"ModelError 应包含 401 状态码，实际: {err!r}"
    )


async def test_http_429_raises_model_error() -> None:
    """HTTP 429 限流必须 raise ModelError。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, text="Too Many Requests", headers={"content-type": "application/json"}
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect(
            client,
            LLMGenerateRequest(
                session_id="sess_429",
                model="kimiCoding:K2.6",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err = exc_info.value
    assert err.details.get("status_code") == 429 or "429" in str(err), (
        f"ModelError 应包含 429 状态码，实际: {err!r}"
    )


async def test_http_500_raises_model_error() -> None:
    """HTTP 500 服务端错误必须 raise ModelError。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            text="Internal Server Error",
            headers={"content-type": "application/json"},
        )

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect(
            client,
            LLMGenerateRequest(
                session_id="sess_500",
                model="kimiCoding:K2.6",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err = exc_info.value
    assert err.details.get("status_code") == 500 or "500" in str(err), (
        f"ModelError 应包含 500 状态码，实际: {err!r}"
    )


# ---------------------------------------------------------------------------
# FIX 3: 传输层错误专项测试 — httpx.HTTPError → ModelError
# ---------------------------------------------------------------------------


async def test_connect_timeout_raises_model_error() -> None:
    """连接超时(ConnectTimeout)必须 raise ModelError。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out", request=request)

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect(
            client,
            LLMGenerateRequest(
                session_id="sess_connect_timeout",
                model="kimiCoding:K2.6",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err = exc_info.value
    assert (
        "transport" in str(err).lower()
        or "timeout" in str(err).lower()
        or err.details.get("error")
    ), f"ModelError 应反映传输层超时，实际: {err!r}"


async def test_connect_error_raises_model_error() -> None:
    """连接被拒(ConnectError)必须 raise ModelError。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = AnthropicClient(
        base_url="http://127.0.0.1:9999",
        model="kimiCoding:K2.6",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect(
            client,
            LLMGenerateRequest(
                session_id="sess_connect_error",
                model="kimiCoding:K2.6",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err = exc_info.value
    assert (
        "transport" in str(err).lower()
        or "connect" in str(err).lower()
        or err.details.get("error")
    ), f"ModelError 应反映连接被拒，实际: {err!r}"


async def test_stream_usage_surfaces_cache_hit_fields() -> None:
    """feat-439-M1: 流式终态 message_stop 的 usage 暴露缓存读取量。"""
    events = [
        {"type": "message_start", "message": {"role": "assistant"}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}},
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {
                "input_tokens": 100,
                "output_tokens": 8,
                "cache_creation_input_tokens": 5,
                "cache_read_input_tokens": 2,
            },
        },
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
            session_id="sess_cache_439",
            model="kimiCoding:K2.6",
            messages=(LLMMessage(role="user", content="hi"),),
        ),
    )
    final = next((m for m in messages if m.usage is not None), None)
    assert final is not None and final.usage is not None
    assert final.usage.prompt_tokens == 107
    assert final.usage.cache_read_tokens == 2
    assert final.usage.cache_total_input_tokens == 107
