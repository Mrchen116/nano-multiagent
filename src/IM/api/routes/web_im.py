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


class UpdateConversationRequest(BaseModel):
    """Request payload for updating conversation metadata."""

    title: str | None = None
    is_pinned: bool | None = None
    is_muted: bool | None = None


class ConversationResponse(BaseModel):
    """Serialized conversation object returned by API endpoints."""

    id: str
    title: str
    participant_ids: list[str]
    type: str
    owner_id: str
    creator_id: str
    is_pinned: bool
    is_muted: bool
    unread_count: int
    last_message_at: str | None
    config_profile_version: int | None
    created_at: str


class ListConversationsResponse(BaseModel):
    """Envelope returned when listing conversations."""

    items: list[ConversationResponse]


def to_conversation_response(conversation: Conversation) -> ConversationResponse:
    """Convert domain conversation to API response model."""
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        participant_ids=conversation.participant_ids,
        type=conversation.type,
        owner_id=conversation.owner_id,
        creator_id=conversation.creator_id,
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


@router.get("/im/v1/conversations", response_model=ListConversationsResponse)
def list_conversations(
    service: WebIMService = Depends(get_web_im_service),
) -> ListConversationsResponse:
    """List all conversations with participant membership."""
    return ListConversationsResponse(
        items=[to_conversation_response(item) for item in service.list_conversations()]
    )


@router.get("/im/v1/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Return one conversation snapshot."""
    conversation = service.get_conversation(conversation_id=conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation_id not found")
    return to_conversation_response(conversation)


@router.patch("/im/v1/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str,
    payload: UpdateConversationRequest,
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Update mutable conversation metadata."""
    try:
        updated = service.update_conversation(
            conversation_id=conversation_id,
            title=payload.title,
            is_pinned=payload.is_pinned,
            is_muted=payload.is_muted,
        )
    except ValueError as exc:
        detail = str(exc)
        http_status = status.HTTP_404_NOT_FOUND if detail == "conversation_id not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail) from exc
    return to_conversation_response(updated)


class DeleteConversationRequest(BaseModel):
    """Request body for dissolving a conversation; carries the requester identity."""

    requester_id: str = Field(min_length=1)


@router.delete(
    "/im/v1/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: str,
    payload: DeleteConversationRequest,
    service: WebIMService = Depends(get_web_im_service),
) -> None:
    """Dissolve a group conversation (creator only).

    Cascades deletion of all messages, participants, and relay tasks.
    Returns 403 when the requester is not the conversation creator.
    """
    try:
        service.delete_conversation(
            conversation_id=conversation_id,
            requester_id=payload.requester_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete(
    "/im/v1/conversations/{conversation_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def leave_conversation(
    conversation_id: str,
    user_id: str,
    service: WebIMService = Depends(get_web_im_service),
) -> None:
    """Remove one participant from a conversation (leave-group).

    Other participants are not affected.
    """
    try:
        service.remove_participant(
            conversation_id=conversation_id,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
