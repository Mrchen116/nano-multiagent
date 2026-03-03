"""Request/response mapper for Anthropic messages protocol."""

from __future__ import annotations

from typing import Any, Mapping

from nano_multiagent.core.errors import ModelError

from ...interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall

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
        """Normalize Anthropic response payload.

        Raises:
            ModelError: If payload misses required content/tool structure.
        """

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
                        "content": [{"type": "text", "text": message.content}],
                    }
                ],
            }
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
