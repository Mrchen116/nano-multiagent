"""Message and event routes for IM HTTP APIs."""

from pathlib import Path
import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from IM.api.deps import (
    GatewayPrincipal,
    current_data_principal,
    current_gateway,
    current_user,
    get_web_im_service,
    require_conversation_access,
)
from IM.api.resource_access import authorize_resource_references
from IM.application.web_im_service import WebIMService
from IM.api.deps import get_gateway_control, get_gateway_relay
from IM.ws.gateway.control import GatewayControl
from IM.ws.gateway.relay import GatewayRelay
from IM.domain.models import (
    AgentConfigChangedBoundary,
    Attachment,
    BackgroundReturn,
    ReplyProcessItem,
    Conversation,
    Message,
    ThinkingSegment,
    TokenUsage,
    ToolCall,
    User,
)
from IM.infra.repositories.users import UserRepository

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
    sender_display_name: str | None = None
    sender_source_id: str | None = None
    suppress_relay: bool = False

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
    # feat-434-M1: user-decision verdict on history load, so the gate region's
    # 已授权/已拒绝 survives a page reload (not only live WS). None → gate hidden.
    approval: str | None = None
    # feat-439-M2: shared process-timeline seq on history load, so the process panel
    # interleaves thinking + tools in true order after a reload. None → legacy row.
    seq: int | None = None


class ThinkingSegmentPayload(BaseModel):
    """feat-439-M2: one thinking process item on history load (process timeline)."""

    seq: int
    text: str


class BackgroundReturnPayload(BaseModel):
    """Terminal subagent/workflow result attached to one assistant message."""

    task_id: str
    task_type: str
    status: str
    description: str
    agent_id: str | None = None
    workflow_run_id: str | None = None
    result: str | None = None
    error: str | None = None
    usage: dict | None = None
    tool_use_count: int | None = None
    duration_ms: int | None = None
    output_file: str | None = None
    diagnostics: str | None = None
    resume_hint: str | None = None
    seq: int | None = None

    @classmethod
    def from_domain(cls, item: BackgroundReturn) -> "BackgroundReturnPayload":
        return cls(**{name: getattr(item, name) for name in cls.model_fields})


class TokenUsagePayload(BaseModel):
    output: int
    context_used: int
    context_window: int
    total: int | None = None
    # feat-439-M1: 缓存命中两字段(整轮口径)。旧行默认 0，前端渲染「缓存命中 X (Y%)」。
    cache_read_tokens: int = 0
    cache_total_input_tokens: int = 0


class ExternalAgentMessageSnapshotRequest(BaseModel):
    """Complete terminal projection used to recover an external Agent bubble."""

    agent_id: str = Field(min_length=1)
    content: str = ""
    thinking: list[ThinkingSegmentPayload] = Field(default_factory=list)
    tool_calls: list[ToolCallPayload] = Field(default_factory=list)
    token_usage: TokenUsagePayload | None = None
    elapsed_ms: int = Field(ge=0)
    delivery_status: str
    kernel_message_id: str | None = None

    @model_validator(mode="after")
    def validate_terminal(self) -> "ExternalAgentMessageSnapshotRequest":
        if self.delivery_status not in {"completed", "failed"}:
            raise ValueError("delivery_status must be completed or failed")
        return self


class SystemNoticePayload(BaseModel):
    """Browser-safe structured presentation snapshot for a system message."""

    kind: str
    source_agent_id: str
    source_agent_display_name: str
    updated_targets: list[str]


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
    # feat-439-M2: 整轮多段思考（过程时间线），历史回放还原过程盘。空列表 = 无思考。
    thinking: list[ThinkingSegmentPayload] = []
    background_returns: list[BackgroundReturnPayload] = []
    reply_process: list[ReplyProcessItem] = []
    token_usage: TokenUsagePayload | None = None
    # feat-414: 本轮 agent 处理墙钟（毫秒）。用户消息及旧行均为 None。
    elapsed_ms: int | None = None
    # feat-445-M1: kernel assistant message id（fork 锚点）。前端据此决定该气泡是否
    # 可 fork；用户/系统消息及本特性上线前的旧 agent 气泡为 None。
    kernel_message_id: str | None = None
    # bugfix-367: list-shaped 以保留同一 message 上所有 ask 的历史(允许 / 拒绝 /
    # 当前 pending)。REST 历史回放因此能完整还原"按了多少个同意"。
    permission_requests: list[dict] = []
    system_notice: SystemNoticePayload | None = None


class AgentConfigChangedResponse(BaseModel):
    """Serialized non-message cache boundary returned in a conversation timeline."""

    type: str = "agent_config_changed"
    id: str
    conversation_id: str
    agent_id: str
    before_message_id: str
    applied_at: str


class MessageTimelineItemResponse(BaseModel):
    """Typed timeline wrapper for a normal conversation message."""

    type: str = "message"
    message: MessageResponse


class ListMessagesResponse(BaseModel):
    """Envelope returned when listing a message-counted typed timeline page."""

    items: list[MessageTimelineItemResponse | AgentConfigChangedResponse]
    next_before_message_id: str | None

    def __iter__(self):
        """Preserve legacy list-like iteration for older tests and callers."""
        return iter(self.items)

    def __len__(self) -> int:
        """Preserve legacy len() semantics for older tests and callers."""
        return len(self.items)


def to_boundary_response(
    boundary: AgentConfigChangedBoundary,
) -> AgentConfigChangedResponse:
    """Serialize only browser-safe boundary fields, excluding runtime provenance."""
    return AgentConfigChangedResponse(
        id=boundary.id,
        conversation_id=boundary.conversation_id,
        agent_id=boundary.agent_id,
        before_message_id=boundary.before_message_id,
        applied_at=boundary.applied_at,
    )


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
                approval=tc.approval,
                seq=tc.seq,
            )
            for tc in (message.tool_calls or [])
        ],
        thinking=[
            ThinkingSegmentPayload(seq=s.seq, text=s.text)
            for s in (message.thinking or [])
        ],
        reply_process=message.reply_process or [],
        background_returns=[
            BackgroundReturnPayload.from_domain(item)
            for item in (message.background_returns or [])
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
            cache_read_tokens=message.token_usage.cache_read_tokens,
            cache_total_input_tokens=message.token_usage.cache_total_input_tokens,
        )
        if message.token_usage is not None
        else None,
        # feat-414: 直接透传，用户消息及旧行为 None。
        elapsed_ms=message.elapsed_ms,
        # feat-445-M1: 透传 fork 锚点供前端决定可 fork 性。
        kernel_message_id=message.kernel_message_id,
        # bugfix-367: pass-through list 形态。前端 reducer / 渲染按 request_id
        # 索引每张卡,key 用 request_id remount,刷新后历史小条全部还原。
        permission_requests=list(message.permission_requests),
        system_notice=(
            SystemNoticePayload(
                kind=message.system_notice.kind,
                source_agent_id=message.system_notice.source_agent_id,
                source_agent_display_name=(
                    message.system_notice.source_agent_display_name
                ),
                updated_targets=list(message.system_notice.updated_targets),
            )
            if message.system_notice is not None
            else None
        ),
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


@router.post(
    "/im/v1/uploads",
    response_model=AttachmentPayload,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload(
    request: Request,
    conversation_id: str = Query(min_length=1),
    file_name: str = Query(min_length=1),
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
) -> AttachmentPayload:
    """Store an ordinary attachment under its authenticated conversation boundary."""
    require_conversation_access(request, user, conversation_id, agent_id)
    safe_name = _sanitize_upload_file_name(file_name)
    content_type = _resolve_upload_content_type(request)
    if not _is_allowed_upload_content_type(content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported content_type: {content_type}",
        )
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _UPLOAD_MAX_BYTES:
            raise HTTPException(413, f"upload exceeds {_UPLOAD_MAX_BYTES} bytes")
        body.extend(chunk)
    require_conversation_access(request, user, conversation_id, agent_id)
    resource, _ = request.app.state.message_image_repository.put(
        conversation_id=conversation_id,
        source_key=f"upload:{uuid4().hex}",
        data=bytes(body),
        content_type=content_type,
        file_name=safe_name,
    )
    return AttachmentPayload(
        url=resource.attachment_url,
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
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
    service: WebIMService = Depends(get_web_im_service),
    gateway_handler: GatewayRelay = Depends(get_gateway_relay),
) -> MessageResponse:
    """Create a message in a conversation and optionally relay it to one gateway."""
    conversation = require_conversation_access(request, user, conversation_id, agent_id)
    if len(payload.attachments) > _MESSAGE_MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"too many attachments: max {_MESSAGE_MAX_ATTACHMENTS} per message",
        )
    try:
        sender_user_id, sender_type = _resolve_authorized_sender(
            request, user, conversation, payload, agent_id
        )
        content = authorize_resource_references(
            request, user, conversation_id, payload.content, agent_id
        )
        attachments = [
            Attachment(
                url=authorize_resource_references(
                    request, user, conversation_id, item.url, agent_id
                ),
                content_type=item.content_type,
                file_name=item.file_name,
            )
            for item in payload.attachments
        ]
        resolved_target_node_id = None
        if not payload.suppress_relay and any(
            member.type == "agent" for member in conversation.participants
        ):
            resolved_target_node_id = (
                conversation.target_node_id
                or service.resolve_target_node_id(
                    conversation_id=conversation_id,
                    content=payload.content,
                )
            )
        created = service.create_message(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            sender_type=sender_type,
            content=content,
            attachments=attachments,
            auto_complete_delivery=resolved_target_node_id is None,
            sender_display_name=(
                payload.sender_display_name
                if isinstance(user, GatewayPrincipal)
                else None
            ),
            sender_source_id=(
                payload.sender_source_id if isinstance(user, GatewayPrincipal) else None
            ),
            emit_created_event=payload.suppress_relay,
            caller_idempotency_key=idempotency_key,
            external_sender=isinstance(user, GatewayPrincipal)
            and sender_type == "user",
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
            relay_target_node_id = relay_result.relay_task.target_node_id
            dispatched = await gateway_handler.push_relay_message(
                relay_task_id=relay_result.relay_task.relay_task_id,
                target_node_id=relay_target_node_id,
                payload=relay_result.relay_task.payload,
            )
            if dispatched:
                any_dispatched = True
            else:
                gateway_handler.record_relay_failure(
                    conversation_id=created.conversation_id,
                    message_id=created.id,
                    relay_task_id=relay_result.relay_task.relay_task_id,
                    target_node_id=relay_target_node_id,
                    reason="node_disconnected",
                    guidance="检查目标节点连接状态后重试，或切换到在线节点。",
                )
        if not any_dispatched:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="target_node_id is not connected",
            )
    return to_message_response(created)


@router.put(
    "/im/v1/conversations/{conversation_id}/external-agent-messages/{shadow_message_id}",
    response_model=MessageResponse,
)
def reconcile_external_agent_message(
    conversation_id: str,
    shadow_message_id: str,
    payload: ExternalAgentMessageSnapshotRequest,
    request: Request,
    user: GatewayPrincipal = Depends(current_gateway),
    service: WebIMService = Depends(get_web_im_service),
) -> MessageResponse:
    """Create or reconcile one terminal external Agent message by source identity."""

    conversation = require_conversation_access(
        request, user, conversation_id, payload.agent_id
    )
    if not conversation.external_source or not conversation.external_chat_id:
        raise HTTPException(404, "external conversation not found")
    content = authorize_resource_references(
        request, user, conversation_id, payload.content, payload.agent_id
    )
    try:
        message = service.reconcile_external_agent_message(
            conversation_id=conversation_id,
            shadow_message_id=shadow_message_id,
            agent_id=payload.agent_id,
            content=content,
            thinking=[
                ThinkingSegment(seq=item.seq, text=item.text)
                for item in payload.thinking
            ],
            tool_calls=[
                ToolCall(
                    id=item.id,
                    name=item.name,
                    status=item.status,
                    input=item.input,
                    duration_ms=item.duration_ms,
                    output=item.output,
                    reason=item.reason,
                    detail=item.detail,
                    emoji=item.emoji,
                    approval=item.approval,
                    seq=item.seq,
                )
                for item in payload.tool_calls
            ],
            token_usage=(
                TokenUsage(
                    output=payload.token_usage.output,
                    context_used=payload.token_usage.context_used,
                    context_window=payload.token_usage.context_window,
                    total=payload.token_usage.total
                    if payload.token_usage.total is not None
                    else payload.token_usage.context_used + payload.token_usage.output,
                    cache_read_tokens=payload.token_usage.cache_read_tokens,
                    cache_total_input_tokens=payload.token_usage.cache_total_input_tokens,
                )
                if payload.token_usage is not None
                else None
            ),
            elapsed_ms=payload.elapsed_ms,
            delivery_status=payload.delivery_status,
            kernel_message_id=payload.kernel_message_id,
        )
    except ValueError as exc:
        raise map_message_write_error(exc) from exc
    return to_message_response(message)


@router.get(
    "/im/v1/conversations/{conversation_id}/messages",
    response_model=ListMessagesResponse,
)
def list_messages(
    conversation_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    before_message_id: str | None = Query(default=None),
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
    service: WebIMService = Depends(get_web_im_service),
) -> ListMessagesResponse:
    """List messages for one conversation in insertion order (owner-scoped)."""
    require_conversation_access(request, user, conversation_id, agent_id)
    try:
        items = service.list_timeline(
            conversation_id=conversation_id,
            limit=limit,
            before_message_id=before_message_id,
        )
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_404_NOT_FOUND
            if detail == "before_message_id not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    message_items = [item for item in items if isinstance(item, Message)]
    next_before_message_id = (
        message_items[0].id if len(message_items) == limit else None
    )
    return ListMessagesResponse(
        items=[
            MessageTimelineItemResponse(message=to_message_response(item))
            if isinstance(item, Message)
            else to_boundary_response(item)
            for item in items
        ],
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
    # feat-440-M1: optional free-text reason a user types when denying. Threaded
    # through to PermissionResponse.reason so the gate weaves it into the rejection
    # text sent back to the LLM. Allow decisions ignore it.
    reason: str | None = None


@router.post(
    "/im/v1/conversations/{conversation_id}/permissions/{request_id}",
    status_code=status.HTTP_200_OK,
)
async def submit_permission_decision(
    conversation_id: str,
    request_id: str,
    payload: SubmitPermissionDecisionRequest,
    request: Request,
    user: User = Depends(current_user),
    gateway_control: GatewayControl = Depends(get_gateway_control),
) -> dict:
    """Durably accept the first member decision for the card's original execution."""
    require_conversation_access(request, user, conversation_id)
    normalized_reason = payload.reason.strip() if payload.reason else None
    try:
        decision = request.app.state.message_repository.claim_permission_decision(
            conversation_id=conversation_id,
            message_id=payload.message_id,
            request_id=request_id,
            decision=payload.decision,
            decided_by=user.id,
            reason=normalized_reason or None,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if decision["status"] == "submitted":
        request.app.state.event_repository.append_event(
            conversation_id=conversation_id,
            message_id=payload.message_id,
            event_type="permission.submitted",
            delivery_status="running",
            payload={
                "conversation_id": conversation_id,
                "message_id": payload.message_id,
                "request_id": request_id,
                "status": "submitted",
                "decision": decision["decision"],
                "decided_by": decision["decided_by"],
            },
        )
        await gateway_control.push_permission_response(
            target_node_id=str(decision["node_id"]),
            message_id=payload.message_id,
            request_id=request_id,
            decision=str(decision["decision"]),
            reason=decision.get("reason"),
        )
    return {
        key: decision.get(key)
        for key in ("status", "request_id", "decision", "decided_by")
    }


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


def _resolve_authorized_sender(
    request: Request,
    principal: User | GatewayPrincipal,
    conversation: Conversation,
    payload: CreateMessageRequest,
    agent_id: str | None,
) -> tuple[str, str]:
    sender_id, sender_type = _resolve_create_message_sender(payload)
    if isinstance(principal, User):
        if sender_type != "user" or sender_id not in {
            principal.id,
            f"user:{principal.id}",
        }:
            raise HTTPException(403, "sender must be the authenticated user")
        if payload.suppress_relay:
            raise HTTPException(403, "suppress_relay requires a gateway")
        return principal.id, "user"
    if sender_type == "agent" and sender_id == f"agent:{agent_id}":
        return sender_id, "agent"
    if (
        sender_type != "user"
        or not conversation.external_source
        or not conversation.external_chat_id
        or conversation.source_agent_id != agent_id
        or conversation.owner_id != principal.owner_id
    ):
        raise HTTPException(
            403, "external sender requires its gateway shadow conversation"
        )
    source_user_id = sender_id.removeprefix("user:")
    if source_user_id != principal.owner_id or not payload.sender_source_id:
        raise HTTPException(403, "external speaker identity is required")
    # The transport's owner anchors the shadow source, never the external speaker.
    # A non-login identity preserves source attribution without impersonating an account.
    identity = json.dumps(
        [principal.node_id, conversation.external_source, payload.sender_source_id]
    )
    username = "shadow:" + hashlib.sha256(identity.encode()).hexdigest()
    users = UserRepository(request.app.state.connection)
    speaker = users.get_user_by_username(username=username)
    if speaker is None:
        speaker = users.create_user(
            username=username,
            display_name=payload.sender_display_name or payload.sender_source_id,
        )
    return speaker.id, "user"
