"""Dependency helpers for IM API routes."""

from fastapi import HTTPException, Request, status

from IM.application.bind_service import BindService
from IM.application.config_service import ConfigService
from IM.application.event_service import EventService
from IM.application.user_service import UserService
from IM.application.web_im_service import WebIMService
from IM.infra.repositories import AgentProfileRepository, BindRepository, ConversationRepository, EventRepository, MessageRepository, NodeRepository, UserRepository


def get_user_service(request: Request) -> UserService:
    """Build the user application service from app-scoped dependencies."""
    return UserService(users=UserRepository(request.app.state.connection))


def get_web_im_service(request: Request) -> WebIMService:
    """Build the Web IM application service from app-scoped dependencies."""
    return WebIMService(
        conversations=ConversationRepository(request.app.state.connection),
        messages=MessageRepository(request.app.state.connection),
    )


def get_event_service(request: Request) -> EventService:
    """Build the event application service from app-scoped dependencies."""
    return EventService(events=EventRepository(request.app.state.connection))


def get_config_service(request: Request) -> ConfigService:
    """Build the agent config application service from app-scoped dependencies."""
    return ConfigService(profiles=AgentProfileRepository(request.app.state.connection))


def get_bind_service(request: Request) -> BindService:
    """Build the account and bind application service from app-scoped dependencies."""
    return BindService(
        users=UserRepository(request.app.state.connection),
        nodes=NodeRepository(request.app.state.connection),
        binds=BindRepository(request.app.state.connection),
        profiles=AgentProfileRepository(request.app.state.connection),
        bind_base_url="https://im.local/bind/confirm",
    )


def assert_conversation_exists(request: Request, *, conversation_id: str) -> None:
    """Raise 404 when target conversation does not exist."""
    row = request.app.state.connection.execute(
        "SELECT 1 FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation_id not found",
        )
