"""run_status.error.kind 投影的可观察分类。"""

from agent.core.errors import ModelError
from agent.core.runs.error_kind import project_model_error_kind


def _error(
    message: str,
    *,
    status_code: int | None = None,
    provider_code: str | None = None,
    provider_type: str | None = None,
) -> ModelError:
    details: dict[str, object] = {}
    if status_code is not None:
        details["status_code"] = status_code
    if provider_code is not None:
        details["provider_code"] = provider_code
    if provider_type is not None:
        details["provider_type"] = provider_type
    return ModelError(message, details=details)


def test_quota_from_balance_text() -> None:
    assert project_model_error_kind(_error("insufficient balance")) == "quota"


def test_quota_from_chinese_billing_text() -> None:
    assert project_model_error_kind(_error("账户欠费，额度不足")) == "quota"


def test_credit_card_required_is_not_quota() -> None:
    assert (
        project_model_error_kind(_error("credit card required for billing")) == "other"
    )


def test_rate_limit_from_429() -> None:
    assert project_model_error_kind(_error("slow down", status_code=429)) == "rate_limit"


def test_auth_from_invalid_api_key() -> None:
    assert (
        project_model_error_kind(
            _error("nope", status_code=401, provider_code="invalid_api_key")
        )
        == "auth"
    )


def test_auth_from_403() -> None:
    assert project_model_error_kind(_error("forbidden", status_code=403)) == "auth"


def test_timeout_from_message() -> None:
    assert project_model_error_kind(_error("request timeout")) == "timeout"


def test_overload_from_5xx() -> None:
    assert project_model_error_kind(_error("bad gateway", status_code=503)) == "overload"


def test_overload_from_overloaded_text() -> None:
    assert project_model_error_kind(_error("model is overloaded")) == "overload"


def test_context_length_from_provider_code() -> None:
    assert (
        project_model_error_kind(
            _error("too long", provider_code="context_length_exceeded")
        )
        == "context_length"
    )


def test_context_length_from_window_text() -> None:
    assert (
        project_model_error_kind(_error("exceeds the context window")) == "context_length"
    )


def test_unknown_maps_to_other() -> None:
    assert project_model_error_kind(_error("tool exploded")) == "other"
