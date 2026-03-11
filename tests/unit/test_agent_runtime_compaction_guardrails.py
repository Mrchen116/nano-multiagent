from nano_multiagent.core.agent.runtime import _is_context_overflow_error
from nano_multiagent.core.errors import ModelError


def test_overflow_detector_accepts_http_413_with_token_marker() -> None:
    error = ModelError(
        "payload too large",
        details={
            "status_code": 413,
            "response": "too many tokens for model",
        },
    )

    assert _is_context_overflow_error(error) is True


def test_overflow_detector_rejects_non_overflow_errors() -> None:
    error = ModelError(
        "service unavailable",
        details={
            "status_code": 503,
            "response": "upstream timeout",
        },
    )

    assert _is_context_overflow_error(error) is False
