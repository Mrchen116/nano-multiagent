from typing import Any, Mapping


class NanoMultiAgentError(Exception):
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
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


class ModelError(NanoMultiAgentError):
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
