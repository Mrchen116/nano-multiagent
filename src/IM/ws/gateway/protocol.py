"""Typed facts and strict validation for the IM Gateway wire protocol."""

from __future__ import annotations

import json
from typing import Any

from IM.domain.models import TokenUsage, ToolCall

"""Package-local parsers for Gateway websocket runtime protocol frames."""

from dataclasses import dataclass
from typing import Mapping


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
            "message_discarded",
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
        reason=text_for(
            "run_terminal_reconcile", "message_discarded", field_name="reason"
        ),
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


def _encode_status_frame(*, event_type: str, payload: dict[str, object]) -> str:
    """Encode one status-change frame for the browser user stream.

    Mirrors ``encode_user_stream_event_frame`` shape (op=event, event_type, data)
    so the SPA reducer can dispatch by ``event_type`` without a separate parser.
    """
    body = {"op": "event", "event_type": event_type, "data": payload}
    return json.dumps(body, ensure_ascii=True, separators=(",", ":"))


def _decode_message(raw_message: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("message must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("message must be a JSON object")
    return parsed


def _require_message_type(payload: dict[str, Any]) -> str:
    return _require_text(payload.get("type"), field_name="type")


# WS-layer strict field helpers — intentionally NOT unified with IM/infra/_helpers.py.
# At the WS boundary a missing or non-string required field means the gateway sent a
# malformed frame, which is a protocol error.  Fail-fast here (raise ValueError/
# RuntimeError) prevents silently routing bad data into the domain layer.
# The _helpers.py variants return None on missing values; that lenient behaviour is
# correct for HTTP request parsing, not for WS frames where the schema is contract-level.
def _boundary_rejection_code(error: ValueError) -> str:
    """Map durable boundary validation failures to dispatcher quarantine codes."""
    message = str(error)
    if "anchor" in message and "not found" in message:
        return "anchor_not_found"
    if "participant" in message:
        return "agent_not_participant"
    if "agent" in message and "not found" in message:
        return "agent_not_found"
    if "conversation" in message and "not found" in message:
        return "conversation_not_found"
    return "bad_payload"


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_non_negative_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _optional_non_negative_int(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    return _require_non_negative_int(value, field_name=field_name)


def _require_dict(value: object, *, field_name: str) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_string_list(value: object, *, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return [item for item in value]


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text fields must be strings when provided")
    stripped = value.strip()
    return stripped or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("optional integer fields must be integers when provided")
    return value


def _optional_dict(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("optional object fields must be objects when provided")
    return value


def _normalize_agent_string_list_seed(
    raw: dict[object, object],
) -> dict[str, list[str]]:
    """Normalize an per-agent string-list seed field from a node.register payload.

    Invalid entries are dropped so a malformed single-agent seed cannot break
    registration for the whole node.
    """
    result: dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return result
    for agent_id, items in raw.items():
        if not isinstance(agent_id, str) or not agent_id.strip():
            continue
        if isinstance(items, list):
            cleaned = [item for item in items if isinstance(item, str)]
            if cleaned:
                result[agent_id] = cleaned
    return result


def _optional_usage(value: object) -> dict[str, int] | None:
    if value is None:
        return None
    payload = _require_dict(value, field_name="usage")
    prompt_tokens = _optional_int(payload.get("prompt_tokens"))
    completion_tokens = _optional_int(payload.get("completion_tokens"))
    if prompt_tokens is None or completion_tokens is None:
        return None
    total_tokens = _optional_int(payload.get("total_tokens"))
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": max(prompt_tokens, 0),
        "completion_tokens": max(completion_tokens, 0),
        "total_tokens": max(total_tokens, 0),
    }


def _parse_token_usage(value: object) -> TokenUsage | None:
    """Parse a streaming_delta token_usage dict into a TokenUsage domain object."""
    if value is None or not isinstance(value, dict):
        return None
    prompt = value.get("prompt") or value.get("prompt_tokens")
    completion = value.get("completion") or value.get("completion_tokens")
    total = value.get("total") or value.get("total_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    if not isinstance(total, int):
        total = prompt + completion
    # context_window is the model's actual maximum context size, passed through from
    # the kernel's CompactionSettings.context_window via the turn_end event chain.
    # 0 means unknown (kernel didn't send it); the frontend treats 0 as "not available".
    cw_raw = value.get("context_window")
    context_window = max(int(cw_raw), 0) if isinstance(cw_raw, int) else 0
    # feat-439-M1: 缓存命中两字段(短键 cache_read / cache_total_input，由 gateway 白名单带出)。
    # 缺省(旧 gateway / 无缓存信息)→ 0，前端按「缓存命中 0 (0%)」空态渲染。
    cache_read_raw = value.get("cache_read")
    cache_read = max(int(cache_read_raw), 0) if isinstance(cache_read_raw, int) else 0
    cache_total_raw = value.get("cache_total_input")
    cache_total_input = (
        max(int(cache_total_raw), 0) if isinstance(cache_total_raw, int) else 0
    )
    return TokenUsage(
        output=max(completion, 0),
        context_used=max(prompt, 0),
        context_window=context_window,
        total=max(total, 0),
        cache_read_tokens=cache_read,
        cache_total_input_tokens=cache_total_input,
    )


def _parse_tool_call(value: object) -> ToolCall:
    """Parse a streaming_delta tool_call dict into a ToolCall domain object."""
    if not isinstance(value, dict):
        raise ValueError("tool_call must be an object")
    tc_id = str(value.get("id") or "")
    name = str(value.get("name") or "")
    status = str(value.get("status") or "running")
    input_data = value.get("input") or {}
    if not isinstance(input_data, dict):
        input_data = {}
    duration_ms = value.get("duration_ms")
    output = value.get("output")
    reason = value.get("reason")
    detail = value.get("detail")
    emoji = value.get("emoji")
    approval = value.get("approval")
    return ToolCall(
        id=tc_id,
        name=name,
        status=status,  # type: ignore[arg-type]
        input=input_data,
        duration_ms=int(duration_ms) if isinstance(duration_ms, (int, float)) else None,
        output=str(output) if output is not None else None,
        reason=str(reason) if isinstance(reason, str) and reason else None,
        detail=detail if isinstance(detail, dict) else None,
        emoji=emoji if isinstance(emoji, str) and emoji else None,
        approval=str(approval) if isinstance(approval, str) and approval else None,
    )


def _not_registered_error(*, node_id: str) -> dict[str, object]:
    return {
        "type": "error",
        "payload": {
            "code": "node_not_registered",
            "message": f"node {node_id} is not registered",
        },
    }


__all__ = [name for name in globals() if not name.startswith("__")]
