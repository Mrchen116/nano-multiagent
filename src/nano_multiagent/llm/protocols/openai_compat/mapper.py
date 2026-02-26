from typing import Any, Mapping

from nano_multiagent.core.errors import ModelError

from ...interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage


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
        finish_reason = first_choice.get("finish_reason")

        return LLMGenerateResponse(
            model=str(payload.get("model", "")),
            message=LLMMessage(
                role=str(message_payload.get("role", "assistant")),
                content=normalized_content,
            ),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            raw=dict(payload),
        )

    def _map_message(self, message: LLMMessage) -> Mapping[str, Any]:
        mapped: dict[str, Any] = {
            "role": message.role,
            "content": message.content,
        }
        if message.name is not None:
            mapped["name"] = message.name
        return mapped


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
