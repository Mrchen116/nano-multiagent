"""FastAPI application for the independent IM service."""

from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

from IM.infra.db import connect, initialize_schema
from IM.models import Conversation, Message, User
from IM.repositories import ConversationRepository, MessageRepository, UserRepository


class CreateUserRequest(BaseModel):
    """Request payload for creating a chat user."""

    username: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class UserResponse(BaseModel):
    """Serialized user object returned by API endpoints."""

    id: str
    username: str
    display_name: str
    created_at: str


class CreateConversationRequest(BaseModel):
    """Request payload for creating a conversation."""

    title: str = Field(min_length=1)
    participant_ids: list[str] = Field(min_length=1)


class ConversationResponse(BaseModel):
    """Serialized conversation object returned by API endpoints."""

    id: str
    title: str
    participant_ids: list[str]
    created_at: str


class CreateMessageRequest(BaseModel):
    """Request payload for creating a message."""

    sender_user_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class MessageResponse(BaseModel):
    """Serialized message object returned by API endpoints."""

    id: str
    conversation_id: str
    sender_user_id: str
    content: str
    delivery_status: str
    created_at: str


def create_app(*, db_path: Path | None = None) -> FastAPI:
    """Build a standalone IM FastAPI application.

    Args:
        db_path: Optional SQLite file path used by the IM service.

    Returns:
        FastAPI app with initialized storage and IM routes.

    Side Effects:
        Creates the SQLite file if missing and initializes schema at startup.
    """
    resolved_db_path = db_path or Path(os.getenv("IM_DB_PATH", "data/im_service.sqlite3"))

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        """Manage app-level SQLite connection lifecycle."""
        connection = connect(resolved_db_path)
        initialize_schema(connection)
        app_instance.state.connection = connection
        try:
            yield
        finally:
            connection.close()

    app = FastAPI(title="Independent IM Service", version="0.1.0", lifespan=lifespan)

    @app.post("/im/v1/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
    def create_user(payload: CreateUserRequest, request: Request) -> UserResponse:
        """Create a chat user persisted in SQLite."""
        repository = _get_user_repository(request)
        try:
            created = repository.create_user(
                username=payload.username,
                display_name=payload.display_name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return _to_user_response(created)

    @app.get("/im/v1/users", response_model=list[UserResponse])
    def list_users(request: Request) -> list[UserResponse]:
        """List all users in creation order."""
        repository = _get_user_repository(request)
        return [_to_user_response(item) for item in repository.list_users()]

    @app.post(
        "/im/v1/conversations",
        response_model=ConversationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_conversation(
        payload: CreateConversationRequest,
        request: Request,
    ) -> ConversationResponse:
        """Create a conversation with validated participants."""
        repository = _get_conversation_repository(request)
        try:
            created = repository.create_conversation(
                title=payload.title,
                participant_ids=payload.participant_ids,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return _to_conversation_response(created)

    @app.get("/im/v1/conversations", response_model=list[ConversationResponse])
    def list_conversations(request: Request) -> list[ConversationResponse]:
        """List all conversations with participant membership."""
        repository = _get_conversation_repository(request)
        return [_to_conversation_response(item) for item in repository.list_conversations()]

    @app.post(
        "/im/v1/conversations/{conversation_id}/messages",
        response_model=MessageResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_message(
        conversation_id: str,
        payload: CreateMessageRequest,
        request: Request,
    ) -> MessageResponse:
        """Create a message in a conversation."""
        repository = _get_message_repository(request)
        try:
            created = repository.create_message(
                conversation_id=conversation_id,
                sender_user_id=payload.sender_user_id,
                content=payload.content,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return _to_message_response(created)

    @app.get(
        "/im/v1/conversations/{conversation_id}/messages",
        response_model=list[MessageResponse],
    )
    def list_messages(conversation_id: str, request: Request) -> list[MessageResponse]:
        """List messages for one conversation in insertion order."""
        repository = _get_message_repository(request)
        return [
            _to_message_response(item)
            for item in repository.list_messages(conversation_id=conversation_id)
        ]

    return app


def _to_user_response(user: User) -> UserResponse:
    """Convert domain user to API response model."""
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
    )


def _to_conversation_response(conversation: Conversation) -> ConversationResponse:
    """Convert domain conversation to API response model."""
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        participant_ids=conversation.participant_ids,
        created_at=conversation.created_at,
    )


def _to_message_response(message: Message) -> MessageResponse:
    """Convert domain message to API response model."""
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_user_id=message.sender_user_id,
        content=message.content,
        delivery_status=message.delivery_status,
        created_at=message.created_at,
    )


def _get_user_repository(request: Request) -> UserRepository:
    """Build user repository from app-scoped database connection."""
    return UserRepository(request.app.state.connection)


def _get_conversation_repository(request: Request) -> ConversationRepository:
    """Build conversation repository from app-scoped database connection."""
    return ConversationRepository(request.app.state.connection)


def _get_message_repository(request: Request) -> MessageRepository:
    """Build message repository from app-scoped database connection."""
    return MessageRepository(request.app.state.connection)


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("IM.app:app", host="127.0.0.1", port=8011, reload=False)
