"""Shared registered-model request-body merging for provider clients."""

from __future__ import annotations

from dataclasses import replace

from agent.core.llm.interfaces import LLMGenerateRequest
from agent.core.llm.model_registry import resolve_model_metadata


def merge_registered_model_body(
    provider: str, request: LLMGenerateRequest
) -> LLMGenerateRequest:
    """Merge static registered model fields below request-specific fields.

    Args:
        provider: Registered provider family used for model lookup.
        request: Normalized request whose ``extra_body`` has higher priority.

    Returns:
        The original request when no static body exists, otherwise a replacement
        carrying the effective merged body.
    """

    static_body = resolve_model_metadata(provider, request.model).extra_request_body
    if not static_body:
        return request
    merged = dict(static_body)
    if request.extra_body:
        merged.update(request.extra_body)
    return replace(request, extra_body=merged)


__all__ = ["merge_registered_model_body"]
