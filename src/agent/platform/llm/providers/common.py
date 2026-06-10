"""Shared low-level helpers for LLM provider implementations.

Providers (anthropic, openai_compat) each carried a private copy of
extract_non_negative_int — consolidated here as refactor-395-M1.

bugfix-402-M6: extract_http_error_facts was also duplicated in both provider
clients; the shared implementation lives here.  Both providers use the same
{"error": {"type", "code", "message"}} JSON envelope, so a single function
parameterised on the provider label is sufficient.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from agent.core.llm.error_classifier import ProviderErrorFacts


def extract_non_negative_int(value: Any) -> int | None:
    """Return *value* as a non-negative int, or None if invalid.

    Rejects booleans (Python's bool is a subclass of int) and negative values.

    Args:
        value: Arbitrary value from a JSON payload.

    Returns:
        The integer if it is a non-negative int; None otherwise.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def extract_http_error_facts(
    exc: httpx.HTTPStatusError,
    *,
    provider: str,
) -> ProviderErrorFacts:
    """Extract ProviderErrorFacts from an HTTP error response.

    Handles the standard ``{"error": {"type": ..., "code": ..., "message": ...}}``
    JSON envelope used by both the Anthropic and OpenAI-compatible APIs.

    Args:
        exc: The httpx HTTP status error to decode.
        provider: Short label used in the fallback message string (e.g.
            ``"anthropic"`` or ``"openai_compat"``).

    Returns:
        A ProviderErrorFacts instance populated from the response body.
    """
    status = exc.response.status_code
    raw_body = exc.response.text
    provider_code: str | None = None
    provider_type: str | None = None
    message = f"{provider} request failed: HTTP {status}"
    try:
        body = json.loads(raw_body)
        if isinstance(body, dict):
            error_obj = body.get("error") or {}
            if isinstance(error_obj, dict):
                provider_type = error_obj.get("type")
                raw_code = error_obj.get("code")
                provider_code = str(raw_code) if raw_code is not None else None
                text = error_obj.get("message") or ""
                if text:
                    message = f"{provider}: {text}"
    except (ValueError, KeyError):
        pass
    return ProviderErrorFacts(
        message=message,
        http_status=status,
        provider_code=provider_code,
        provider_type=provider_type,
        raw_body=raw_body,
    )
