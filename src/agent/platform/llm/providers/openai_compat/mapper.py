"""Request/response mapper for OpenAI-compatible chat completion protocol."""

import sys
import json
from typing import Any, Mapping

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from agent.core.types import TokenUsage


class OpenAICompatMapper:
    """Map normalized LLM contracts to OpenAI-compatible payloads."""

    endpoint_path = "/v1/chat/completions"

    def map_generate_request(self, request: LLMGenerateRequest) -> Mapping[str, Any]:
        """Map normalized request fields into provider request JSON."""

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [self._map_message(message) for message in request.messages],
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop_sequences:
            payload["stop"] = list(request.stop_sequences)
        if request.tools:
            payload["tools"] = [self._map_tool_spec(spec) for spec in request.tools]
            payload["tool_choice"] = "auto"
        if request.extra_body:
            payload.update(request.extra_body)
        return payload

    def map_generate_response(self, payload: Mapping[str, Any]) -> LLMGenerateResponse:
        """Normalize OpenAI-compatible response payload."""

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelError(
                "openai_compat response missing choices",
                retryable=False,
                details={"payload_keys": sorted(payload.keys())},
            )

        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise ModelError(
                "openai_compat response choice is invalid",
                retryable=False,
            )

        message_payload = first_choice.get("message")
        if not isinstance(message_payload, Mapping):
            raise ModelError(
                "openai_compat response missing assistant message",
                retryable=False,
            )

        content = message_payload.get("content", "")
        normalized_content = _normalize_content(content)
        tool_calls = self._parse_tool_calls(message_payload.get("tool_calls"))
        finish_reason = first_choice.get("finish_reason")

        return LLMGenerateResponse(
            model=str(payload.get("model", "")),
            message=LLMMessage(
                role=str(message_payload.get("role", "assistant")),
                content=normalized_content,
                tool_calls=tool_calls,
            ),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            usage=_parse_openai_usage(payload.get("usage")),
            raw=dict(payload),
        )

    def _map_message(self, message: LLMMessage) -> Mapping[str, Any]:
        mapped: dict[str, Any] = {"role": message.role}
        if message.role == "assistant" and message.tool_calls:
            mapped["content"] = message.content or ""
            mapped["tool_calls"] = [self._map_tool_call(call) for call in message.tool_calls]
        elif message.role == "tool":
            mapped["content"] = _map_tool_content(message.content)
            if message.tool_call_id is None:
                raise ModelError("tool message requires tool_call_id", retryable=False)
            mapped["tool_call_id"] = message.tool_call_id
        else:
            mapped["content"] = message.content
        if message.name is not None:
            mapped["name"] = message.name
        return mapped

    def _map_tool_spec(self, spec: Any) -> Mapping[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": dict(spec.input_schema),
            },
        }

    def _map_tool_call(self, tool_call: LLMToolCall) -> Mapping[str, Any]:
        return {
            "id": tool_call.call_id,
            "type": "function",
            "function": {
                "name": tool_call.name,
                "arguments": json.dumps(tool_call.arguments, ensure_ascii=True, separators=(",", ":")),
            },
        }

    def _parse_tool_calls(self, payload: Any) -> tuple[LLMToolCall, ...]:
        if payload is None:
            return ()
        if not isinstance(payload, list):
            raise ModelError(
                "openai_compat response tool_calls is invalid",
                retryable=False,
            )

        parsed: list[LLMToolCall] = []
        for index, item in enumerate(payload):
            if not isinstance(item, Mapping):
                raise ModelError(
                    "openai_compat response tool_calls item is invalid",
                    retryable=False,
                    details={"index": index},
                )
            function_payload = item.get("function")
            if not isinstance(function_payload, Mapping):
                raise ModelError(
                    "openai_compat response tool_calls missing function payload",
                    retryable=False,
                    details={"index": index},
                )
            name = function_payload.get("name")
            if not isinstance(name, str) or not name:
                raise ModelError(
                    "openai_compat response tool call missing name",
                    retryable=False,
                    details={"index": index},
                )
            arguments = _parse_tool_arguments(function_payload.get("arguments"))
            call_id = item.get("id")
            if not isinstance(call_id, str) or not call_id:
                call_id = f"tool_call_{index}"
            parsed.append(
                LLMToolCall(
                    call_id=call_id,
                    name=name,
                    arguments=arguments,
                )
            )
        return tuple(parsed)


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, Mapping) and item.get("type") == "text":
                text_value = item.get("text")
                if isinstance(text_value, str):
                    chunks.append(text_value)
        return "".join(chunks)
    return str(content)


def _map_tool_content(content: str | list[dict[str, Any]]) -> Any:
    if isinstance(content, list):
        normalized = _normalize_tool_output_parts(content)
        if normalized:
            return normalized
        return ""
    payload = _parse_tool_payload(content)
    if payload is None:
        return content
    output = payload.get("output")
    if not isinstance(output, Mapping):
        return content
    structured_content = output.get("content")
    if not isinstance(structured_content, list):
        return content
    normalized_parts = _normalize_tool_output_parts(structured_content)
    if not normalized_parts:
        return content
    return normalized_parts


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


def _normalize_tool_output_parts(parts: list[Any]) -> list[dict[str, Any]]:
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
            image_data = item.get("data")
            mime_type = item.get("mimeType", item.get("mime_type"))
            if isinstance(image_data, str) and image_data:
                media_type = mime_type if isinstance(mime_type, str) and mime_type else "application/octet-stream"
                normalized.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}})
                continue
            image_url = item.get("image_url")
            if isinstance(image_url, str) and image_url:
                normalized.append({"type": "image_url", "image_url": {"url": image_url}})
            continue
        if part_type == "image_url":
            image_payload = item.get("image_url")
            if isinstance(image_payload, Mapping):
                url = image_payload.get("url")
                if isinstance(url, str) and url:
                    normalized.append({"type": "image_url", "image_url": {"url": url}})
            elif isinstance(image_payload, str) and image_payload:
                normalized.append({"type": "image_url", "image_url": {"url": image_payload}})
    return normalized


def _parse_tool_arguments(arguments: Any) -> Mapping[str, Any]:
    if arguments is None or arguments == "":
        return {}
    if isinstance(arguments, Mapping):
        return dict(arguments)
    if isinstance(arguments, str):
        try:
            decoded = json.loads(arguments)
        except ValueError as exc:
            raise ModelError(
                "openai_compat response tool call arguments is invalid json",
                retryable=False,
                details={"arguments": arguments},
            ) from exc
        if not isinstance(decoded, Mapping):
            raise ModelError(
                "openai_compat response tool call arguments must decode to object",
                retryable=False,
                details={"arguments_type": type(decoded).__name__},
            )
        return dict(decoded)
    raise ModelError(
        "openai_compat response tool call arguments has invalid type",
        retryable=False,
        details={"arguments_type": type(arguments).__name__},
    )


def _parse_openai_usage(payload: Any) -> TokenUsage | None:
    if not isinstance(payload, Mapping):
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


_LEGACY_OPENAI_COMPAT_MAPPER_MODULE = "agent" + ".llm.providers" + ".openai_compat.mapper"
sys.modules.setdefault(_LEGACY_OPENAI_COMPAT_MAPPER_MODULE, sys.modules[__name__])

__all__ = ["OpenAICompatMapper"]
