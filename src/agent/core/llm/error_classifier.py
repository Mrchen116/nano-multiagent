"""Provider-neutral LLM error facts and retryability classifier.

bugfix-402-M2: All provider clients extract HTTP/SSE/transport failures into
ProviderErrorFacts and call classify_retryability() before constructing a
ModelError.  The classifier knows nothing about which provider sent the error —
it only inspects the structured fields and high-confidence text patterns.

Classification priority (from design.md decision 4):
  1. Local mapper/schema errors → permanent
  2. Explicit permanent structured code/type, or high-confidence text → permanent
  3. transport/timeout/5xx/429 → retryable
  4. quota/balance/billing/overdue text → retryable (even when HTTP is 4xx)
  5. Everything else → retryable (default)

The cost of a missed permanent classification (unnecessary retry) is an extra
delay before the same failure, not data loss.  The cost of a missed transient
classification (skipped retry) is a user-visible error that could have resolved
itself.  The asymmetry favours the retryable default.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProviderErrorFacts:
    """Structured facts extracted from an HTTP/SSE/transport provider error.

    All fields are optional; absent fields do not contribute to classification.

    Args:
        message: Human-readable error text from the provider (or transport).
        http_status: HTTP response status code, if available.
        provider_code: Structured error code from provider JSON body (e.g.
            ``"rate_limit_exceeded"``, ``"invalid_api_key"``).
        provider_type: Structured error type from provider JSON body (e.g.
            ``"authentication_error"``, ``"invalid_request_error"``).
        raw_body: Raw response body string, kept as a controlled diagnostic
            field; must not be exposed unconditionally in user-facing messages.
    """

    message: str
    http_status: int | None = None
    provider_code: str | None = None
    provider_type: str | None = None
    raw_body: str | None = None


# ---------------------------------------------------------------------------
# Internal classification tables
# ---------------------------------------------------------------------------

# provider_type values that are unambiguously permanent (no retry can help)
_PERMANENT_PROVIDER_TYPES: frozenset[str] = frozenset(
    {
        "authentication_error",
        "authorization_error",
        "permission_error",
        "not_found_error",
        "invalid_request_error",
        "unsupported_operation",
        "unsupported_operation_error",
        "invalid_model_error",
        "model_not_found",
    }
)

# provider_code values that are unambiguously permanent
_PERMANENT_PROVIDER_CODES: frozenset[str] = frozenset(
    {
        "invalid_api_key",
        "api_key_invalid",
        "unauthorized",
        "forbidden",
        "model_not_found",
        "context_length_exceeded",
        "invalid_request",
        "parameter_validation_failed",
        "unsupported_model",
    }
)

# HTTP status codes that are unambiguously permanent when not overridden by
# billing/quota text (priority 4 is checked before these are applied).
_PERMANENT_HTTP_STATUSES: frozenset[int] = frozenset({401, 403, 404, 405, 422})

# High-confidence substrings that indicate billing / quota / rate-limit
# conditions that *can* resolve without caller changes.  Checked before
# permanent HTTP status classification so that e.g. a 403 "overdue" response
# stays retryable.  Case-insensitive.
_BILLING_QUOTA_FRAGMENTS: tuple[str, ...] = (
    "billing",
    "balance",
    "insufficient",
    "overdue",
    "quota",
    "rate limit",
    "rate_limit",
    "usage limit",
    "credit",
    "throttl",
)

# High-confidence substrings indicating *permanent* failures when no structured
# code/type is present.  Only include strings that are unambiguous across all
# known providers.  Case-insensitive.
_PERMANENT_TEXT_FRAGMENTS: tuple[str, ...] = (
    "authentication failed",
    "invalid credentials",
    "invalid api key",
    "api key is invalid",
    "invalid parameter",
    "model does not exist",
    "model not found",
    "context window",
    "context length",
    "permission denied",
    "access denied",
    "not authorized",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_retryability(facts: ProviderErrorFacts) -> bool:
    """Return True when the error described by *facts* is worth retrying.

    Args:
        facts: Structured provider error facts.  All fields are optional.

    Returns:
        True if the caller should retry the request, False if the error is
        unambiguously permanent and retrying cannot help.
    """
    # Priority 4 (billing/quota) is checked first so that ambiguous HTTP
    # status codes (403, 429) used for billing/quota responses stay retryable.
    msg_lower = facts.message.lower()
    if any(fragment in msg_lower for fragment in _BILLING_QUOTA_FRAGMENTS):
        return True

    # Priority 2a: structured provider_type signals an explicit permanent error
    if facts.provider_type and facts.provider_type in _PERMANENT_PROVIDER_TYPES:
        return False

    # Priority 2b: structured provider_code signals an explicit permanent error
    if facts.provider_code and facts.provider_code in _PERMANENT_PROVIDER_CODES:
        return False

    # Priority 2c: HTTP status that is unambiguously permanent (401/403/404/…)
    if facts.http_status in _PERMANENT_HTTP_STATUSES:
        return False

    # Priority 2d: high-confidence permanent text when no structured signal
    if any(fragment in msg_lower for fragment in _PERMANENT_TEXT_FRAGMENTS):
        return False

    # Priority 3 / 5: transient or unknown — default retryable
    return True
