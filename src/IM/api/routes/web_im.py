"""Conversation routes for IM HTTP APIs."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, model_validator

from IM.api.deps import (
    current_user,
    current_data_principal,
    current_gateway,
    GatewayPrincipal,
    require_conversation_access,
    notify_conversation_membership,
    get_event_service,
    get_profile_repository,
    get_web_im_service,
)
from IM.application.event_service import EventService
from IM.application.node_service import NodeService
from IM.infra.repositories.nodes import NodeRepository
from IM.application.web_im_service import (
    AgentOfflineError,
    ForkDelegationError,
    ForkNotFoundError,
    ForkValidationError,
    WebIMService,
)
from IM.api.deps import get_gateway_control, get_gateway_sessions
from IM.ws.gateway.control import GatewayControl
from IM.ws.gateway.sessions import GatewaySessions
from IM.domain.models import Conversation, User
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.users import UserRepository

router = APIRouter(tags=["web-im"])


class ActorPayload(BaseModel):
    """Actor-first identity payload used by IM HTTP APIs."""

    type: str = Field(min_length=1)
    id: str = Field(min_length=1)
    display_name: str | None = None
    # decision 5: agent participants carry a stable user_id (UUID) distinct from
    # ``id`` (the logical agent_id); the frontend reads it to drive the remove
    # endpoint, which keys on conversation_participants.user_id.
    user_id: str | None = None
    is_stale: bool | None = None


class CreateConversationRequest(BaseModel):
    """Request payload for creating a conversation."""

    title: str = Field(min_length=1)
    type: Literal["direct", "group"]
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


class DistillSourceRequest(BaseModel):
    """One browser-selected historical source identified without filesystem data."""

    conversation_id: str = Field(min_length=1)
    source_agent_id: str = Field(min_length=1)


class CreateDistillPromptRequest(BaseModel):
    """Request one Gateway-produced ordinary-chat distill prompt."""

    sources: list[DistillSourceRequest] = Field(min_length=1)
    execution_agent_id: str = Field(min_length=1)
    target_scope: str = Field(pattern="^(agent|global)$")


class ForkConversationRequest(BaseModel):
    """Request payload for forking a conversation at one agent reply (feat-445-M1)."""

    fork_message_id: str = Field(min_length=1)


class UpdateConversationRequest(BaseModel):
    """Request payload for updating conversation metadata."""

    title: str | None = None
    is_pinned: bool | None = None
    is_muted: bool | None = None


class AddParticipantsRequest(BaseModel):
    """Request payload for adding participants to an existing conversation.

    Emptiness and resolve failures are validated downstream (repo) so they surface
    as 400 (decision 3), not 422 — the route maps the raised ValueError to 400.
    """

    participants: list["ActorPayload"]


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
    config_agent_id: str | None
    config_profile_version: int | None
    external_source: str | None = None
    external_chat_id: str | None = None
    created_at: str
    run_state: str
    source_agent_id: str | None = None
    source_node_id: str | None = None


class DistillPromptResponse(BaseModel):
    """Return a server-pinned execution conversation and its editable prompt."""

    conversation: ConversationResponse
    prompt: str


class ExternalFindOrCreateConversationRequest(BaseModel):
    """Request payload for external-channel shadow conversation upsert."""

    external_source: str = Field(min_length=1)
    external_chat_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    is_group: bool = False
    participant_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


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
                user_id=item.user_id,
                is_stale=item.is_stale
                if item.type == "agent" and item.is_stale
                else None,
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
        config_agent_id=conversation.config_agent_id,
        config_profile_version=conversation.config_profile_version,
        external_source=conversation.external_source,
        external_chat_id=conversation.external_chat_id,
        created_at=conversation.created_at,
        run_state=conversation.run_state,
        source_agent_id=conversation.source_agent_id,
        source_node_id=conversation.source_node_id,
    )


def _load_member_conversation(
    *,
    service: WebIMService,
    conversation_id: str,
    user_id: str,
) -> Conversation:
    """Return the current member view, otherwise a non-disclosing 404."""
    conversation = service.get_conversation_for_member(
        conversation_id=conversation_id, user_id=user_id
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="conversation_id not found"
        )
    return conversation


@router.get("/im/v1/contacts")
async def list_contacts(
    request: Request,
    q: str = "",
    kind: str | None = None,
    cursor: str | None = None,
    user: User = Depends(current_user),
) -> dict[str, object]:
    """List public human and Agent identities without exposing management data."""
    try:
        items, next_cursor = UserRepository(request.app.state.connection).list_contacts(
            q=q, kind=kind, cursor=cursor
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _project_contact_status(request, items)
    return {"items": items, "next_cursor": next_cursor}


@router.get("/im/v1/contacts/{user_id}")
async def get_contact(
    user_id: str, request: Request, user: User = Depends(current_user)
) -> dict[str, object]:
    """Read one discoverable contact using its stable IM user identity."""
    item = UserRepository(request.app.state.connection).get_contact(user_id=user_id)
    if item is None:
        raise HTTPException(status_code=404, detail="contact not found")
    await _project_contact_status(request, [item])
    return item


async def _project_contact_status(
    request: Request, items: list[dict[str, object]]
) -> None:
    """Use the same heartbeat and live-connection status as the owned node board."""
    connected = await request.app.state.gateway_sessions.list_connected_node_ids()
    statuses = {
        node.node_id: node.status
        for node in NodeService(
            nodes=NodeRepository(request.app.state.connection)
        ).list_nodes(connected_node_ids=connected)
    }
    profiles = AgentProfileRepository(request.app.state.connection)
    for item in items:
        if item["kind"] == "agent":
            profile = profiles.get_profile(agent_id=str(item["agent_id"]))
            item["status"] = (
                statuses.get(profile.node_id, "offline") if profile else "offline"
            )


def _validated_public_participants(
    *, request: Request, references: list[str], user: User, group: bool
) -> list[str]:
    users = UserRepository(request.app.state.connection)
    result: list[str] = []
    for reference in references:
        if reference.startswith("agent:"):
            identity = users.get_user_by_username(username=reference)
        else:
            identity = users.get_user(user_id=reference.removeprefix("user:"))
        contact = users.get_contact(user_id=identity.id) if identity else None
        if contact is None:
            raise ValueError("participant_ids contains unknown users")
        if (
            group
            and contact["kind"] == "agent"
            and contact["owner_id"] != user.owner_id
        ):
            raise PermissionError(
                "only the Agent manager can add this Agent to a group"
            )
        if identity.id not in result:
            result.append(identity.id)
    return result


@router.post(
    "/im/v1/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: Request,
    payload: CreateConversationRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Create a conversation with validated participants including the authenticated creator."""
    # The app-scoped SQLite handle also serves Gateway writes on the event loop.
    # Keep this short transaction there so concurrent creates cannot cross-commit.
    try:
        participant_refs = _validated_public_participants(
            request=request,
            references=_resolve_create_conversation_participants(payload),
            user=user,
            group=payload.type == "group",
        )
        participant_refs = list(dict.fromkeys([user.id, *participant_refs]))
        created = service.create_conversation(
            title=payload.title,
            participant_ids=participant_refs,
            caller_owner_id=user.owner_id,
            creator_id=user.id,
            conversation_type=payload.type,
            reuse_direct=True,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    await notify_conversation_membership(request, created.id, created.participant_ids)
    return to_conversation_response(
        service.get_conversation_for_member(conversation_id=created.id, user_id=user.id)
    )


@router.post(
    "/im/v1/conversations/distill-prompt",
    response_model=DistillPromptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_distill_prompt(
    payload: CreateDistillPromptRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
    gateway_control: GatewayControl = Depends(get_gateway_control),
    profiles: AgentProfileRepository = Depends(get_profile_repository),
) -> DistillPromptResponse:
    """Create one same-Gateway execution chat after its prompt is locally resolved."""
    target_node_id: str | None = None
    control_sources: list[dict[str, object]] = []
    for source_request in payload.sources:
        source = service.get_conversation_for_member(
            conversation_id=source_request.conversation_id,
            user_id=user.id,
        )
        if (
            source is None
            or source.run_state != "idle"
            or source.source_agent_id != source_request.source_agent_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="selected source is unavailable",
            )
        source_profile = profiles.get_profile_for_owner(
            agent_id=source.source_agent_id,
            owner_id=user.owner_id,
        )
        source_node_id = source_profile.node_id if source_profile is not None else None
        if not source_node_id or source_profile.work_mode != "single_thread":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="selected source is unavailable",
            )
        if target_node_id is None:
            target_node_id = source_node_id
        elif target_node_id != source_node_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="selected sources must belong to one Gateway",
            )
        control_source: dict[str, object] = {
            "conversation_id": source.id,
            "source_agent_id": source.source_agent_id,
        }
        if source.external_source and source.external_chat_id:
            control_source.update(
                {
                    "external_source": source.external_source,
                    "external_chat_id": source.external_chat_id,
                }
            )
        control_sources.append(control_source)

    execution = profiles.get_profile_for_owner(
        agent_id=payload.execution_agent_id,
        owner_id=user.owner_id,
    )
    if (
        execution is None
        or not execution.node_id
        or execution.node_id != target_node_id
        or execution.work_mode != "single_thread"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="execution agent must belong to the selected Gateway",
        )

    result = await gateway_control.request_distill_prompt(
        target_node_id=target_node_id,
        sources=control_sources,
        execution_agent_id=payload.execution_agent_id,
        target_scope=payload.target_scope,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="selected Gateway did not return a distill prompt",
        )
    prompt = result.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(
                result.get("message") or "selected Gateway cannot distill these sources"
            ),
        )

    try:
        conversation = service.create_conversation(
            title=f"Skill distill · {execution.display_name}",
            participant_ids=[f"user:{user.id}", f"agent:{execution.agent_id}"],
            caller_owner_id=user.owner_id,
            target_node_id=target_node_id,
            creator_id=user.id,
            conversation_type="direct",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return DistillPromptResponse(
        conversation=to_conversation_response(conversation), prompt=prompt
    )


@router.post(
    "/im/v1/conversations/{conversation_id}/fork",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def fork_conversation(
    conversation_id: str,
    payload: ForkConversationRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
    gateway_sessions: GatewaySessions = Depends(get_gateway_sessions),
    gateway_control: GatewayControl = Depends(get_gateway_control),
    profiles: AgentProfileRepository = Depends(get_profile_repository),
) -> ConversationResponse:
    """Fork a direct agent chat at one completed agent reply into a new branch chat.

    The online check and the kernel session fork both reach the agent's owning node over
    the gateway WS — wired here as delegates so WebIMService stays WS-agnostic.
    """

    async def _check_agent_online(agent_id: str) -> bool:
        profile = profiles.get_profile(agent_id=agent_id)
        if profile is None or not profile.node_id:
            return False
        return await gateway_sessions.is_connected(node_id=profile.node_id)

    async def _request_fork(
        *,
        agent_id,
        source_conversation_id,
        new_conversation_id,
        fork_message_id,
        source_external_source=None,
        source_external_chat_id=None,
    ):
        profile = profiles.get_profile(agent_id=agent_id)
        if profile is None or not profile.node_id:
            return None
        return await gateway_control.request_fork_session(
            target_node_id=profile.node_id,
            source_conversation_id=source_conversation_id,
            new_conversation_id=new_conversation_id,
            agent_id=agent_id,
            fork_message_id=fork_message_id,
            source_external_source=source_external_source,
            source_external_chat_id=source_external_chat_id,
        )

    try:
        forked = await service.fork_conversation(
            source_conversation_id=conversation_id,
            fork_message_id=payload.fork_message_id,
            owner_id=user.owner_id,
            actor_user_id=user.id,
            check_agent_online=_check_agent_online,
            request_fork=_request_fork,
        )
    except ForkNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ForkValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except AgentOfflineError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ForkDelegationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return to_conversation_response(forked)


@router.get("/im/v1/conversations", response_model=ListConversationsResponse)
async def list_conversations(
    request: Request,
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
    service: WebIMService = Depends(get_web_im_service),
) -> ListConversationsResponse:
    """List conversations visible in the caller's current memberships."""
    if isinstance(user, GatewayPrincipal):
        profile = AgentProfileRepository(request.app.state.connection).get_profile(
            agent_id=agent_id or ""
        )
        identity = UserRepository(request.app.state.connection).get_user_by_username(
            username=f"agent:{agent_id}"
        )
        if (
            profile is None
            or profile.is_stale
            or profile.node_id != user.node_id
            or profile.owner_id != user.owner_id
            or identity is None
        ):
            raise HTTPException(status_code=404, detail="agent_id not found")
        member_id = identity.id
    else:
        member_id = user.id
    return ListConversationsResponse(
        items=[
            to_conversation_response(item)
            for item in service.list_conversations_for_member(user_id=member_id)
        ]
    )


@router.post(
    "/im/v1/conversations/external/find-or-create",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def find_or_create_external_conversation(
    payload: ExternalFindOrCreateConversationRequest,
    response: Response,
    user: GatewayPrincipal = Depends(current_gateway),
    profiles: AgentProfileRepository = Depends(get_profile_repository),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Find or create an owner-scoped external-channel shadow conversation."""
    profile = profiles.get_profile(agent_id=payload.agent_id)
    if (
        profile is None
        or profile.node_id != user.node_id
        or profile.owner_id != user.owner_id
    ):
        raise HTTPException(status_code=404, detail="agent_id not found")
    participant_ids = [f"user:{user.owner_id}", f"agent:{payload.agent_id}"]
    if payload.participant_ids and {
        item.removeprefix("user:") for item in payload.participant_ids
    } != {item.removeprefix("user:") for item in participant_ids}:
        raise HTTPException(
            status_code=400,
            detail="shadow participants must match node owner and Agent",
        )
    try:
        result = service.find_or_create_external_conversation(
            external_source=payload.external_source,
            external_chat_id=payload.external_chat_id,
            agent_id=payload.agent_id,
            title=payload.title,
            is_group=payload.is_group,
            participant_ids=participant_ids,
            owner_id=user.owner_id,
            creator_id=f"user:{user.owner_id}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if not result.created:
        response.status_code = status.HTTP_200_OK
    persisted = service.get_conversation(conversation_id=result.conversation.id)
    assert persisted is not None
    return to_conversation_response(persisted).model_copy(
        update={
            "config_agent_id": payload.agent_id,
            "external_source": payload.external_source,
            "external_chat_id": payload.external_chat_id,
        }
    )


@router.get("/im/v1/sync", response_model=ImSyncResponse)
def sync_im_state(
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
    event_service: EventService = Depends(get_event_service),
) -> ImSyncResponse:
    """返回会话列表与全局 max(event_id)，供用户 WebSocket resync_required 后对齐客户端游标。"""
    items = [
        to_conversation_response(item)
        for item in service.list_conversations_for_member(user_id=user.id)
    ]
    max_event_id = event_service.global_max_event_id()
    return ImSyncResponse(items=items, max_event_id=max_event_id)


@router.get(
    "/im/v1/conversations/{conversation_id}", response_model=ConversationResponse
)
async def get_conversation(
    conversation_id: str,
    request: Request,
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Return one conversation snapshot for the current member (404 otherwise)."""
    conversation = require_conversation_access(
        request=request,
        principal=user,
        conversation_id=conversation_id,
        agent_id=agent_id,
    )
    return to_conversation_response(conversation)


@router.patch(
    "/im/v1/conversations/{conversation_id}", response_model=ConversationResponse
)
async def update_conversation(
    conversation_id: str,
    request: Request,
    payload: UpdateConversationRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Update mutable conversation metadata for the current member."""
    _load_member_conversation(
        service=service, conversation_id=conversation_id, user_id=user.id
    )
    try:
        updated = service.update_conversation(
            conversation_id=conversation_id,
            user_id=user.id,
            title=payload.title,
            is_pinned=payload.is_pinned,
            is_muted=payload.is_muted,
        )
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_404_NOT_FOUND
            if detail == "conversation_id not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    if payload.title is not None:
        await notify_conversation_membership(
            request, conversation_id, updated.participant_ids
        )
    return to_conversation_response(updated)


@router.delete(
    "/im/v1/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: str,
    request: Request,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> None:
    """Dissolve a group conversation (creator only).

    Cascades deletion of all messages, participants, and relay tasks.
    Returns 404 when the conversation is outside the caller's membership.
    Returns 403 when the requester is not the conversation creator.
    """
    conversation = _load_member_conversation(
        service=service, conversation_id=conversation_id, user_id=user.id
    )
    try:
        service.delete_conversation(
            conversation_id=conversation_id,
            requester_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

    await notify_conversation_membership(
        request, conversation_id, conversation.participant_ids, deleted=True
    )


@router.delete(
    "/im/v1/conversations/{conversation_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_conversation(
    conversation_id: str,
    request: Request,
    user_id: str,
    caller: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> None:
    """Remove one participant from a conversation (leave-group).

    Other participants are not affected. The conversation must belong to the
    caller's membership; otherwise 404.
    """
    conversation = _load_member_conversation(
        service=service, conversation_id=conversation_id, user_id=caller.id
    )
    if conversation.type != "group":
        raise HTTPException(
            status_code=400, detail="members can only be removed from a group"
        )
    if user_id == conversation.creator_id:
        raise HTTPException(
            status_code=403,
            detail="the creator must dissolve the group instead of leaving",
        )
    try:
        service.remove_participant(
            conversation_id=conversation_id,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    await notify_conversation_membership(
        request, conversation_id, conversation.participant_ids
    )


@router.post(
    "/im/v1/conversations/{conversation_id}/participants",
    response_model=ConversationResponse,
)
async def add_participants(
    conversation_id: str,
    request: Request,
    payload: AddParticipantsRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Add agent participants to an existing conversation (idempotent).

    Reuses the create path's actor→user resolution + membership INSERT and does
    not touch relay tasks (those are created per-participant when a message is
    sent). Returns 404 when the conversation is outside the caller's membership, and
    400 when the participant list is empty or an agent id cannot be resolved.
    """
    conversation = _load_member_conversation(
        service=service, conversation_id=conversation_id, user_id=user.id
    )
    if conversation.type != "group":
        raise HTTPException(
            status_code=400, detail="members can only be added to a group"
        )
    try:
        references = _validated_public_participants(
            request=request,
            references=_actor_payloads_to_references(payload.participants),
            user=user,
            group=True,
        )
        updated = service.add_participants(
            conversation_id=conversation_id,
            references=references,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    await notify_conversation_membership(
        request,
        conversation_id,
        list(set(conversation.participant_ids) | set(updated.participant_ids)),
    )
    return to_conversation_response(
        service.get_conversation_for_member(
            conversation_id=conversation_id, user_id=user.id
        )
    )


class ReadConversationRequest(BaseModel):
    """The latest message actually displayed by this member."""

    last_read_message_id: str = Field(min_length=1)


@router.post(
    "/im/v1/conversations/{conversation_id}/read", response_model=ConversationResponse
)
async def mark_conversation_read(
    conversation_id: str,
    payload: ReadConversationRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ConversationResponse:
    """Advance only the requesting member's read boundary."""
    _load_member_conversation(
        service=service, conversation_id=conversation_id, user_id=user.id
    )
    try:
        return to_conversation_response(
            service.mark_read(
                conversation_id=conversation_id,
                user_id=user.id,
                last_read_message_id=payload.last_read_message_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _actor_payloads_to_references(actors: list[ActorPayload]) -> list[str]:
    """Normalize actor-first payloads to repository-compatible references.

    Shared by conversation creation and participant addition so both paths
    resolve ``agent`` / ``user`` actors the same way.
    """
    references: list[str] = []
    for actor in actors:
        normalized_actor_type = actor.type.strip().lower()
        if normalized_actor_type == "agent":
            references.append(f"agent:{actor.id.strip()}")
            continue
        if normalized_actor_type == "user":
            references.append(f"user:{actor.id.strip()}")
            continue
        raise ValueError("participants.type must be one of: user, agent")
    return references


def _resolve_create_conversation_participants(
    payload: CreateConversationRequest,
) -> list[str]:
    """Normalize actor-first participants to repository-compatible references."""
    if payload.participants is not None:
        return _actor_payloads_to_references(payload.participants)
    assert payload.participant_ids is not None
    return [item.strip() for item in payload.participant_ids if item.strip()]
