from typing import Any

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nano_multiagent.agent.compaction.types import CompactionSettings
from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.runs.registry import RunsRegistry
from nano_multiagent.server.sse import EventStreamHub, StreamEvent, encode_sse_event
from nano_multiagent.session.models import Session
from nano_multiagent.session.service import SessionService
from nano_multiagent.tools.registry import ToolRegistry

from ..auth import require_bearer_auth
from ..deps import (
    APIError,
    get_agent_runtime,
    get_event_stream_hub,
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


class CreateSessionRequest(BaseModel):
    title: str | None = None
    metadata: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    limit: int
    offset: int
    has_more: bool


class SendMessageRequest(BaseModel):
    message_id: str | None = None
    parts: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None
    stream: bool = False


class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str


class SendMessageResponse(BaseModel):
    session_id: str
    turn_id: str
    message: MessageResponse
    completed: bool
    stop_reason: str


class SendMessageAsyncRequest(BaseModel):
    message_id: str | None = None
    parts: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None


class SendMessageAsyncResponse(BaseModel):
    run_id: str
    session_id: str
    status: str


class ToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class SessionToolsResponse(BaseModel):
    session_id: str
    tools: list[ToolDescriptor]


class CompactResultResponse(BaseModel):
    reason: str
    entry_id: str
    first_kept_event_id: str
    summary: str
    dropped_event_ids: list[str]
    kept_event_ids: list[str]


class CompactSessionResponse(BaseModel):
    session_id: str
    compacted: bool
    result: CompactResultResponse | None


class ContextBudgetResponse(BaseModel):
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
    session = session_service.create_session(title=payload.title, metadata=payload.metadata)
    return _to_session_response(session)


@router.get("", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session_service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
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
) -> ContextBudgetResponse:
    if session_service.get_session(session_id) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    messages = session_service.manager.list_turn_messages(session_id)
    used_tokens = _estimate_context_tokens(messages)
    max_tokens = _resolve_context_window(runtime)
    remaining_tokens = max(max_tokens - used_tokens, 0)
    usage_ratio = float(used_tokens) / float(max_tokens)
    return ContextBudgetResponse(
        session_id=session_id,
        used_tokens=used_tokens,
        max_tokens=max_tokens,
        remaining_tokens=remaining_tokens,
        usage_ratio=usage_ratio,
    )


@router.post("/{session_id}/messages", response_model=SendMessageResponse)
def send_message(
    session_id: str,
    payload: SendMessageRequest,
    runtime=Depends(get_agent_runtime),
) -> SendMessageResponse:
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
    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
    )


def _to_message_response(result: TurnResult) -> dict[str, Any]:
    message = _select_assistant_message(result.messages)
    return {
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


def _select_assistant_message(messages: tuple[Message, ...]) -> Message:
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
    for item in events:
        yield encode_sse_event(event_id=item.event_id, event=item.event, data=item.data)


def _resolve_context_window(runtime: object) -> int:
    default_context_window = CompactionSettings().context_window
    settings = getattr(runtime, "_compaction_settings", None)
    context_window = getattr(settings, "context_window", None)
    if isinstance(context_window, bool):
        return default_context_window
    if isinstance(context_window, int) and context_window > 0:
        return context_window
    return default_context_window


def _estimate_context_tokens(history: tuple[Message, ...]) -> int:
    total = 0
    for message in history:
        total += _estimate_text_tokens(message.content)
    total += 4 + len(history) * 2
    return total


def _estimate_text_tokens(text: str) -> int:
    normalized = " ".join(text.split())
    if not normalized:
        return 1
    return max(1, (len(normalized) + 7) // 8)
