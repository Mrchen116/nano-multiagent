"""Package-local parsers for Gateway websocket runtime protocol frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RelayMessageFrame:
    relay_task_id: str
    idempotency_key: str
    conversation_id: str
    message_id: str
    sender_user_id: str
    text: str
    agent_id: str | None
    metadata: Mapping[str, Any]
    external_source: str | None
    external_chat_id: str | None
    conversation_type: str | None
    trigger_source: str | None


@dataclass(frozen=True, slots=True)
class StreamingDeltaEvent:
    kind: str
    run_id: str | None
    agent_id: str | None
    conversation_id: str | None
    message_id: str | None
    to_user_id: str | None
    agent_user_id: str | None
    delta_text: str | None
    final_content: str | None
    delivery_status: str | None
    token_usage: Mapping[str, int] | None
    kernel_message_id: str | None
    source: str | None
    text: str | None
    tool_call: Mapping[str, Any] | None
    permission_request: Mapping[str, Any] | None
    request_id: str | None
    decision: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class DeliveryReceiptEvent:
    node_id: str
    relay_task_id: str
    delivery_status: str
    detail: str | None
    target: str | None


@dataclass(frozen=True, slots=True)
class NodeReportEvent:
    node_id: str
    run_id: str
    status: str
    agent_id: str | None
    session_key: str | None
    conversation_id: str | None
    message_id: str | None
    summary: str | None
    guidance: str | None
    detail: Mapping[str, Any] | None
    usage: Mapping[str, int] | None


def parse_relay_message_frame(payload: Mapping[str, object]) -> RelayMessageFrame:
    """Parse an IM-produced ``relay.message`` payload into typed protocol facts."""

    message = _require_mapping(payload.get("message"), field_name="message")
    metadata = _optional_mapping(payload.get("metadata"), field_name="metadata") or {}
    return RelayMessageFrame(
        relay_task_id=_require_text(
            payload.get("relay_task_id"), field_name="relay_task_id"
        ),
        idempotency_key=_require_text(
            payload.get("idempotency_key"), field_name="idempotency_key"
        ),
        conversation_id=_require_text(
            payload.get("conversation_id") or message.get("conversation_id"),
            field_name="conversation_id",
        ),
        message_id=_require_text(message.get("id"), field_name="message.id"),
        sender_user_id=_require_text(
            message.get("sender_user_id"), field_name="message.sender_user_id"
        ),
        text=_require_text(message.get("content"), field_name="message.content"),
        agent_id=_optional_text(payload.get("agent_id")),
        metadata=metadata,
        external_source=_optional_text(metadata.get("external_source")),
        external_chat_id=_optional_text(metadata.get("external_chat_id")),
        conversation_type=_optional_text(metadata.get("conversation_type")),
        trigger_source=_optional_text(metadata.get("trigger_source")),
    )


def parse_streaming_delta_event(payload: Mapping[str, object]) -> StreamingDeltaEvent:
    """Parse a Gateway ``node.streaming_delta`` payload."""

    return StreamingDeltaEvent(
        kind=_optional_text(payload.get("kind")) or "",
        run_id=_optional_text(payload.get("run_id")),
        agent_id=_optional_text(payload.get("agent_id")),
        conversation_id=_optional_text(payload.get("conversation_id")),
        message_id=_optional_text(payload.get("message_id")),
        to_user_id=_optional_text(payload.get("to_user_id")),
        agent_user_id=_optional_text(payload.get("agent_user_id")),
        delta_text=_optional_text(payload.get("delta_text")),
        final_content=_optional_text(payload.get("final_content")),
        delivery_status=_optional_text(payload.get("delivery_status")),
        token_usage=_optional_int_mapping(
            payload.get("token_usage"), field_name="token_usage"
        ),
        kernel_message_id=_optional_text(payload.get("kernel_message_id")),
        source=_optional_text(payload.get("source")),
        text=_optional_text(payload.get("text")),
        tool_call=_optional_mapping(payload.get("tool_call"), field_name="tool_call"),
        permission_request=_optional_mapping(
            payload.get("permission_request"), field_name="permission_request"
        ),
        request_id=_optional_text(payload.get("request_id")),
        decision=_optional_text(payload.get("decision")),
        reason=_optional_text(payload.get("reason")),
    )


def parse_delivery_receipt_event(
    payload: Mapping[str, object],
) -> DeliveryReceiptEvent:
    """Parse a Gateway ``node.delivery_receipt`` payload."""

    return DeliveryReceiptEvent(
        node_id=_require_text(payload.get("node_id"), field_name="node_id"),
        relay_task_id=_require_text(
            payload.get("relay_task_id"), field_name="relay_task_id"
        ),
        delivery_status=_require_text(
            payload.get("delivery_status"), field_name="delivery_status"
        ),
        detail=_optional_text(payload.get("detail")),
        target=_optional_text(payload.get("target")),
    )


def parse_node_report_event(payload: Mapping[str, object]) -> NodeReportEvent:
    """Parse a Gateway ``node.report`` payload."""

    return NodeReportEvent(
        node_id=_require_text(payload.get("node_id"), field_name="node_id"),
        run_id=_require_text(payload.get("run_id"), field_name="run_id"),
        status=_require_text(payload.get("status"), field_name="status"),
        agent_id=_optional_text(payload.get("agent_id")),
        session_key=_optional_text(payload.get("session_key")),
        conversation_id=_optional_text(payload.get("conversation_id")),
        message_id=_optional_text(payload.get("message_id")),
        summary=_optional_text(payload.get("summary")),
        guidance=_optional_text(payload.get("guidance")),
        detail=_optional_mapping(payload.get("detail"), field_name="detail"),
        usage=_optional_int_mapping(payload.get("usage"), field_name="usage"),
    )


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text fields must be strings when provided")
    stripped = value.strip()
    return stripped or None


def _require_mapping(value: object, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _optional_mapping(
    value: object, *, field_name: str
) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _optional_int_mapping(
    value: object, *, field_name: str
) -> Mapping[str, int] | None:
    if value is None:
        return None
    raw = _require_mapping(value, field_name=field_name)
    parsed: dict[str, int] = {}
    for key, item in raw.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} keys must be strings")
        if not isinstance(item, int):
            raise ValueError(f"{field_name}.{key} must be an integer")
        parsed[key] = item
    return parsed
