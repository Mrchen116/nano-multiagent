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
    token_usage: Mapping[str, Any] | None
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

    kind = _optional_text(payload.get("kind")) or ""

    def text_for(*kinds: str, field_name: str) -> str | None:
        if kind not in kinds:
            return None
        return _optional_text(payload.get(field_name))

    return StreamingDeltaEvent(
        kind=kind,
        run_id=_optional_text_or_none(payload.get("run_id")),
        agent_id=text_for("turn_start", field_name="agent_id"),
        conversation_id=text_for("turn_start", field_name="conversation_id"),
        message_id=text_for(
            "message_delta",
            "message_completed",
            "run_heartbeat",
            "thinking_segment",
            "tool_call_upserted",
            "tool_call_completed",
            "permission_request",
            "permission_resolved",
            field_name="message_id",
        ),
        to_user_id=text_for("turn_start", field_name="to_user_id"),
        agent_user_id=text_for("turn_start", field_name="agent_user_id"),
        delta_text=text_for("message_delta", field_name="delta_text"),
        final_content=text_for("message_completed", field_name="final_content"),
        delivery_status=text_for("message_completed", field_name="delivery_status"),
        token_usage=(
            _optional_mapping_or_none(payload.get("token_usage"))
            if kind == "message_completed"
            else None
        ),
        kernel_message_id=text_for("message_completed", field_name="kernel_message_id"),
        source=text_for("run_heartbeat", field_name="source"),
        text=text_for("thinking_segment", field_name="text"),
        tool_call=(
            _optional_mapping_or_none(payload.get("tool_call"))
            if kind in {"tool_call_upserted", "tool_call_completed"}
            else None
        ),
        permission_request=(
            _optional_mapping_or_none(payload.get("permission_request"))
            if kind == "permission_request"
            else None
        ),
        request_id=text_for("permission_resolved", field_name="request_id"),
        decision=text_for("permission_resolved", field_name="decision"),
        reason=text_for("run_terminal_reconcile", field_name="reason"),
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
        detail=_optional_mapping_or_none(payload.get("detail")),
        usage=_optional_int_mapping_or_none(payload.get("usage")),
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


def _optional_text_or_none(value: object) -> str | None:
    """Return a normalized text value without validating an unused protocol field."""

    return _optional_text(value) if isinstance(value, str) else None


def _require_mapping(value: object, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _optional_mapping(value: object, *, field_name: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _optional_mapping_or_none(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _optional_int_mapping_or_none(value: object) -> Mapping[str, int] | None:
    if not isinstance(value, Mapping):
        return None
    parsed: dict[str, int] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, int):
            return None
        parsed[key] = item
    return parsed


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
