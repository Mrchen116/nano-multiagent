from __future__ import annotations

from typing import Any, Mapping

from nano_multiagent.core.errors import ModelError

from ...interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage

_DEFAULT_MAX_TOKENS = 1024


class AnthropicMapper:
    endpoint_path = "/v1/messages"

    def map_generate_request(self, request: LLMGenerateRequest) -> Mapping[str, Any]:
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []

        for message in request.messages:
            if message.role == "system":
                if message.content:
                    system_parts.append(message.content)
                continue
            messages.append(self._map_message(message))

        if not messages:
            raise ModelError(
                "anthropic request requires at least one non-system message",
                retryable=False,
            )

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": request.stream,
            "max_tokens": request.max_tokens if request.max_tokens is not None else _DEFAULT_MAX_TOKENS,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    def map_generate_response(self, payload: Mapping[str, Any]) -> LLMGenerateResponse:
        content_blocks = payload.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise ModelError(
                "anthropic response missing content blocks",
                retryable=False,
                details={"payload_keys": sorted(payload.keys())},
            )

        normalized_content = _normalize_content(content_blocks)
        if not normalized_content:
            raise ModelError(
                "anthropic response has no text content",
                retryable=False,
            )

        finish_reason = payload.get("stop_reason")
        role = str(payload.get("role", "assistant"))

        return LLMGenerateResponse(
            model=str(payload.get("model", "")),
            message=LLMMessage(role=role, content=normalized_content),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            raw=dict(payload),
        )

    def _map_message(self, message: LLMMessage) -> Mapping[str, Any]:
        role = message.role if message.role in {"user", "assistant"} else "user"
        return {
            "role": role,
            "content": [{"type": "text", "text": message.content}],
        }


def _normalize_content(content_blocks: list[Any]) -> str:
    chunks: list[str] = []
    for block in content_blocks:
        if isinstance(block, Mapping) and block.get("type") == "text":
            text_value = block.get("text")
            if text_value is not None:
                chunks.append(str(text_value))
    return "".join(chunks)
