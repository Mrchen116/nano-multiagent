from typing import Any

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.runs.registry import RunsRegistry
from nano_multiagent.server.sse import EventStreamHub, StreamEvent, encode_sse_event
from nano_multiagent.session.models import Session
from nano_multiagent.session.service import SessionService

from ..auth import require_bearer_auth
from ..deps import (
    APIError,
    get_agent_runtime,
    get_event_stream_hub,
    get_runs_registry,
    get_session_service,
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
