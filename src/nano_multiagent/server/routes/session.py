from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from nano_multiagent.session.models import Session
from nano_multiagent.session.service import SessionService

from ..auth import require_bearer_auth
from ..deps import APIError, get_session_service

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


@router.post("/{session_id}/messages")
def send_message_placeholder() -> None:
    raise APIError(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        code="not_implemented",
        message="sync messages endpoint is not implemented yet",
        retryable=False,
    )


def _to_session_response(session: Session) -> SessionResponse:
    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
    )
