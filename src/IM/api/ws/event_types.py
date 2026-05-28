"""IM → Browser WS event type constants and payload builders.

These are the canonical names referenced by feat-340 design §4 (Frontend接收 WS 事件
schema). They are emitted by the event_bridge module and consumed by the browser SPA's
React Query cache patcher. Keeping name + payload shape in one module makes them easy
to grep and prevents drift between producer and consumer when M3+ frontend lands.

Event payload shape rules:
- Each payload is JSON-serializable dict[str, Any].
- ``conversation_id`` and ``message_id`` are present on all message/tool_call events so
  the frontend can route by conversation without an extra DB hit.
- Optional fields are emitted as ``None`` when absent (rather than omitted) so the
  frontend can rely on a stable shape; tool_call payload omits unset fields per ToolCall
  domain semantics (running calls have no duration/output yet).
"""

from __future__ import annotations

from typing import Any

from IM.domain.models import Message, TokenUsage, ToolCall


# Event type identifiers — keep as module-level constants; the EVENT_* names are stable
# wire identifiers, not refactor-safe Python symbols.
EVENT_MESSAGE_CREATED = "message.created"
EVENT_MESSAGE_DELTA = "message.delta"
EVENT_MESSAGE_COMPLETED = "message.completed"
EVENT_TOOL_CALL_UPSERTED = "tool_call.upserted"
EVENT_TOOL_CALL_COMPLETED = "tool_call.completed"
EVENT_NODE_STATUS_CHANGED = "node.status_changed"
EVENT_AGENT_STATUS_CHANGED = "agent.status_changed"
# feat-333-M2: permission ask flow — sent when agent awaits user decision and when resolved.
EVENT_PERMISSION_REQUEST = "permission.request"
EVENT_PERMISSION_RESOLVED = "permission.resolved"


def tool_call_to_dict(tool_call: ToolCall) -> dict[str, Any]:
    """Serialize one ToolCall for WS payloads.

    Mirrors ``IM.infra.repositories._tool_call_to_dict`` so persisted JSON and the
    live WS payload have identical shape — front-end uses one parser for both replay
    and live stream.
    """
    payload: dict[str, Any] = {
        "id": tool_call.id,
        "name": tool_call.name,
        "status": tool_call.status,
        "input": tool_call.input,
    }
    if tool_call.duration_ms is not None:
        payload["duration_ms"] = tool_call.duration_ms
    if tool_call.output is not None:
        payload["output"] = tool_call.output
    return payload


def token_usage_to_dict(usage: TokenUsage | None) -> dict[str, int] | None:
    if usage is None:
        return None
    return {
        "output": int(usage.output),
        "context_used": int(usage.context_used),
        "context_window": int(usage.context_window),
        # M17/R8-3: per-turn total (prompt+completion). Falls back to
        # context_used+output for old persisted rows where total wasn't stored.
        "total": int(usage.total) if usage.total else int(usage.context_used) + int(usage.output),
    }


def build_message_created_payload(*, message: Message) -> dict[str, Any]:
    """Build payload for the ``message.created`` event.

    Emitted when the event_bridge inserts the agent's empty placeholder message
    after kernel TURN_START. Front-end uses it to add a fresh bubble to the
    conversation cache before deltas start flowing.
    """
    return {
        "conversation_id": message.conversation_id,
        "message_id": message.id,
        "sender_user_id": message.sender_user_id,
        "sender_type": message.sender_type,
        "content": message.content,
        "tool_calls": [tool_call_to_dict(tc) for tc in (message.tool_calls or [])],
        "token_usage": token_usage_to_dict(message.token_usage),
        "delivery_status": message.delivery_status,
        "created_at": message.created_at,
    }


def build_message_delta_payload(
    *, conversation_id: str, message_id: str, delta_text: str
) -> dict[str, Any]:
    """Build payload for the ``message.delta`` event (incremental token append)."""
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "delta_text": delta_text,
    }


def build_message_completed_payload(
    *,
    conversation_id: str,
    message_id: str,
    content: str,
    token_usage: TokenUsage | None,
) -> dict[str, Any]:
    """Build payload for the ``message.completed`` event.

    Emitted on kernel run_status=completed. ``content`` is the final full string;
    front-end replaces accumulated delta state with this canonical text to avoid
    drift if any delta frames were dropped.
    """
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "content": content,
        "token_usage": token_usage_to_dict(token_usage),
    }


def build_tool_call_upserted_payload(
    *, conversation_id: str, message_id: str, tool_call: ToolCall
) -> dict[str, Any]:
    """Build payload for the ``tool_call.upserted`` event."""
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "tool_call": tool_call_to_dict(tool_call),
    }


def build_tool_call_completed_payload(
    *, conversation_id: str, message_id: str, tool_call: ToolCall
) -> dict[str, Any]:
    """Build payload for the ``tool_call.completed`` event.

    Carries the full updated ToolCall (status / duration_ms / output) so a frontend
    that missed the prior upserted event can still settle the panel correctly.
    """
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "tool_call": tool_call_to_dict(tool_call),
    }


def build_node_status_changed_payload(
    *,
    seq: int,
    node_id: str,
    status: str,
    last_heartbeat_at: str | None,
    last_error: str | None,
) -> dict[str, Any]:
    """Build payload for the ``node.status_changed`` event (feat-340 §4).

    Emitted by ``GatewayHandler`` on register / heartbeat status flip / disconnect
    / offline-timeout. ``seq`` is owner-scoped monotonic — frontend uses it to
    detect gaps. ``last_error`` is None when status is online or no error context.
    """
    return {
        "seq": seq,
        "node_id": node_id,
        "status": status,
        "last_heartbeat_at": last_heartbeat_at,
        "last_error": last_error,
    }


def build_agent_status_changed_payload(
    *, seq: int, agent_id: str, status: str
) -> dict[str, Any]:
    """Build payload for the ``agent.status_changed`` event.

    Per feat-340 决策 11: agent status folds onto the hosting node.status — when
    the node flips, all agents advertised by that node emit a status change with
    the same value. ``seq`` shares the owner-scoped counter with node events.
    """
    return {"seq": seq, "agent_id": agent_id, "status": status}
