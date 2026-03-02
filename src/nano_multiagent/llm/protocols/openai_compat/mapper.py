import json
from typing import Any, Mapping

from nano_multiagent.core.errors import ModelError

from ...interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall


class OpenAICompatMapper:
    endpoint_path = "/v1/chat/completions"

    def map_generate_request(self, request: LLMGenerateRequest) -> Mapping[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [self._map_message(message) for message in request.messages],
            "stream": request.stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = [self._map_tool_spec(spec) for spec in request.tools]
            payload["tool_choice"] = "auto"
        return payload

    def map_generate_response(self, payload: Mapping[str, Any]) -> LLMGenerateResponse:
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
            raw=dict(payload),
        )

    def _map_message(self, message: LLMMessage) -> Mapping[str, Any]:
        mapped: dict[str, Any] = {"role": message.role}
        if message.role == "assistant" and message.tool_calls:
            mapped["content"] = message.content or ""
            mapped["tool_calls"] = [self._map_tool_call(call) for call in message.tool_calls]
        elif message.role == "tool":
            mapped["content"] = message.content
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
