"""Session-scoped HTTP handlers covering message, SSE, tools, and compaction."""

from typing import Any

from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.core.agent.compaction.types import CompactionSettings
from agent.core.errors import ModelError
from agent.core.hooks.registry import HookRegistry
from agent.core.session.models import Session
from agent.core.types import Message, TurnResult
from agent.platform.hooks.session_usage import get_session_usage_snapshot
from agent.platform.http_api.sse import EventStreamHub, StreamEvent, encode_sse_event
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.registry import ToolRegistry
from agent.core.runs.registry import RunsRegistry

from ..auth import require_bearer_auth
from ..deps import (
    APIError,
    get_agent_runtime,
    get_event_stream_hub,
    get_hook_registry,
    get_runs_registry,
    get_session_service,
    get_tool_registry,
    get_trace_id,
)

router = APIRouter(
    prefix="/v1/sessions",
    tags=["sessions"],
    dependencies=[Depends(require_bearer_auth)],
)
# Ownership marker: tests assert exported routers come from the platform route module,
# even though the underlying APIRouter class itself lives in FastAPI.
router.__module__ = __name__

_CONTEXT_BUDGET_MAX_TOKENS = CompactionSettings().context_window


class CreateSessionRequest(BaseModel):
    """Payload for creating a new session container."""

    title: str | None = None
    metadata: dict[str, Any] | None = None
    workspace_root: str | None = None


class SessionResponse(BaseModel):
    """Canonical session summary returned by session lookup APIs."""

    session_id: str
    status: str
    created_at: str


class SessionListResponse(BaseModel):
    """Paginated session list response."""

    items: list[SessionResponse]
    limit: int
    offset: int
    has_more: bool


class SendMessageRequest(BaseModel):
    """Synchronous message submission payload."""

    message_id: str | None = None
    parts: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None
    stream: bool = False


class MessageResponse(BaseModel):
    """Assistant message projection for sync response payload."""

    message_id: str
    role: str
    content: str


class UsageResponse(BaseModel):
    """Canonical per-turn model usage counters."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class SendMessageResponse(BaseModel):
    """Synchronous turn execution response payload."""

    session_id: str
    turn_id: str
    message: MessageResponse
    completed: bool
    stop_reason: str
    usage: UsageResponse | None = None


class SendMessageAsyncRequest(BaseModel):
    """Asynchronous message submission payload."""

    message_id: str | None = None
    parts: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None


class SendMessageAsyncResponse(BaseModel):
    """Accepted async run record reference."""

    run_id: str
    session_id: str
    status: str


class ToolDescriptor(BaseModel):
    """Tool descriptor visible to one authenticated session."""

    name: str
    description: str
    input_schema: dict[str, Any]


class SessionToolsResponse(BaseModel):
    """Response envelope for session tool listing."""

    session_id: str
    tools: list[ToolDescriptor]


class CompactResultResponse(BaseModel):
    """Compaction details when session history was compacted."""

    reason: str
    entry_id: str
    first_kept_event_id: str
    summary: str
    dropped_event_ids: list[str]
    kept_event_ids: list[str]


class CompactSessionResponse(BaseModel):
    """Response envelope for manual compaction request."""

    session_id: str
    compacted: bool
    result: CompactResultResponse | None


class ContextBudgetResponse(BaseModel):
    """Session context budget snapshot used by CLI hints."""

    session_id: str
    used_tokens: int
    max_tokens: int
    remaining_tokens: int
    usage_ratio: float


@router.post("", status_code=201, response_model=SessionResponse)
def create_session(
    payload: CreateSessionRequest,
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Create one session via HTTP boundary."""
    try:
        session = session_service.create_session(
            title=payload.title,
            metadata=_build_session_metadata(metadata=payload.metadata, workspace_root=payload.workspace_root),
        )
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    return _to_session_response(session)


@router.get("", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session_service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    """List sessions with offset pagination semantics."""
    sessions, has_more = session_service.list_sessions(limit=limit, offset=offset)
    return SessionListResponse(
        items=[_to_session_response(session) for session in sessions],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Fetch session by id or map missing session to HTTP 404."""
    session = session_service.get_session(session_id)
    if session is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )
    return _to_session_response(session)


@router.get("/{session_id}/tools", response_model=SessionToolsResponse)
def list_session_tools(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> SessionToolsResponse:
    """List available tools for one session after existence check."""
    if session_service.get_session(session_id) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    return SessionToolsResponse(
        session_id=session_id,
        tools=[
            ToolDescriptor(
                name=spec.name,
                description=spec.description,
                input_schema=dict(spec.input_schema),
            )
            for spec in registry.list_specs()
        ],
    )


@router.post("/{session_id}:compact", response_model=CompactSessionResponse)
def compact_session(
    session_id: str,
    payload: dict[str, Any],
    session_service: SessionService = Depends(get_session_service),
    runtime=Depends(get_agent_runtime),
) -> CompactSessionResponse:
    """Trigger manual compaction and return compaction metadata when applied."""
    del payload
    if session_service.get_session(session_id) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    try:
        result = runtime.compact(session_id)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc

    if result is None:
        return CompactSessionResponse(session_id=session_id, compacted=False, result=None)

    return CompactSessionResponse(
        session_id=session_id,
        compacted=True,
        result=CompactResultResponse(
            reason=result.reason.value,
            entry_id=result.entry_id,
            first_kept_event_id=result.first_kept_event_id,
            summary=result.summary,
            dropped_event_ids=list(result.dropped_event_ids),
            kept_event_ids=list(result.kept_event_ids),
        ),
    )


@router.get("/{session_id}/context-budget", response_model=ContextBudgetResponse)
def get_context_budget(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    runtime=Depends(get_agent_runtime),
    hook_registry: HookRegistry = Depends(get_hook_registry),
) -> ContextBudgetResponse:
    """Return session context usage for user-facing budget hints."""
    if session_service.get_session(session_id) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    max_tokens = _resolve_context_window(runtime)
    usage_snapshot = get_session_usage_snapshot(registry=hook_registry, session_id=session_id)
    if usage_snapshot is not None:
        used_tokens = min(max(usage_snapshot.last_total_tokens, 0), max_tokens)
    else:
        used_tokens = 0
    remaining_tokens = max(max_tokens - used_tokens, 0)
    usage_ratio = float(used_tokens) / float(max_tokens)
    return ContextBudgetResponse(
        session_id=session_id,
        used_tokens=used_tokens,
        max_tokens=max_tokens,
        remaining_tokens=remaining_tokens,
        usage_ratio=usage_ratio,
    )


@router.post("/{session_id}/messages", response_model=SendMessageResponse, response_model_exclude_none=True)
def send_message(
    session_id: str,
    payload: SendMessageRequest,
    runtime=Depends(get_agent_runtime),
) -> SendMessageResponse:
    """Execute one synchronous turn and normalize runtime errors to HTTP codes."""
    if payload.stream:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message="sync endpoint does not support stream=true",
            retryable=False,
        )

    try:
        result = runtime.run(session_id, payload.parts, stream=False)
    except ValueError as exc:
        # Preserve 404 vs 400 split so CLI can present actionable guidance.
        message = str(exc)
        if message.startswith("session does not exist:"):
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="session_not_found",
                message=message,
                retryable=False,
            ) from exc
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=message,
            retryable=False,
        ) from exc
    except ModelError as exc:
        # Provider/model upstream failures are surfaced as 502 gateway errors.
        raise APIError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
        ) from exc

    return SendMessageResponse(**_to_message_response(result))


@router.post("/{session_id}/messages:async", status_code=202, response_model=SendMessageAsyncResponse)
def send_message_async(
    session_id: str,
    payload: SendMessageAsyncRequest,
    request: Request,
    runs: RunsRegistry = Depends(get_runs_registry),
) -> SendMessageAsyncResponse:
    """Submit an async run and return polling handle (`run_id`)."""
    del payload.message_id
    del payload.model
    try:
        record = runs.submit(
            session_id=session_id,
            parts=payload.parts,
            trace_id=get_trace_id(request),
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith("session does not exist:"):
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="session_not_found",
                message=message,
                retryable=False,
            ) from exc
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=message,
            retryable=False,
        ) from exc
    return SendMessageAsyncResponse(
        run_id=record.run_id,
        session_id=record.session_id,
        status=record.status.value,
    )


@router.get("/{session_id}/events")
def stream_session_events(
    session_id: str,
    max_events: int = Query(default=20, ge=1, le=200),
    timeout_seconds: float = Query(default=0.25, ge=0.0, le=5.0),
    session_service: SessionService = Depends(get_session_service),
    event_hub: EventStreamHub = Depends(get_event_stream_hub),
) -> StreamingResponse:
    """Stream SSE events for one session with bounded long-poll semantics."""
    if session_service.get_session(session_id) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )
    return StreamingResponse(
        _iter_sse(
            event_hub.stream(
                session_id=session_id,
                max_events=max_events,
                timeout_seconds=timeout_seconds,
            )
        ),
        media_type="text/event-stream",
    )


def _to_session_response(session: Session) -> SessionResponse:
    """Convert domain session model to HTTP response schema."""
    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
    )


def _to_message_response(result: TurnResult) -> dict[str, Any]:
    """Convert runtime turn result into sync response payload."""
    message = _select_assistant_message(result.messages)
    payload: dict[str, Any] = {
        "session_id": result.session_id,
        "turn_id": result.turn_id,
        "message": {
            "message_id": message.message_id,
            "role": message.role,
            "content": message.content,
        },
        "completed": result.completed,
        "stop_reason": result.stop_reason,
    }
    if result.usage is not None:
        payload["usage"] = {
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
        }
    return payload


def _select_assistant_message(messages: tuple[Message, ...]) -> Message:
    """Select latest assistant message or raise contract violation error."""
    for message in reversed(messages):
        if message.role == "assistant":
            return message
    raise APIError(
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="invalid_runtime_response",
        message="runtime did not return assistant message",
        retryable=False,
    )


def _iter_sse(events: Iterator[StreamEvent]) -> Iterator[str]:
    """Encode hub events into text/event-stream payload chunks."""
    for item in events:
        yield encode_sse_event(event_id=item.event_id, event=item.event, data=item.data)


def _build_session_metadata(*, metadata: dict[str, Any] | None, workspace_root: str | None) -> dict[str, Any]:
    """Merge create-session metadata with normalized workspace root when provided."""
    merged: dict[str, Any] = dict(metadata or {})
    normalized_workspace_root = _normalize_workspace_root(workspace_root)
    if normalized_workspace_root is not None:
        merged["workspace_root"] = normalized_workspace_root
    return merged


def _normalize_workspace_root(workspace_root: str | None) -> str | None:
    """Normalize optional workspace root into an absolute filesystem path."""
    if workspace_root is None:
        return None
    normalized = workspace_root.strip()
    if not normalized:
        return None
    candidate = Path(normalized).expanduser()
    if not candidate.is_absolute():
        raise ValueError("workspace_root must be an absolute path or start with ~/")
    return str(candidate.resolve())


def _resolve_context_window(runtime: object) -> int:
    """Resolve user-facing context budget ceiling.

    Notes:
        Context budget tracks the same runtime `context_window` source used by
        compaction policy checks.
    """
    settings = getattr(runtime, "_compaction_settings", None)
    context_window = getattr(settings, "context_window", None)
    if isinstance(context_window, int) and not isinstance(context_window, bool) and context_window > 0:
        return context_window
    return _CONTEXT_BUDGET_MAX_TOKENS
