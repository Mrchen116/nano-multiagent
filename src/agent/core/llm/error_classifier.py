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

from dataclasses import dataclass


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
# conditions that *can* resolve without caller changes.  Checked after
# structured permanent signals (provider_type/provider_code) so that e.g.
# invalid_request_error with "credit card required" body is still permanent.
# Case-insensitive.
# bugfix-402-M6: "credit" replaced with precise compound phrases to avoid
# matching "credit card required" (which is a permanent billing-setup error
# that a retry cannot fix), while retaining "insufficient credit",
# "credit balance", "credit limit", etc. which are transient quota conditions.
_BILLING_QUOTA_FRAGMENTS: tuple[str, ...] = (
    "billing",
    "balance",
    "insufficient",
    "overdue",
    "quota",
    "rate limit",
    "rate_limit",
    "usage limit",
    "insufficient credit",
    "credit balance",
    "credit limit",
    "credit expired",
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

    Classification priority (highest wins):
      1. Structured permanent provider_type (e.g. invalid_request_error) → permanent
      2. Structured permanent provider_code (e.g. invalid_api_key) → permanent
      3. Billing/quota/rate-limit text → retryable (overrides permanent HTTP status)
      4. Permanent HTTP status (401/403/404/…) → permanent
      5. High-confidence permanent text → permanent
      6. Everything else → retryable (default)

    bugfix-402-M6: structured permanent signals (provider_type/provider_code)
    now take priority over billing-quota text so that a response whose body
    mentions billing-adjacent words but carries an explicit permanent type
    (e.g. invalid_request_error + "credit card required") is correctly
    classified as permanent rather than retryable.
    """
    msg_lower = facts.message.lower()

    # Priority 1: structured provider_type signals an explicit permanent error.
    # Checked first so that e.g. invalid_request_error is permanent even when
    # the message body contains billing-adjacent words.
    if facts.provider_type and facts.provider_type in _PERMANENT_PROVIDER_TYPES:
        return False

    # Priority 2: structured provider_code signals an explicit permanent error.
    if facts.provider_code and facts.provider_code in _PERMANENT_PROVIDER_CODES:
        return False

    # Priority 3 (billing/quota): checked before HTTP status so that a 403
    # "overdue" or 429 "quota" response stays retryable despite the status.
    if any(fragment in msg_lower for fragment in _BILLING_QUOTA_FRAGMENTS):
        return True

    # Priority 4: HTTP status that is unambiguously permanent (401/403/404/…)
    if facts.http_status in _PERMANENT_HTTP_STATUSES:
        return False

    # Priority 5: high-confidence permanent text when no structured signal
    if any(fragment in msg_lower for fragment in _PERMANENT_TEXT_FRAGMENTS):
        return False

    # Priority 6: transient or unknown — default retryable
    return True
