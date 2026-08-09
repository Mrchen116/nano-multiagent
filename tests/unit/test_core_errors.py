from agent.core.errors import CompactionError, ModelError, PolicyViolation, ToolError


def test_model_error_is_typed_and_retryable() -> None:
    error = ModelError("upstream timeout")

    assert error.code == "model_error"
    assert error.retryable is True
    assert error.message == "upstream timeout"


def test_tool_error_carries_tool_context() -> None:
    error = ToolError("tool failed", tool_name="bash", call_id="call_123")

    assert error.code == "tool_error"
    assert error.retryable is False
    assert error.details["tool_name"] == "bash"
    assert error.details["call_id"] == "call_123"


def test_policy_violation_is_not_retryable() -> None:
    error = PolicyViolation("max turns exceeded")

    assert error.code == "policy_violation"
    assert error.retryable is False


def test_compaction_error_preserves_trigger_count_and_root_causes() -> None:
    overflow = ModelError(
        "maximum context length exceeded",
        details={"status_code": 400},
    )
    error = CompactionError(
        trigger="overflow",
        failure_kind="persistence",
        consecutive_failures=2,
        cause=OSError("disk unavailable"),
        overflow_cause=overflow,
    )

    payload = error.to_dict()

    assert payload["code"] == "compaction_failed"
    assert payload["retryable"] is True
    assert payload["details"] == {
        "trigger": "overflow",
        "failure_kind": "persistence",
        "consecutive_failures": 2,
        "cause": {"type": "OSError", "message": "disk unavailable"},
        "overflow_cause": overflow.to_dict(),
    }
