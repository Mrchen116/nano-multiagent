"""Message and event routes for IM HTTP APIs."""
import asyncio
import json
from time import monotonic

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from IM.api.deps import assert_conversation_exists, get_event_service, get_gateway_handler, get_web_im_service
from IM.application.event_service import EventService
from IM.application.web_im_service import WebIMService
from IM.domain.models import Attachment, ConversationEvent, Message
from IM.infra.sse import encode_sse_event_frame, encode_sse_heartbeat
from IM.ws.gateway_handler import GatewayHandler

router = APIRouter(tags=["messages"])


class AttachmentPayload(BaseModel):
    """Serialized attachment payload accepted and returned by the API."""

    url: str = Field(min_length=1)
    content_type: str | None = None
    file_name: str | None = None


class CreateMessageRequest(BaseModel):
    """Request payload for creating a message."""

    sender_user_id: str = Field(min_length=1)
    sender_type: str = Field(default="user")
    content: str = Field(min_length=1)
    attachments: list[AttachmentPayload] = Field(default_factory=list)
    target_node_id: str | None = None


class MessageResponse(BaseModel):
    """Serialized message object returned by API endpoints."""

    id: str
    conversation_id: str
    sender_user_id: str
    sender_type: str
    content: str
    attachments: list[AttachmentPayload]
    delivery_status: str
    created_at: str


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
    )


def to_event_payload(event: ConversationEvent) -> dict[str, object]:
    """Convert persisted event row to SSE payload."""
    try:
        raw_payload = json.loads(event.payload_json)
        if not isinstance(raw_payload, dict):
            raw_payload = {}
    except json.JSONDecodeError:
        raw_payload = {}
    return {
        **raw_payload,
        "event_id": event.event_id,
        "conversation_id": event.conversation_id,
        "message_id": event.message_id,
        "delivery_status": event.delivery_status,
        "created_at": event.created_at,
    }


def parse_event_cursor(*, after_event_id: str | None, last_event_id: str | None) -> int:
    """Parse reconnect cursor from query/header with stable 400 semantics."""
    raw_value = after_event_id if after_event_id is not None else last_event_id
    if raw_value is None or raw_value.strip() == "":
        return 0
    try:
        cursor = int(raw_value)
    except ValueError as exc:  # pragma: no cover - exercised by contract tests
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="after_event_id must be an integer",
        ) from exc
    if cursor < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="after_event_id must be >= 0",
        )
    return cursor


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
    service: WebIMService = Depends(get_web_im_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> MessageResponse:
    """Create a message in a conversation and optionally relay it to one gateway."""
    assert_conversation_exists(request, conversation_id=conversation_id)
    try:
        created = service.create_message(
            conversation_id=conversation_id,
            sender_user_id=payload.sender_user_id,
            sender_type=payload.sender_type,
            content=payload.content,
            attachments=[
                Attachment(
                    url=item.url,
                    content_type=item.content_type,
                    file_name=item.file_name,
                )
                for item in payload.attachments
            ],
        )
    except ValueError as exc:
        raise map_message_write_error(exc) from exc
    if payload.target_node_id is not None:
        relay_result = service.enqueue_relay(
            message=created,
            target_node_id=payload.target_node_id,
            idempotency_key=idempotency_key or f"relay:{created.id}:{payload.target_node_id}",
            sender_user_id=payload.sender_user_id,
        )
        dispatched = await gateway_handler.push_relay_message(
            relay_task_id=relay_result.relay_task.relay_task_id,
            target_node_id=payload.target_node_id,
            payload=relay_result.relay_task.payload,
        )
        if not dispatched:
            gateway_handler.record_relay_failure(
                conversation_id=created.conversation_id,
                message_id=created.id,
                relay_task_id=relay_result.relay_task.relay_task_id,
                target_node_id=payload.target_node_id,
                reason="node_disconnected",
                guidance="检查目标节点连接状态后重试，或切换到在线节点。",
            )
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
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    before_message_id: str | None = Query(default=None),
    service: WebIMService = Depends(get_web_im_service),
) -> ListMessagesResponse:
    """List messages for one conversation in insertion order."""
    assert_conversation_exists(request, conversation_id=conversation_id)
    try:
        items = service.list_messages(
            conversation_id=conversation_id,
            limit=limit,
            before_message_id=before_message_id,
        )
    except ValueError as exc:
        detail = str(exc)
        http_status = status.HTTP_404_NOT_FOUND if detail == "before_message_id not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail) from exc
    next_before_message_id = items[0].id if len(items) == limit else None
    return ListMessagesResponse(
        items=[to_message_response(item) for item in items],
        next_before_message_id=next_before_message_id,
    )


@router.get("/im/v1/conversations/{conversation_id}/events")
async def stream_conversation_events(
    conversation_id: str,
    request: Request,
    after_event_id: str | None = Query(default=None),
    max_events: int = Query(default=50, ge=1, le=500),
    timeout_seconds: float = Query(default=1.0, ge=0.01, le=30.0),
    service: EventService = Depends(get_event_service),
) -> StreamingResponse:
    """Stream conversation events in SSE format with cursor-based replay."""
    assert_conversation_exists(request, conversation_id=conversation_id)
    cursor = parse_event_cursor(
        after_event_id=after_event_id,
        last_event_id=request.headers.get("Last-Event-ID"),
    )
    deadline = monotonic() + timeout_seconds

    async def event_generator():
        remaining = max_events
        current_cursor = cursor
        while remaining > 0:
            if await request.is_disconnected():
                break
            events = service.list_events(
                conversation_id=conversation_id,
                after_event_id=current_cursor,
                limit=remaining,
            )
            if events:
                for item in events:
                    yield encode_sse_event_frame(
                        event_id=item.event_id,
                        event_type=item.event_type,
                        data=to_event_payload(item),
                    )
                    current_cursor = item.event_id
                    remaining -= 1
                    if remaining <= 0:
                        break
                continue
            if monotonic() >= deadline:
                break
            yield encode_sse_heartbeat()
            await asyncio.sleep(0.02)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
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
