"""FastAPI dependency accessors and canonical API error envelope model."""

from fastapi import Request

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.hooks.registry import HookRegistry
from nano_multiagent.runs.registry import RunsRegistry
from nano_multiagent.platform.http_api.sse import EventStreamHub
from nano_multiagent.platform.persistence.session.service import SessionService
from nano_multiagent.platform.tools.registry import ToolRegistry


class APIError(Exception):
    """Represent an API-facing error that maps directly to HTTP response fields.

    Notes:
        `code/message/retryable` are serialized to the server error envelope
        in `server.app` so route handlers can express domain failures without
        manually building response payloads.
    """

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
    """Return the session service bound during app bootstrap."""
    return request.app.state.session_service  # type: ignore[no-any-return]


def get_agent_runtime(request: Request) -> AgentRuntime:
    """Return the runtime instance stored on application state."""
    return request.app.state.agent_runtime  # type: ignore[no-any-return]


def get_tool_registry(request: Request) -> ToolRegistry:
    """Return the tool registry exposed to HTTP handlers."""
    return request.app.state.tool_registry  # type: ignore[no-any-return]


def get_hook_registry(request: Request) -> HookRegistry:
    """Return the hook registry used by hook inspection routes."""
    return request.app.state.hook_registry  # type: ignore[no-any-return]


def get_runs_registry(request: Request) -> RunsRegistry:
    """Return async run registry for run polling/cancel endpoints."""
    return request.app.state.runs_registry  # type: ignore[no-any-return]


def get_event_stream_hub(request: Request) -> EventStreamHub:
    """Return SSE hub shared by session/global event streaming handlers."""
    return request.app.state.event_stream_hub  # type: ignore[no-any-return]


def get_trace_id(request: Request) -> str:
    """Read request trace id propagated by middleware.

    Returns:
        Existing trace id, or a stable placeholder when middleware was bypassed.
    """
    trace_id = getattr(request.state, "trace_id", "")
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    return "unknown-trace"
