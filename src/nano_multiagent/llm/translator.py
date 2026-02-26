from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .interfaces import LLMGenerateRequest, LLMGenerateResponse


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    method: str
    path: str
    headers: Mapping[str, str]
    json_body: Mapping[str, Any]


class ProviderMapper(Protocol):
    endpoint_path: str

    def map_generate_request(self, request: LLMGenerateRequest) -> Mapping[str, Any]:
        ...

    def map_generate_response(self, payload: Mapping[str, Any]) -> LLMGenerateResponse:
        ...


class LLMTranslator:
    def __init__(self, mapper: ProviderMapper) -> None:
        self._mapper = mapper

    def to_provider_request(self, request: LLMGenerateRequest) -> ProviderRequest:
        session_id = request.session_id.strip()
        if not session_id:
            raise ValueError("session_id is required for llm provider calls")

        return ProviderRequest(
            method="POST",
            path=self._mapper.endpoint_path,
            headers={
                "Content-Type": "application/json",
                "X-Session-Id": session_id,
            },
            json_body=self._mapper.map_generate_request(request),
        )

    def from_provider_response(self, payload: Mapping[str, Any]) -> LLMGenerateResponse:
        return self._mapper.map_generate_response(payload)
