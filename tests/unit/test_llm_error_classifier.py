"""Tests for provider-neutral error facts extraction and retryability classifier.

bugfix-402-M2: unified error semantics.
Permanent errors fail-fast; transient/unknown errors default to retryable.
"""

from __future__ import annotations

import pytest

from agent.core.llm.error_classifier import (
    ProviderErrorFacts,
    classify_retryability,
)


# ---------------------------------------------------------------------------
# ProviderErrorFacts construction
# ---------------------------------------------------------------------------


def test_facts_minimal() -> None:
    facts = ProviderErrorFacts(message="upstream error")
    assert facts.message == "upstream error"
    assert facts.http_status is None
    assert facts.provider_code is None
    assert facts.provider_type is None
    assert facts.raw_body is None


def test_facts_full() -> None:
    facts = ProviderErrorFacts(
        message="rate limit exceeded",
        http_status=429,
        provider_code="rate_limit_exceeded",
        provider_type="rate_limit_error",
        raw_body='{"error":{"type":"rate_limit_error"}}',
    )
    assert facts.http_status == 429
    assert facts.provider_code == "rate_limit_exceeded"


# ---------------------------------------------------------------------------
# Permanent errors → retryable=False
# ---------------------------------------------------------------------------


class TestPermanentErrors:
    """Explicit permanent errors must fail-fast."""

    def test_invalid_api_key_type(self) -> None:
        facts = ProviderErrorFacts(
            message="invalid api key",
            http_status=401,
            provider_type="authentication_error",
        )
        assert classify_retryability(facts) is False

    def test_auth_error_code(self) -> None:
        facts = ProviderErrorFacts(
            message="invalid key",
            http_status=401,
            provider_code="invalid_api_key",
        )
        assert classify_retryability(facts) is False

    def test_permission_denied_type(self) -> None:
        facts = ProviderErrorFacts(
            message="permission denied",
            http_status=403,
            provider_type="permission_error",
        )
        assert classify_retryability(facts) is False

    def test_not_found_status(self) -> None:
        """Model/resource not found is permanent."""
        facts = ProviderErrorFacts(
            message="model not found",
            http_status=404,
            provider_type="not_found_error",
        )
        assert classify_retryability(facts) is False

    def test_not_found_code(self) -> None:
        facts = ProviderErrorFacts(
            message="model does not exist",
            http_status=404,
            provider_code="model_not_found",
        )
        assert classify_retryability(facts) is False

    def test_invalid_request_type(self) -> None:
        """Parameter/format errors are permanent."""
        facts = ProviderErrorFacts(
            message="invalid request",
            http_status=400,
            provider_type="invalid_request_error",
        )
        assert classify_retryability(facts) is False

    def test_context_length_exceeded(self) -> None:
        """Context window exceeded is permanent — caller must truncate."""
        facts = ProviderErrorFacts(
            message="context length exceeded",
            http_status=400,
            provider_code="context_length_exceeded",
        )
        assert classify_retryability(facts) is False

    def test_unsupported_operation(self) -> None:
        facts = ProviderErrorFacts(
            message="unsupported operation",
            http_status=400,
            provider_type="unsupported_operation",
        )
        assert classify_retryability(facts) is False

    def test_text_auth_error_high_confidence(self) -> None:
        """High-confidence text match: authentication / authorization failure."""
        facts = ProviderErrorFacts(
            message="Authentication failed: invalid credentials",
            http_status=401,
        )
        assert classify_retryability(facts) is False

    def test_text_invalid_parameter(self) -> None:
        facts = ProviderErrorFacts(
            message="Invalid parameter: max_tokens must be positive",
            http_status=400,
        )
        assert classify_retryability(facts) is False

    def test_structured_permanent_type_overrides_billing_text(self) -> None:
        """bugfix-402-M6: invalid_request_error is permanent even when body says 'credit card required'.

        Previously billing-quota text was checked before structured permanent
        types, so 'credit card required' + invalid_request_error was retryable.
        Structured permanent type now takes priority.
        """
        facts = ProviderErrorFacts(
            message="Your payment method is invalid: credit card required",
            http_status=400,
            provider_type="invalid_request_error",
        )
        assert classify_retryability(facts) is False

    def test_structured_permanent_code_overrides_billing_text(self) -> None:
        """bugfix-402-M6: permanent provider_code beats billing text."""
        facts = ProviderErrorFacts(
            message="invalid api key — please check your credit balance",
            http_status=401,
            provider_code="invalid_api_key",
        )
        assert classify_retryability(facts) is False

    def test_authentication_facts_override_insufficient_permissions_text(self) -> None:
        """Explicit auth facts stay permanent despite quota-like wording."""
        facts = ProviderErrorFacts(
            message="insufficient permissions for this API key",
            http_status=401,
            provider_code="invalid_api_key",
            provider_type="authentication_error",
        )
        assert classify_retryability(facts) is False

    def test_bare_credit_word_without_billing_context(self) -> None:
        """bugfix-402-M6: bare 'credit' no longer matches; requires compound phrase."""
        facts = ProviderErrorFacts(
            message="credit card required to activate account",
            http_status=400,
            provider_type="invalid_request_error",
        )
        assert classify_retryability(facts) is False

    def test_credit_balance_compound_still_retryable(self) -> None:
        """bugfix-402-M6: 'insufficient credit' and 'credit balance' stay retryable."""
        facts = ProviderErrorFacts(
            message="Insufficient credit: please top up your credit balance",
            http_status=402,
        )
        assert classify_retryability(facts) is True


# ---------------------------------------------------------------------------
# Transient / unknown errors → retryable=True
# ---------------------------------------------------------------------------


class TestRetryableErrors:
    """Transient and ambiguous errors must default to retryable."""

    def test_network_timeout(self) -> None:
        facts = ProviderErrorFacts(message="connection timed out")
        assert classify_retryability(facts) is True

    def test_rate_limit_429(self) -> None:
        facts = ProviderErrorFacts(
            message="rate limit exceeded",
            http_status=429,
            provider_type="rate_limit_error",
        )
        assert classify_retryability(facts) is True

    def test_server_error_500(self) -> None:
        facts = ProviderErrorFacts(
            message="internal server error",
            http_status=500,
        )
        assert classify_retryability(facts) is True

    def test_server_overloaded_529(self) -> None:
        facts = ProviderErrorFacts(
            message="api is currently overloaded",
            http_status=529,
        )
        assert classify_retryability(facts) is True

    def test_quota_exceeded_kimi_4xx(self) -> None:
        """Kimi / volcano billing errors are 4xx but must be retried (quota replenishes)."""
        facts = ProviderErrorFacts(
            message="Your account balance is insufficient.",
            http_status=402,
            provider_code="InsufficientBalance",
        )
        assert classify_retryability(facts) is True

    def test_billing_text_match(self) -> None:
        facts = ProviderErrorFacts(
            message="You've reached your usage limit for this billing cycle.",
            http_status=429,
        )
        assert classify_retryability(facts) is True

    def test_overdue_text_match(self) -> None:
        facts = ProviderErrorFacts(
            message="Account overdue. Please top up.",
            http_status=403,
        )
        # Even though 403 maps to permission, "overdue" is billing → retryable
        assert classify_retryability(facts) is True

    def test_unknown_4xx_defaults_retryable(self) -> None:
        """Unknown 4xx without recognized permanent type → default retryable."""
        facts = ProviderErrorFacts(
            message="something went wrong",
            http_status=418,
        )
        assert classify_retryability(facts) is True

    def test_no_http_status_defaults_retryable(self) -> None:
        """Transport errors with no HTTP status → default retryable."""
        facts = ProviderErrorFacts(message="connection reset by peer")
        assert classify_retryability(facts) is True

    def test_truncated_stream_retryable(self) -> None:
        """Stream ended without terminal event is a transient truncation."""
        facts = ProviderErrorFacts(
            message="stream ended without terminal event",
        )
        assert classify_retryability(facts) is True

    def test_volcano_rate_limit_4xx(self) -> None:
        """Volcano Ark throttling — text says 'rate limit' even if code is 4xx."""
        facts = ProviderErrorFacts(
            message="You have exceeded your request rate limit.",
            http_status=429,
            provider_code="Throttling.RateQuota",
        )
        assert classify_retryability(facts) is True


# ---------------------------------------------------------------------------
# Provider-name independence
# ---------------------------------------------------------------------------


def test_classifier_has_no_provider_name_branch() -> None:
    """Classifier must not care about provider name.

    Same facts classified identically regardless of which provider sent them.
    This is enforced by the classifier signature: no provider name parameter.
    """
    import inspect

    sig = inspect.signature(classify_retryability)
    param_names = list(sig.parameters.keys())
    assert "provider" not in param_names, (
        f"classify_retryability must not accept a 'provider' parameter; "
        f"got: {param_names}"
    )
