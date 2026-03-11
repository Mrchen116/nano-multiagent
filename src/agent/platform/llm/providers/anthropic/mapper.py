"""Request/response mapper for Anthropic messages protocol."""

from __future__ import annotations

import sys

import json
from typing import Any, Mapping

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from agent.core.types import TokenUsage

_DEFAULT_MAX_TOKENS = 1024


class AnthropicMapper:
    """Map normalized LLM contracts to Anthropic-compatible payloads."""

    endpoint_path = "/v1/messages"

    def map_generate_request(self, request: LLMGenerateRequest) -> Mapping[str, Any]:
        """Map normalized request fields into Anthropic request JSON."""

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
        if request.tools:
            payload["tools"] = [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "input_schema": dict(spec.input_schema),
                }
                for spec in request.tools
            ]
        return payload

    def map_generate_response(self, payload: Mapping[str, Any]) -> LLMGenerateResponse:
        """Normalize Anthropic response payload."""

        content_blocks = payload.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise ModelError(
                "anthropic response missing content blocks",
                retryable=False,
                details={"payload_keys": sorted(payload.keys())},
            )

        normalized_content = _normalize_content(content_blocks)
        tool_calls = _normalize_tool_calls(content_blocks)
        if not normalized_content and not tool_calls:
            raise ModelError(
                "anthropic response has no text content or tool calls",
                retryable=False,
            )

        finish_reason = payload.get("stop_reason")
        role = str(payload.get("role", "assistant"))

        return LLMGenerateResponse(
            model=str(payload.get("model", "")),
            message=LLMMessage(role=role, content=normalized_content, tool_calls=tool_calls),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            usage=_parse_anthropic_usage(payload.get("usage")),
            raw=dict(payload),
        )

    def _map_message(self, message: LLMMessage) -> Mapping[str, Any]:
        if message.role == "assistant":
            content: list[dict[str, Any]] = []
            if message.content:
                content.append({"type": "text", "text": message.content})
            for tool_call in message.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.call_id,
                        "name": tool_call.name,
                        "input": dict(tool_call.arguments),
                    }
                )
            return {"role": "assistant", "content": content}
        if message.role == "tool":
            if message.tool_call_id is None:
                raise ModelError("tool message requires tool_call_id", retryable=False)
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id,
                        "content": _map_tool_result_content(message.content),
                    }
                ],
            }
        role = message.role if message.role in {"user", "assistant"} else "user"
        return {
            "role": role,
            "content": [{"type": "text", "text": message.content}],
        }


def _map_tool_result_content(content: str) -> list[dict[str, Any]]:
    payload = _parse_tool_payload(content)
    if payload is None:
        return [{"type": "text", "text": content}]
    output = payload.get("output")
    if not isinstance(output, Mapping):
        return [{"type": "text", "text": content}]
    structured_content = output.get("content")
    if not isinstance(structured_content, list):
        return [{"type": "text", "text": content}]

    normalized = _normalize_tool_result_parts(structured_content)
    if normalized:
        return normalized
    return [{"type": "text", "text": content}]


def _parse_tool_payload(content: str) -> Mapping[str, Any] | None:
    if not content:
        return None
    try:
        decoded = json.loads(content)
    except ValueError:
        return None
    if not isinstance(decoded, Mapping):
        return None
    return decoded


def _normalize_tool_result_parts(parts: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in parts:
        if not isinstance(item, Mapping):
            continue
        part_type = item.get("type")
        if part_type == "text":
            text = item.get("text")
            if isinstance(text, str):
                normalized.append({"type": "text", "text": text})
            continue
        if part_type == "image":
            image_part = _to_anthropic_image_part(
                image_url=item.get("image_url"),
                image_data=item.get("data"),
                mime_type=item.get("mimeType", item.get("mime_type")),
            )
            if image_part is not None:
                normalized.append(image_part)
            continue
    return normalized


def _to_anthropic_image_part(*, image_url: Any, image_data: Any, mime_type: Any) -> dict[str, Any] | None:
    if isinstance(image_data, str) and image_data:
        media_type = mime_type if isinstance(mime_type, str) and mime_type else "application/octet-stream"
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data,
            },
        }

    if not isinstance(image_url, str) or not image_url.startswith("data:"):
        return None
    header, separator, payload = image_url.partition(",")
    if separator != "," or not payload:
        return None
    if ";base64" not in header:
        return None

    media_type = header.removeprefix("data:").split(";", 1)[0]
    if not media_type and isinstance(mime_type, str):
        media_type = mime_type
    if not media_type:
        media_type = "application/octet-stream"
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": payload,
        },
    }


def _normalize_content(content_blocks: list[Any]) -> str:
    chunks: list[str] = []
    for block in content_blocks:
        if isinstance(block, Mapping) and block.get("type") == "text":
            text_value = block.get("text")
            if text_value is not None:
                chunks.append(str(text_value))
    return "".join(chunks)


def _normalize_tool_calls(content_blocks: list[Any]) -> tuple[LLMToolCall, ...]:
    tool_calls: list[LLMToolCall] = []
    for index, block in enumerate(content_blocks):
        if not isinstance(block, Mapping) or block.get("type") != "tool_use":
            continue
        call_id = block.get("id")
        name = block.get("name")
        arguments = block.get("input", {})
        if not isinstance(call_id, str) or not call_id:
            call_id = f"tool_use_{index}"
        if not isinstance(name, str) or not name:
            raise ModelError(
                "anthropic response tool_use block missing name",
                retryable=False,
                details={"index": index},
            )
        if not isinstance(arguments, Mapping):
            raise ModelError(
                "anthropic response tool_use input must be object",
                retryable=False,
                details={"index": index, "input_type": type(arguments).__name__},
            )
        tool_calls.append(
            LLMToolCall(
                call_id=call_id,
                name=name,
                arguments=dict(arguments),
            )
        )
    return tuple(tool_calls)


def _parse_anthropic_usage(payload: Any) -> TokenUsage | None:
    if not isinstance(payload, Mapping):
        return None

    input_tokens = _extract_non_negative_int(payload.get("input_tokens"))
    output_tokens = _extract_non_negative_int(payload.get("output_tokens"))
    cache_creation_tokens = _extract_non_negative_int(payload.get("cache_creation_input_tokens")) or 0
    cache_read_tokens = _extract_non_negative_int(payload.get("cache_read_input_tokens")) or 0
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


_LEGACY_ANTHROPIC_MAPPER_MODULE = "agent" + ".llm.providers" + ".anthropic.mapper"
sys.modules.setdefault(_LEGACY_ANTHROPIC_MAPPER_MODULE, sys.modules[__name__])

__all__ = ["AnthropicMapper"]
