from fastapi import Request

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.session.service import SessionService
from nano_multiagent.tools.registry import ToolRegistry


class APIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service  # type: ignore[no-any-return]


def get_agent_runtime(request: Request) -> AgentRuntime:
    return request.app.state.agent_runtime  # type: ignore[no-any-return]


def get_tool_registry(request: Request) -> ToolRegistry:
    return request.app.state.tool_registry  # type: ignore[no-any-return]


def get_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", "")
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    return "unknown-trace"
