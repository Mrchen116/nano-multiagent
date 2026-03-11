"""Conversation routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from IM.api.deps import get_web_im_service
from IM.application.web_im_service import WebIMService
from IM.domain.models import Conversation

router = APIRouter(tags=["web-im"])


class CreateConversationRequest(BaseModel):
    """Request payload for creating a conversation."""

    title: str = Field(min_length=1)
    participant_ids: list[str] = Field(min_length=1)


class ConversationResponse(BaseModel):
    """Serialized conversation object returned by API endpoints."""

    id: str
    title: str
    participant_ids: list[str]
    type: str
    owner_id: str
    is_pinned: bool
    is_muted: bool
    unread_count: int
    last_message_at: str | None
    config_profile_version: int | None
    created_at: str


def to_conversation_response(conversation: Conversation) -> ConversationResponse:
    """Convert domain conversation to API response model."""
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        participant_ids=conversation.participant_ids,
        type=conversation.type,
        owner_id=conversation.owner_id,
        is_pinned=conversation.is_pinned,
        is_muted=conversation.is_muted,
        unread_count=conversation.unread_count,
        last_message_at=conversation.last_message_at,
        config_profile_version=conversation.config_profile_version,
        created_at=conversation.created_at,
    )


@router.post(
    "/im/v1/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: CreateConversationRequest,
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Create a conversation with validated participants."""
    try:
        created = service.create_conversation(
            title=payload.title,
            participant_ids=payload.participant_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_conversation_response(created)


@router.get("/im/v1/conversations", response_model=list[ConversationResponse])
def list_conversations(
    service: WebIMService = Depends(get_web_im_service),
) -> list[ConversationResponse]:
    """List all conversations with participant membership."""
    return [to_conversation_response(item) for item in service.list_conversations()]
