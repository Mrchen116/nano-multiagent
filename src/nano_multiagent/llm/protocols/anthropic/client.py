from __future__ import annotations

import json
from dataclasses import replace

import httpx

from nano_multiagent.core.errors import ModelError

from ...interfaces import LLMClient, LLMGenerateRequest, LLMGenerateResponse
from ...translator import LLMTranslator
from .mapper import AnthropicMapper


class AnthropicClient(LLMClient):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        anthropic_version: str = "2023-06-01",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._default_model = model
        self._api_key = api_key
        self._anthropic_version = anthropic_version
        self._translator = LLMTranslator(AnthropicMapper())
        self._http_client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        if request.stream:
            raise ModelError("streaming generation is not implemented yet", retryable=False)

        active_request = request
        if not active_request.model:
            active_request = replace(active_request, model=self._default_model)

        provider_request = self._translator.to_provider_request(active_request)
        headers = dict(provider_request.headers)
        headers["anthropic-version"] = self._anthropic_version
        if self._api_key:
            headers["x-api-key"] = self._api_key

        try:
            response = self._http_client.request(
                provider_request.method,
                provider_request.path,
                headers=headers,
                content=json.dumps(provider_request.json_body, separators=(",", ":")),
            )
            response.raise_for_status()
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

        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelError(
                "anthropic response is not valid json",
                retryable=False,
                details={"response": response.text},
            ) from exc

        return self._translator.from_provider_response(payload)

    def close(self) -> None:
        self._http_client.close()

    def __enter__(self) -> "AnthropicClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
