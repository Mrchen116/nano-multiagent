"""Message and event routes for IM HTTP APIs."""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from IM.api.deps import (
    current_user,
    get_gateway_handler,
    get_relay_service,
    get_web_im_service,
)
from IM.application.relay_service import RelayService
from IM.application.web_im_service import WebIMService
from IM.domain.models import Attachment, Message, User
from IM.ws.gateway_handler import GatewayHandler

router = APIRouter(tags=["messages"])

# Upload safety: white-list mirrors design.md decision 8 — image families,
# PDFs, and a handful of plaintext-style documents the agent can read with
# the existing tool surface. Anything else returns 415 so an agent can never
# be coerced into running an arbitrary blob downloaded by the user.
_UPLOAD_ALLOWED_PREFIXES = ("image/",)
_UPLOAD_ALLOWED_EXACT = frozenset(
    {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/json",
    }
)
_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
_MESSAGE_MAX_ATTACHMENTS = 5


def _is_allowed_upload_content_type(content_type: str) -> bool:
    if content_type in _UPLOAD_ALLOWED_EXACT:
        return True
    return any(content_type.startswith(prefix) for prefix in _UPLOAD_ALLOWED_PREFIXES)


class AttachmentPayload(BaseModel):
    """Serialized attachment payload accepted and returned by the API."""

    url: str = Field(min_length=1)
    content_type: str | None = None
    file_name: str | None = None


class ActorPayload(BaseModel):
    """Actor-first identity payload used by message APIs."""

    type: str = Field(min_length=1)
    id: str = Field(min_length=1)
    display_name: str | None = None


class CreateMessageRequest(BaseModel):
    """Request payload for creating a message."""

    sender: ActorPayload | None = None
    sender_user_id: str | None = None
    sender_type: str | None = Field(default="user")
    content: str = Field(default="")
    attachments: list[AttachmentPayload] = Field(default_factory=list)
    target_node_id: str | None = None

    @model_validator(mode="after")
    def validate_sender(self) -> "CreateMessageRequest":
        if self.sender is None and self.sender_user_id is None:
            raise ValueError("sender or sender_user_id is required")
        return self


class ToolCallPayload(BaseModel):
    id: str
    name: str
    status: str
    input: dict = {}
    duration_ms: int | None = None
    output: str | None = None
    # bugfix-410-M2 (#97): sidecar badge classification (denied/timed_out/interrupted),
    # carried on history load so the badge survives a page reload, not only live WS.
    reason: str | None = None
    # feat-409: presenter-produced structured detail, forwarded from the Gateway and
    # persisted on the domain ToolCall. The REST history path must serialize it too,
    # else front-end history load 退化 to <pre>{output}> (no per-tool render / prompt).
    detail: dict | None = None
    # feat-425: tool-carried emoji on history load, so a custom tool's icon survives
    # a page reload (name table only knows built-ins). None → front-end name fallback.
    emoji: str | None = None


class TokenUsagePayload(BaseModel):
    output: int
    context_used: int
    context_window: int
    total: int | None = None


class MessageResponse(BaseModel):
    """Serialized message object returned by API endpoints."""

    id: str
    conversation_id: str
    sender: ActorPayload
    sender_user_id: str
    sender_type: str
    content: str
    attachments: list[AttachmentPayload]
    delivery_status: str
    created_at: str
    tool_calls: list[ToolCallPayload] = []
    token_usage: TokenUsagePayload | None = None
    # feat-414: 本轮 agent 处理墙钟（毫秒）。用户消息及旧行均为 None。
    elapsed_ms: int | None = None
    # bugfix-367: list-shaped 以保留同一 message 上所有 ask 的历史(允许 / 拒绝 /
    # 当前 pending)。REST 历史回放因此能完整还原"按了多少个同意"。
    permission_requests: list[dict] = []


class ListMessagesResponse(BaseModel):
    """Envelope returned when listing paginated messages."""

    items: list[MessageResponse]
    next_before_message_id: str | None

    def __iter__(self):
        """Preserve legacy list-like iteration for older tests and callers."""
        return iter(self.items)

    def __len__(self) -> int:
        """Preserve legacy len() semantics for older tests and callers."""
        return len(self.items)


def to_message_response(message: Message) -> MessageResponse:
    """Convert domain message to API response model."""
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender=ActorPayload(
            type=message.sender.type
            if message.sender is not None
            else message.sender_type,
            id=message.sender.id
            if message.sender is not None
            else message.sender_user_id,
            display_name=message.sender.display_name
            if message.sender is not None
            else None,
        ),
        sender_user_id=message.sender_user_id,
        sender_type=message.sender_type,
        content=message.content,
        attachments=[
            AttachmentPayload(
                url=item.url,
                content_type=item.content_type,
                file_name=item.file_name,
            )
            for item in message.attachments
        ],
        delivery_status=message.delivery_status,
        created_at=message.created_at,
        tool_calls=[
            ToolCallPayload(
                id=tc.id,
                name=tc.name,
                status=tc.status,
                input=tc.input if isinstance(tc.input, dict) else {},
                duration_ms=tc.duration_ms,
                output=tc.output,
                reason=tc.reason,
                detail=tc.detail,
                emoji=tc.emoji,
            )
            for tc in (message.tool_calls or [])
        ],
        token_usage=TokenUsagePayload(
            output=message.token_usage.output,
            context_used=message.token_usage.context_used,
            context_window=message.token_usage.context_window,
            # bugfix-390: align REST total-fallback with WS path (event_types.py:67).
            # Pre-M17 persisted rows may have total=None; derive from context_used+output
            # so that total is always non-None — frontend takes total without view-layer fallback.
            total=(
                message.token_usage.total
                if message.token_usage.total is not None
                else message.token_usage.context_used + message.token_usage.output
            ),
        )
        if message.token_usage is not None
        else None,
        # feat-414: 直接透传，用户消息及旧行为 None。
        elapsed_ms=message.elapsed_ms,
        # bugfix-367: pass-through list 形态。前端 reducer / 渲染按 request_id
        # 索引每张卡,key 用 request_id remount,刷新后历史小条全部还原。
        permission_requests=list(message.permission_requests),
    )


def _sanitize_upload_file_name(file_name: str) -> str:
    """Collapse user-provided upload names to a safe basename."""
    safe_name = Path(file_name.strip()).name
    if not safe_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_name must be non-empty",
        )
    return safe_name


def _resolve_upload_content_type(request: Request) -> str:
    """Pick the content type stored alongside one uploaded attachment."""
    raw_content_type = request.headers.get("Content-Type", "application/octet-stream")
    return raw_content_type.split(";", 1)[0].strip() or "application/octet-stream"


def _assert_conversation_in_owner_scope(
    *, service: WebIMService, conversation_id: str, owner_id: str
) -> None:
    """Raise 404 when the conversation is missing or owned by a different tenant."""
    conversation = service.get_conversation_for_owner(
        conversation_id=conversation_id, owner_id=owner_id
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="conversation_id not found"
        )


@router.post(
    "/im/v1/uploads",
    response_model=AttachmentPayload,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload(
    request: Request,
    file_name: str = Query(min_length=1),
    user: User = Depends(current_user),
) -> AttachmentPayload:
    del user  # auth-gated only; uploads themselves are tenant-agnostic by URL design
    """Persist one raw upload body and return the IM-hosted attachment descriptor."""
    safe_name = _sanitize_upload_file_name(file_name)
    content_type = _resolve_upload_content_type(request)
    if not _is_allowed_upload_content_type(content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported content_type: {content_type}",
        )
    body = await request.body()
    if len(body) > _UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"upload exceeds {_UPLOAD_MAX_BYTES} bytes",
        )
    suffix = Path(safe_name).suffix
    stored_name = f"{uuid4().hex}{suffix}"
    upload_dir = Path(request.app.state.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / stored_name).write_bytes(body)
    return AttachmentPayload(
        url=f"{str(request.base_url).rstrip('/')}/im/uploads/{stored_name}",
        content_type=content_type,
        file_name=safe_name,
    )


@router.post(
    "/im/v1/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    conversation_id: str,
    payload: CreateMessageRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> MessageResponse:
    """Create a message in a conversation and optionally relay it to one gateway."""
    del request
    _assert_conversation_in_owner_scope(
        service=service, conversation_id=conversation_id, owner_id=user.owner_id
    )
    if len(payload.attachments) > _MESSAGE_MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"too many attachments: max {_MESSAGE_MAX_ATTACHMENTS} per message",
        )
    try:
        sender_user_id, sender_type = _resolve_create_message_sender(payload)
        resolved_target_node_id = (
            payload.target_node_id
            or service.resolve_target_node_id(
                conversation_id=conversation_id,
                content=payload.content,
            )
        )
        created = service.create_message(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            sender_type=sender_type,
            content=payload.content,
            attachments=[
                Attachment(
                    url=item.url,
                    content_type=item.content_type,
                    file_name=item.file_name,
                )
                for item in payload.attachments
            ],
            auto_complete_delivery=resolved_target_node_id is None,
        )
    except ValueError as exc:
        raise map_message_write_error(exc) from exc
    if resolved_target_node_id is not None:
        idempotency_key_base = (
            idempotency_key or f"relay:{created.id}:{resolved_target_node_id}"
        )
        relay_results = service.enqueue_relay_all(
            message=created,
            target_node_id=resolved_target_node_id,
            idempotency_key_base=idempotency_key_base,
            sender_user_id=created.sender_user_id,
        )
        # Push each relay independently: one offline agent must not block others.
        any_dispatched = False
        for relay_result in relay_results:
            dispatched = await gateway_handler.push_relay_message(
                relay_task_id=relay_result.relay_task.relay_task_id,
                target_node_id=resolved_target_node_id,
                payload=relay_result.relay_task.payload,
            )
            if dispatched:
                any_dispatched = True
            else:
                gateway_handler.record_relay_failure(
                    conversation_id=created.conversation_id,
                    message_id=created.id,
                    relay_task_id=relay_result.relay_task.relay_task_id,
                    target_node_id=resolved_target_node_id,
                    reason="node_disconnected",
                    guidance="检查目标节点连接状态后重试，或切换到在线节点。",
                )
        if not any_dispatched:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="target_node_id is not connected",
            )
    return to_message_response(created)


@router.get(
    "/im/v1/conversations/{conversation_id}/messages",
    response_model=ListMessagesResponse,
)
def list_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before_message_id: str | None = Query(default=None),
    mark_as_read: bool = Query(default=False),
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> ListMessagesResponse:
    """List messages for one conversation in insertion order (owner-scoped)."""
    _assert_conversation_in_owner_scope(
        service=service, conversation_id=conversation_id, owner_id=user.owner_id
    )
    try:
        items = service.list_messages(
            conversation_id=conversation_id,
            limit=limit,
            before_message_id=before_message_id,
            mark_as_read=mark_as_read,
        )
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_404_NOT_FOUND
            if detail == "before_message_id not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    next_before_message_id = items[0].id if len(items) == limit else None
    return ListMessagesResponse(
        items=[to_message_response(item) for item in items],
        next_before_message_id=next_before_message_id,
    )


def map_message_write_error(exc: ValueError) -> HTTPException:
    """Map repository write failures to stable HTTP status codes."""
    detail = str(exc)
    if detail in {
        "conversation_id not found",
        "sender_user_id not found",
        "before_message_id not found",
    }:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class SubmitPermissionDecisionRequest(BaseModel):
    """Request body for the user-decision permission endpoint."""

    message_id: str = Field(min_length=1)
    decision: str = Field(min_length=1)


@router.post(
    "/im/v1/conversations/{conversation_id}/permissions/{request_id}",
    status_code=status.HTTP_200_OK,
)
async def submit_permission_decision(
    conversation_id: str,
    request_id: str,
    payload: SubmitPermissionDecisionRequest,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
    relay_service: RelayService = Depends(get_relay_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> dict:
    """Forward user's permission decision to the gateway node hosting the parked run.

    Resolves the target node from the conversation's agent participant, then pushes
    a ``permission_response`` frame via the gateway WS so the PA can relay it to the
    agent inbound endpoint and resume the parked hook.

    Returns:
        ``{"status": "forwarded"}`` when the node was connected, otherwise
        ``{"status": "queued"}`` when the node is offline (decision will be retried).
    """
    _assert_conversation_in_owner_scope(
        service=service, conversation_id=conversation_id, owner_id=user.owner_id
    )
    # Resolve which node hosts the agent in this conversation.
    target_node_id = relay_service.resolve_target_node_id(
        conversation_id=conversation_id,
        content="",
    )
    if target_node_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="no agent node found for this conversation",
        )
    delivered = await gateway_handler.push_permission_response(
        target_node_id=target_node_id,
        message_id=payload.message_id,
        request_id=request_id,
        decision=payload.decision,
    )
    return {"status": "forwarded" if delivered else "queued"}


def _resolve_create_message_sender(payload: CreateMessageRequest) -> tuple[str, str]:
    """Normalize actor-first sender payload to repository-compatible sender identifiers."""
    if payload.sender is not None:
        sender_type = payload.sender.type.strip().lower()
        sender_id = payload.sender.id.strip()
        if sender_type not in {"user", "agent", "system"}:
            raise ValueError("sender.type must be one of: user, agent, system")
        if sender_type == "agent":
            return (f"agent:{sender_id}", sender_type)
        if sender_type == "user":
            return (f"user:{sender_id}", sender_type)
        return (sender_id, sender_type)
    assert payload.sender_user_id is not None
    legacy_sender_type = (payload.sender_type or "user").strip().lower()
    return (payload.sender_user_id.strip(), legacy_sender_type)
