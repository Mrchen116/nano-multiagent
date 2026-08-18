"""Project ModelError facts into a stable run_status.error.kind.

Gateway 只读这个 kind 决定是否换模型。不改 error_classifier 的 retryable 表。
"""

from __future__ import annotations

from typing import Any, Mapping

from agent.core.errors import ModelError

MODEL_ERROR_KINDS = (
    "quota",
    "overload",
    "timeout",
    "rate_limit",
    "auth",
    "context_length",
    "other",
)


def project_model_error_kind(error: ModelError) -> str:
    """Map one ModelError into a consumer-stable kind.

    Args:
        error: Provider failure raised from the LLM client.

    Returns:
        One of ``quota`` / ``overload`` / ``timeout`` / ``rate_limit`` /
        ``auth`` / ``context_length`` / ``other``.
    """

    details = error.details if isinstance(error.details, Mapping) else {}
    status = _status_code(details)
    provider_code = _lower_text(details.get("provider_code"))
    provider_type = _lower_text(details.get("provider_type"))
    message = _lower_text(error.message) or _lower_text(str(error))
    blob = " ".join(part for part in (provider_code, provider_type, message) if part)

    if _is_context_length(provider_code, blob):
        return "context_length"
    # 429 先于 quota：限流文案里偶尔带 quota 字样，产品仍按限流换模型。
    if status == 429 or "rate_limit" in blob or "rate limit" in blob:
        return "rate_limit"
    if _is_quota(blob):
        return "quota"
    if status in {401, 403} or _is_auth(provider_code, provider_type, blob):
        return "auth"
    if "timeout" in blob:
        return "timeout"
    if _is_overload(status, blob):
        return "overload"
    return "other"


def _status_code(details: Mapping[str, Any]) -> int | None:
    raw = details.get("status_code", details.get("http_status"))
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _lower_text(value: object) -> str:
    return str(value).strip().lower() if isinstance(value, str) else ""


def _is_context_length(provider_code: str, blob: str) -> bool:
    return (
        "context_length_exceeded" in provider_code
        or "context_length_exceeded" in blob
        or "context window" in blob
        or "context length" in blob
    )


def _is_quota(blob: str) -> bool:
    # 「credit card required」是开户/绑卡，不是欠费额度，不能当成可换模型的 quota。
    if "credit card required" in blob:
        return False
    return any(
        token in blob
        for token in ("欠费", "额度", "balance", "insufficient", "billing", "quota")
    )


def _is_auth(provider_code: str, provider_type: str, blob: str) -> bool:
    return (
        "invalid_api_key" in provider_code
        or "authentication" in provider_type
        or "authentication" in blob
        or "invalid_api_key" in blob
        or "invalid api key" in blob
    )


def _is_overload(status: int | None, blob: str) -> bool:
    if status is not None and status >= 500:
        return True
    return "overloaded" in blob or "overload" in blob
