"""HTTP client for OpenAI-compatible chat completion providers."""

import sys
from collections.abc import AsyncIterator
from typing import Any
import json
from dataclasses import replace
from urllib.parse import urlparse

import httpx

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.core.types import TokenUsage
from agent.platform.llm.providers.translator import LLMTranslator

from .mapper import OpenAICompatMapper


class OpenAICompatClient(LLMClient):
    """Send normalized generation requests to an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._default_model = model
        self._api_key = api_key
        self._translator = LLMTranslator(OpenAICompatMapper())
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

        provider_request = self._translator.to_provider_request(active_request)
        headers = dict(provider_request.headers)
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

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
                    # Read body while stream is still open inside the context manager.
                    await response.aread()
                    raise
                async for msg in self._stream_response(response):
                    yield msg
        except httpx.HTTPStatusError as exc:
            raise ModelError(
                "openai_compat request failed",
                details={
                    "status_code": exc.response.status_code,
                    "response": exc.response.text,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelError(
                "openai_compat transport error",
                details={"error": str(exc)},
            ) from exc

    async def _stream_response(self, response: httpx.Response) -> AsyncIterator[LLMMessage]:
        """Parse OpenAI-compatible SSE stream and yield LLMMessage."""

        text_buffer = ""
        reasoning_buffer = ""
        tool_calls_buffer: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] | None = None
        # Track whether a finish_reason frame was received (bugfix-380).
        got_terminal_event = False

        async for event in _iter_sse_events(response):
            # bugfix-380: top-level {"error":{...}} frame — surface as ModelError.
            if "error" in event and "choices" not in event:
                error_obj = event["error"] if isinstance(event["error"], dict) else {}
                error_msg = error_obj.get("message") or str(event["error"]) or "upstream error"
                error_type = error_obj.get("type") or "error"
                raise ModelError(
                    f"openai_compat: {error_msg}",
                    details={"error_type": error_type, "raw": error_obj},
                    retryable=False,
                )

            choice = _first_choice(event)
            if choice is None:
                continue

            delta = choice.get("delta", {})
            if not isinstance(delta, dict):
                delta = {}

            if "content" in delta:
                content = delta["content"]
                if content:
                    text_buffer += str(content)

            # Collect reasoning_content from providers like kimi K2.6 in thinking mode.
            # This must be round-tripped back in subsequent requests or the upstream
            # rejects with "reasoning_content is missing in assistant tool call message".
            reasoning = delta.get("reasoning_content")
            if reasoning:
                reasoning_buffer += str(reasoning)

            if "tool_calls" in delta and isinstance(delta["tool_calls"], list):
                for tc in delta["tool_calls"]:
                    if isinstance(tc, dict):
                        _accumulate_openai_tool_call(tool_calls_buffer, tc)

            if choice.get("finish_reason") is not None:
                got_terminal_event = True
                finish_reason = choice["finish_reason"]
                usage = event.get("usage")
                # Flush all accumulated content blocks
                if text_buffer:
                    yield LLMMessage(role="assistant", content=text_buffer)
                    text_buffer = ""
                accumulated_reasoning = reasoning_buffer or None
                reasoning_buffer = ""
                for tc in _finalize_tool_calls(tool_calls_buffer, reasoning_content=accumulated_reasoning):
                    yield tc
                tool_calls_buffer.clear()
                # Terminal metadata message
                yield LLMMessage(
                    role="assistant",
                    content="",
                    finish_reason=finish_reason,
                    usage=_parse_openai_usage(usage),
                )

        # bugfix-380: stream ended without finish_reason and without any content —
        # provider truncated the response.
        if not got_terminal_event and not text_buffer and not tool_calls_buffer:
            raise ModelError(
                "openai_compat: stream ended without terminal event",
                details={"finish_reason": finish_reason},
                retryable=True,
            )

    async def close(self) -> None:
        """Close underlying HTTP resources."""

        await self._http_client.aclose()

    async def __aenter__(self) -> "OpenAICompatClient":
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


def _first_choice(event: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the first choice from an OpenAI SSE event."""

    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    choice = choices[0]
    return choice if isinstance(choice, dict) else None


def _accumulate_openai_tool_call(buffer: dict[int, dict[str, Any]], delta: dict[str, Any]) -> None:
    """Accumulate incremental tool_call fragments keyed by index."""

    idx = delta.get("index", 0)
    if not isinstance(idx, int):
        idx = 0
    existing = buffer.setdefault(idx, {})
    function_delta = delta.get("function", {})
    if isinstance(function_delta, dict):
        if "name" in function_delta:
            existing["name"] = function_delta["name"]
        if "arguments" in function_delta:
            existing["arguments"] = existing.get("arguments", "") + function_delta["arguments"]
    if "id" in delta:
        existing["id"] = delta["id"]
    if "type" in delta:
        existing["type"] = delta["type"]


def _finalize_tool_calls(
    buffer: dict[int, dict[str, Any]],
    reasoning_content: str | None = None,
) -> list[LLMMessage]:
    """Convert accumulated tool_call buffers into LLMMessage instances."""

    messages: list[LLMMessage] = []
    sorted_keys = sorted(buffer.keys())
    for pos, idx in enumerate(sorted_keys):
        tc = buffer[idx]
        raw_arguments = tc.get("arguments", "")
        if isinstance(raw_arguments, str):
            try:
                parsed_arguments = json.loads(raw_arguments)
            except ValueError:
                parsed_arguments = {}
        elif isinstance(raw_arguments, dict):
            parsed_arguments = dict(raw_arguments)
        else:
            parsed_arguments = {}
        # Attach reasoning_content only to the first message; loop merges adjacent
        # assistant messages and will preserve it via _append_llm_message.
        msg_reasoning = reasoning_content if pos == 0 else None
        messages.append(
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id=tc.get("id", f"tool_call_{idx}"),
                        name=tc.get("name", ""),
                        arguments=parsed_arguments,
                    ),
                ),
                reasoning_content=msg_reasoning,
            )
        )
    return messages


def _parse_openai_usage(payload: dict[str, Any] | None) -> TokenUsage | None:
    """Parse OpenAI usage payload into TokenUsage."""

    if not isinstance(payload, dict):
        return None

    prompt_tokens = _extract_non_negative_int(payload.get("prompt_tokens"))
    completion_tokens = _extract_non_negative_int(payload.get("completion_tokens"))
    total_tokens = _extract_non_negative_int(payload.get("total_tokens"))
    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None

    resolved_prompt = prompt_tokens or 0
    resolved_completion = completion_tokens or 0
    resolved_total = total_tokens if total_tokens is not None else resolved_prompt + resolved_completion
    return TokenUsage(
        prompt_tokens=resolved_prompt,
        completion_tokens=resolved_completion,
        total_tokens=resolved_total,
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


_LEGACY_OPENAI_COMPAT_CLIENT_MODULE = "agent" + ".llm.providers" + ".openai_compat.client"
sys.modules.setdefault(_LEGACY_OPENAI_COMPAT_CLIENT_MODULE, sys.modules[__name__])

__all__ = ["OpenAICompatClient", "_should_trust_env"]
