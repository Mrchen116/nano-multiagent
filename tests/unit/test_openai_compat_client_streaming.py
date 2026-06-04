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


async def _collect_messages(
    client: OpenAICompatClient, request: LLMGenerateRequest
) -> list[LLMMessage]:
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
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "reasoning_content": thinking_text},
                    "finish_reason": None,
                }
            ],
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
                            {
                                "index": 0,
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "bash",
                                    "arguments": '{"command":"pwd"}',
                                },
                            },
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


# ---------------------------------------------------------------------------
# bugfix-380: top-level {"error":{...}} 帧、流提前结束必须抛 ModelError
# ---------------------------------------------------------------------------

import pytest
from agent.core.errors import ModelError


async def test_stream_response_top_level_error_raises_model_error() -> None:
    """OpenAI compat 顶层 {"error":{...}} 帧必须抛 ModelError。"""
    chunks = [
        {
            "error": {
                "message": "Rate limit exceeded. Please try again later.",
                "type": "rate_limit_error",
                "code": 429,
            }
        }
    ]
    body = _make_sse_body(chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect_messages(
            client,
            LLMGenerateRequest(
                session_id="sess_top_level_error",
                model="kimi-k2",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err_str = str(exc_info.value)
    assert (
        "rate limit" in err_str.lower()
        or "rate_limit" in err_str.lower()
        or "429" in err_str
    )


async def test_stream_response_incomplete_stream_raises_model_error() -> None:
    """OpenAI compat 流提前结束(无 finish_reason 且空内容)必须抛 ModelError。"""
    chunks = [
        {
            "id": "chatcmpl-1",
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        }
    ]
    body = _make_sse_body(chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError):
        await _collect_messages(
            client,
            LLMGenerateRequest(
                session_id="sess_compat_incomplete",
                model="kimi-k2",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )


async def test_stream_response_happy_path() -> None:
    """happy path 正常流正常 yield 消息。"""
    chunks = [
        {
            "id": "chatcmpl-2",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "hello"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-2",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        },
    ]
    body = _make_sse_body(chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    messages = await _collect_messages(
        client,
        LLMGenerateRequest(
            session_id="sess_compat_happy_380",
            model="kimi-k2",
            messages=(LLMMessage(role="user", content="hi"),),
        ),
    )
    text_msg = next((m for m in messages if m.content == "hello"), None)
    assert text_msg is not None, "happy path 仍应正常 yield 文本消息"


# ---------------------------------------------------------------------------
# FIX 2: HTTP 4xx/5xx 专项测试 — raise_for_status() → ModelError
# ---------------------------------------------------------------------------


async def test_http_401_raises_model_error() -> None:
    """HTTP 401 鉴权失败必须 raise ModelError，状态码体现在 error details。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, text="Unauthorized", headers={"content-type": "application/json"}
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect_messages(
            client,
            LLMGenerateRequest(
                session_id="sess_compat_401",
                model="kimi-k2",
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

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect_messages(
            client,
            LLMGenerateRequest(
                session_id="sess_compat_429",
                model="kimi-k2",
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

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect_messages(
            client,
            LLMGenerateRequest(
                session_id="sess_compat_500",
                model="kimi-k2",
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

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect_messages(
            client,
            LLMGenerateRequest(
                session_id="sess_compat_connect_timeout",
                model="kimi-k2",
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

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9999",
        model="kimi-k2",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelError) as exc_info:
        await _collect_messages(
            client,
            LLMGenerateRequest(
                session_id="sess_compat_connect_error",
                model="kimi-k2",
                messages=(LLMMessage(role="user", content="hi"),),
            ),
        )
    err = exc_info.value
    assert (
        "transport" in str(err).lower()
        or "connect" in str(err).lower()
        or err.details.get("error")
    ), f"ModelError 应反映连接被拒，实际: {err!r}"
