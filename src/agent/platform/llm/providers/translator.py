"""Translate normalized LLM contracts to provider-specific HTTP payloads."""

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    """Represent one provider HTTP request ready to send."""

    method: str
    path: str
    headers: Mapping[str, str]
    json_body: Mapping[str, Any]


class ProviderMapper(Protocol):
    """Define the provider-specific mapping contract."""

    endpoint_path: str

    def map_generate_request(self, request: LLMGenerateRequest) -> Mapping[str, Any]:
        """Map a normalized request into provider JSON payload."""

        ...

    def map_generate_response(self, payload: Mapping[str, Any]) -> LLMGenerateResponse:
        """Map provider JSON payload into normalized response."""

        ...


class LLMTranslator:
    """Bridge normalized contracts and provider mapper contracts."""

    def __init__(self, mapper: ProviderMapper) -> None:
        self._mapper = mapper

    def to_provider_request(self, request: LLMGenerateRequest) -> ProviderRequest:
        """Build provider HTTP request metadata from a normalized request.

        Args:
            request: Normalized generation request.

        Returns:
            Provider request containing method/path/headers/body.

        Raises:
            ValueError: If `session_id` is empty after trimming.
        """

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
        """Convert provider payload into normalized response semantics."""

        return self._mapper.map_generate_response(payload)
