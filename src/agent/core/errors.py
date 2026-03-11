"""Domain errors with stable machine-readable semantics."""

from typing import Any, Mapping


class NanoMultiAgentError(Exception):
    """Represent a structured runtime error.

    Args:
        message: Human-readable error description.
        code: Stable code consumed by API and clients.
        retryable: Whether callers may retry safely.
        details: Extra diagnostic fields for observability.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error for transport over HTTP/event channels.

        Returns:
            A JSON-serializable error payload.
        """

        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


class ModelError(NanoMultiAgentError):
    """Wrap LLM provider failures with normalized error semantics."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="model_error",
            retryable=retryable,
            details=details,
        )


class ToolError(NanoMultiAgentError):
    """Wrap tool execution failures with call context."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str,
        call_id: str | None = None,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        merged_details = dict(details or {})
        merged_details["tool_name"] = tool_name
        if call_id is not None:
            merged_details["call_id"] = call_id
        super().__init__(
            message,
            code="tool_error",
            retryable=retryable,
            details=merged_details,
        )


class PolicyViolation(NanoMultiAgentError):
    """Signal runtime guardrail violations that should fail fast."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="policy_violation",
            retryable=False,
            details=details,
        )
