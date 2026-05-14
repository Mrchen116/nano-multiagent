"""Conversation routes for IM HTTP APIs."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from IM.api.deps import current_user, get_web_im_service
from IM.application.web_im_service import WebIMService
from IM.domain.models import Conversation, User
from IM.ws.user_stream import global_max_event_id

router = APIRouter(tags=["web-im"])


class ActorPayload(BaseModel):
    """Actor-first identity payload used by IM HTTP APIs."""

    type: str = Field(min_length=1)
    id: str = Field(min_length=1)
    display_name: str | None = None


class CreateConversationRequest(BaseModel):
    """Request payload for creating a conversation."""

    title: str = Field(min_length=1)
    participants: list["ActorPayload"] | None = None
    participant_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_participants(self) -> "CreateConversationRequest":
        if self.participants is None and self.participant_ids is None:
            raise ValueError("participants or participant_ids is required")
        if self.participants is not None and len(self.participants) == 0:
            raise ValueError("participants must contain at least one actor")
        if self.participant_ids is not None and len(self.participant_ids) == 0:
            raise ValueError("participant_ids must contain at least one id")
        return self


class UpdateConversationRequest(BaseModel):
    """Request payload for updating conversation metadata."""

    title: str | None = None
    is_pinned: bool | None = None
    is_muted: bool | None = None


class ConversationResponse(BaseModel):
    """Serialized conversation object returned by API endpoints."""

    id: str
    title: str
    participants: list["ActorPayload"]
    participant_ids: list[str]
    type: str
    direct_kind: str | None
    owner_id: str
    creator_id: str
    is_pinned: bool
    is_muted: bool
    unread_count: int
    last_message_preview: str | None
    last_message_at: str | None
    config_profile_version: int | None
    created_at: str


class ListConversationsResponse(BaseModel):
    """Envelope returned when listing conversations."""

    items: list[ConversationResponse]


class ImSyncResponse(BaseModel):
    """用户流重连/全量对齐用的会话列表与全局事件游标。"""

    items: list[ConversationResponse]
    max_event_id: int


def to_conversation_response(conversation: Conversation) -> ConversationResponse:
    """Convert domain conversation to API response model."""
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        participants=[
            ActorPayload(
                type=item.type,
                id=item.id,
                display_name=item.display_name,
            )
            for item in conversation.participants
        ],
        participant_ids=conversation.participant_ids,
        type=conversation.type,
        direct_kind=conversation.direct_kind,
        owner_id=conversation.owner_id,
        creator_id=conversation.creator_id,
        is_pinned=conversation.is_pinned,
        is_muted=conversation.is_muted,
        unread_count=conversation.unread_count,
        last_message_preview=conversation.last_message_preview,
        last_message_at=conversation.last_message_at,
        config_profile_version=conversation.config_profile_version,
        created_at=conversation.created_at,
    )


def _load_owner_scoped_conversation(
    *,
    service: WebIMService,
    conversation_id: str,
    owner_id: str,
) -> Conversation:
    """Return the conversation iff it belongs to the requesting owner, else 404."""
    conversation = service.get_conversation_for_owner(
        conversation_id=conversation_id, owner_id=owner_id
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="conversation_id not found"
        )
    return conversation


@router.post(
    "/im/v1/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: CreateConversationRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Create a conversation with validated participants under the caller's tenant."""
    try:
        participant_refs = _resolve_create_conversation_participants(payload)
        created = service.create_conversation(
            title=payload.title,
            participant_ids=participant_refs,
            caller_owner_id=user.owner_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_conversation_response(created)


@router.get("/im/v1/conversations", response_model=ListConversationsResponse)
def list_conversations(
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ListConversationsResponse:
    """List conversations visible in the caller's tenant scope."""
    return ListConversationsResponse(
        items=[
            to_conversation_response(item)
            for item in service.list_conversations_for_owner(owner_id=user.owner_id)
        ]
    )


@router.get("/im/v1/sync", response_model=ImSyncResponse)
def sync_im_state(
    request: Request,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ImSyncResponse:
    """返回会话列表与全局 max(event_id)，供用户 WebSocket resync_required 后对齐客户端游标。"""
    items = [
        to_conversation_response(item)
        for item in service.list_conversations_for_owner(owner_id=user.owner_id)
    ]
    max_event_id = global_max_event_id(request.app.state.connection)
    return ImSyncResponse(items=items, max_event_id=max_event_id)


@router.get("/im/v1/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Return one conversation snapshot for the caller's tenant (404 otherwise)."""
    conversation = _load_owner_scoped_conversation(
        service=service, conversation_id=conversation_id, owner_id=user.owner_id
    )
    return to_conversation_response(conversation)


@router.patch("/im/v1/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str,
    payload: UpdateConversationRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Update mutable conversation metadata for the caller's tenant."""
    _load_owner_scoped_conversation(
        service=service, conversation_id=conversation_id, owner_id=user.owner_id
    )
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


@router.delete(
    "/im/v1/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: str,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> None:
    """Dissolve a group conversation (creator only).

    Cascades deletion of all messages, participants, and relay tasks.
    Returns 404 when the conversation is not in the caller's tenant.
    Returns 403 when the requester is not the conversation creator.
    """
    _load_owner_scoped_conversation(
        service=service, conversation_id=conversation_id, owner_id=user.owner_id
    )
    try:
        service.delete_conversation(
            conversation_id=conversation_id,
            requester_id=user.id,
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
    caller: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> None:
    """Remove one participant from a conversation (leave-group).

    Other participants are not affected. The conversation must belong to the
    caller's tenant; otherwise 404.
    """
    _load_owner_scoped_conversation(
        service=service, conversation_id=conversation_id, owner_id=caller.owner_id
    )
    try:
        service.remove_participant(
            conversation_id=conversation_id,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _resolve_create_conversation_participants(payload: CreateConversationRequest) -> list[str]:
    """Normalize actor-first participants to repository-compatible references."""
    if payload.participants is not None:
        references: list[str] = []
        for actor in payload.participants:
            normalized_actor_type = actor.type.strip().lower()
            if normalized_actor_type == "agent":
                references.append(f"agent:{actor.id.strip()}")
                continue
            if normalized_actor_type == "user":
                references.append(f"user:{actor.id.strip()}")
                continue
            raise ValueError("participants.type must be one of: user, agent")
        return references
    assert payload.participant_ids is not None
    return [item.strip() for item in payload.participant_ids if item.strip()]
