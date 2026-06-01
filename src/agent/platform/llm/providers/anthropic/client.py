"""HTTP client for Anthropic messages-compatible providers."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Mapping

import json
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

import httpx

from agent.core.errors import ModelError
from agent.core.llm.interfaces import (
    LLMClient,
    LLMGenerateRequest,
    LLMMessage,
    LLMToolCall,
)
from agent.core.llm.model_registry import resolve_model_metadata
from agent.core.types import TokenUsage
from agent.platform.llm.providers.translator import LLMTranslator

from .mapper import AnthropicMapper


class AnthropicClient(LLMClient):
    """Send normalized generation requests to Anthropic-compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        anthropic_version: str = "2023-06-01",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._default_model = model
        self._api_key = api_key
        self._anthropic_version = anthropic_version
        self._translator = LLMTranslator(AnthropicMapper())
        trust_env = _should_trust_env(base_url)
        self._http_client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            trust_env=trust_env,
        )

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        """Execute one streaming generation call."""

        active_request = request
        if not active_request.model:
            active_request = replace(active_request, model=self._default_model)

        metadata = resolve_model_metadata("anthropic", active_request.model)
        if metadata.extra_request_body:
            merged_extra = dict(metadata.extra_request_body)
            if active_request.extra_body:
                merged_extra.update(active_request.extra_body)
            active_request = replace(active_request, extra_body=merged_extra)

        provider_request = self._translator.to_provider_request(active_request)
        headers = dict(provider_request.headers)
        headers["anthropic-version"] = self._anthropic_version
        if self._api_key:
            headers["x-api-key"] = self._api_key

        try:
            async with self._http_client.stream(
                provider_request.method,
                provider_request.path,
                headers=headers,
                content=json.dumps(provider_request.json_body, separators=(",", ":")),
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    await response.aread()
                    raise
                async for msg in self._stream_response(response):
                    yield msg
        except httpx.HTTPStatusError as exc:
            raise ModelError(
                "anthropic request failed",
                details={
                    "status_code": exc.response.status_code,
                    "response": exc.response.text,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelError(
                "anthropic transport error",
                details={"error": str(exc)},
            ) from exc

    async def _stream_response(
        self, response: httpx.Response
    ) -> AsyncIterator[LLMMessage]:
        """Parse Anthropic SSE stream and yield LLMMessage per content block."""

        content_blocks: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] | None = None
        # Thinking blocks arrive before tool_use blocks in the same assistant turn.
        # One turn may carry several tool_use blocks sharing a single thinking block;
        # the loop later splits them into separate assistant messages, each of which
        # kimi K2.6 requires to carry the turn's reasoning_content — so attach it to
        # every tool_use/text block in this stream, not just the first (bugfix-373).
        # The thinking block also carries a cryptographic signature that must round-trip
        # back unchanged; an empty signature causes the upstream to replay the same
        # reasoning every turn and the agent loops forever (bugfix-375).
        turn_reasoning: str | None = None
        turn_signature: str | None = None
        # Track whether the stream reached a proper terminal event or yielded content;
        # used to detect truncated streams (bugfix-380).
        got_terminal_event = False
        yielded_content = False

        async for event in _iter_sse_events(response):
            event_type = event.get("type")

            # bugfix-380: upstream error event — surface as ModelError immediately.
            if event_type == "error":
                error_obj = event.get("error") or {}
                error_msg = (
                    error_obj.get("message") or str(error_obj) or "upstream error"
                )
                error_type = error_obj.get("type") or "error"
                raise ModelError(
                    f"anthropic: {error_msg}",
                    details={"error_type": error_type, "raw": error_obj},
                    retryable=False,
                )

            if event_type == "content_block_start":
                idx = event.get("index", 0)
                block = event.get("content_block", {})
                content_blocks[idx] = dict(block)

            elif event_type == "content_block_delta":
                idx = event.get("index", 0)
                delta = event.get("delta", {})
                block = content_blocks.get(idx)
                if block is not None:
                    _apply_anthropic_delta(block, delta)

            elif event_type == "content_block_stop":
                idx = event.get("index", 0)
                block = content_blocks.pop(idx, None)
                if block is None:
                    continue
                if block.get("type") in {"thinking", "redacted_thinking"}:
                    thinking_text = block.get("thinking", "")
                    if thinking_text:
                        turn_reasoning = (turn_reasoning or "") + thinking_text
                    sig = block.get("signature", "")
                    if sig:
                        turn_signature = sig
                    continue
                yielded_content = True
                yield _anthropic_block_to_llm_message(
                    block,
                    reasoning_content=turn_reasoning,
                    reasoning_signature=turn_signature,
                )

            elif event_type == "message_delta":
                delta = event.get("delta", {})
                if "stop_reason" in delta:
                    finish_reason = delta["stop_reason"]
                usage = event.get("usage")

            elif event_type == "message_stop":
                got_terminal_event = True
                yield LLMMessage(
                    role="assistant",
                    content="",
                    finish_reason=finish_reason,
                    usage=_parse_anthropic_usage(usage),
                )

        # bugfix-380: stream ended without message_stop and without yielded content —
        # provider truncated the response (network drop, quota abort mid-stream, etc.).
        if not got_terminal_event and not yielded_content:
            raise ModelError(
                "anthropic: stream ended without terminal event",
                details={"finish_reason": finish_reason},
                retryable=True,
            )

    async def close(self) -> None:
        """Close underlying HTTP resources."""

        await self._http_client.aclose()

    async def __aenter__(self) -> "AnthropicClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()


async def _iter_sse_events(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """Iterate over SSE data lines and yield parsed JSON events."""

    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data = line.removeprefix("data:").lstrip(" ")
            if data == "[DONE]":
                continue
            try:
                yield json.loads(data)
            except ValueError:
                continue


def _apply_anthropic_delta(block: dict[str, Any], delta: dict[str, Any]) -> None:
    """Apply a delta update to an in-flight content block."""

    delta_type = delta.get("type")
    if delta_type == "text_delta":
        block["text"] = block.get("text", "") + delta.get("text", "")
    elif delta_type == "thinking_delta":
        block["thinking"] = block.get("thinking", "") + delta.get("thinking", "")
    elif delta_type == "signature_delta":
        # Accumulate the thinking block's cryptographic signature; must round-trip
        # unchanged so the upstream recognises it as sealed history (bugfix-375).
        block["signature"] = block.get("signature", "") + delta.get("signature", "")
    elif delta_type == "input_json_delta":
        existing = block.get("input", "")
        if isinstance(existing, dict):
            existing = ""
        block["input"] = existing + delta.get("partial_json", "")


def _anthropic_block_to_llm_message(
    block: dict[str, Any],
    *,
    reasoning_content: str | None = None,
    reasoning_signature: str | None = None,
) -> LLMMessage:
    """Convert one completed Anthropic content block into an LLMMessage."""

    block_type = block.get("type")
    if block_type == "text":
        return LLMMessage(
            role="assistant",
            content=block.get("text", ""),
            reasoning_content=reasoning_content,
            reasoning_signature=reasoning_signature,
        )
    if block_type == "tool_use":
        raw_input = block.get("input", "")
        if isinstance(raw_input, str):
            try:
                parsed_input = json.loads(raw_input)
            except ValueError:
                parsed_input = {}
        elif isinstance(raw_input, Mapping):
            parsed_input = dict(raw_input)
        else:
            parsed_input = {}
        return LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(
                    call_id=block.get("id", ""),
                    name=block.get("name", ""),
                    arguments=parsed_input,
                ),
            ),
            reasoning_content=reasoning_content,
            reasoning_signature=reasoning_signature,
        )
    return LLMMessage(
        role="assistant",
        content="",
        reasoning_content=reasoning_content,
        reasoning_signature=reasoning_signature,
    )


def _parse_anthropic_usage(payload: dict[str, Any] | None) -> TokenUsage | None:
    """Parse Anthropic usage payload into TokenUsage."""

    if not isinstance(payload, dict):
        return None

    input_tokens = _extract_non_negative_int(payload.get("input_tokens"))
    output_tokens = _extract_non_negative_int(payload.get("output_tokens"))
    cache_creation_tokens = (
        _extract_non_negative_int(payload.get("cache_creation_input_tokens")) or 0
    )
    cache_read_tokens = (
        _extract_non_negative_int(payload.get("cache_read_input_tokens")) or 0
    )
    if input_tokens is None and output_tokens is None:
        return None

    prompt_tokens = (input_tokens or 0) + cache_creation_tokens + cache_read_tokens
    completion_tokens = output_tokens or 0
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def _extract_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def _should_trust_env(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").strip().lower()
    local_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
    return host not in local_hosts


_LEGACY_ANTHROPIC_CLIENT_MODULE = "agent" + ".llm.providers" + ".anthropic.client"
sys.modules.setdefault(_LEGACY_ANTHROPIC_CLIENT_MODULE, sys.modules[__name__])

__all__ = ["AnthropicClient", "_should_trust_env"]
