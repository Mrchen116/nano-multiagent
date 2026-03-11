"""HTTP client for Anthropic messages-compatible providers."""

from __future__ import annotations

import sys

import json
from dataclasses import replace
from urllib.parse import urlparse

import httpx

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMGenerateResponse
from agent.platform.llm.providers.translator import LLMTranslator

from .mapper import AnthropicMapper


class AnthropicClient(LLMClient):
    """Send normalized generation requests to Anthropic-compatible endpoint."""

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
        trust_env = _should_trust_env(base_url)
        self._http_client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            trust_env=trust_env,
        )

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        """Execute one generation call."""

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
        """Close underlying HTTP resources."""

        self._http_client.close()

    def __enter__(self) -> "AnthropicClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def _should_trust_env(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").strip().lower()
    local_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
    return host not in local_hosts


_LEGACY_ANTHROPIC_CLIENT_MODULE = "agent" + ".llm.providers" + ".anthropic.client"
sys.modules.setdefault(_LEGACY_ANTHROPIC_CLIENT_MODULE, sys.modules[__name__])

__all__ = ["AnthropicClient", "_should_trust_env"]
