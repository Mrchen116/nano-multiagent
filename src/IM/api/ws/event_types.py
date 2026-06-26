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

from IM.domain.models import Message, ThinkingSegment, TokenUsage, ToolCall


# Event type identifiers — keep as module-level constants; the EVENT_* names are stable
# wire identifiers, not refactor-safe Python symbols.
EVENT_MESSAGE_CREATED = "message.created"
EVENT_MESSAGE_DELTA = "message.delta"
EVENT_MESSAGE_COMPLETED = "message.completed"
EVENT_TOOL_CALL_UPSERTED = "tool_call.upserted"
EVENT_TOOL_CALL_COMPLETED = "tool_call.completed"
# feat-439-M2: one thinking process item arrived for an in-flight agent message.
EVENT_THINKING_SEGMENT = "thinking.segment"
EVENT_NODE_STATUS_CHANGED = "node.status_changed"
EVENT_AGENT_STATUS_CHANGED = "agent.status_changed"
# feat-333-M2: permission ask flow — sent when agent awaits user decision and when resolved.
EVENT_PERMISSION_REQUEST = "permission.request"
EVENT_PERMISSION_RESOLVED = "permission.resolved"
# bugfix-417-M3: liveness heartbeat — advances the message's last_evt so the relay
# watchdog sees an alive-but-quiet run (silent long tool / awaiting LLM / parked on a
# permission decision) as live. Pure liveness; carries no content/tool_calls.
EVENT_RUN_HEARTBEAT = "run.heartbeat"


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
    # bugfix-410-M2 (#97): sidecar badge reason, present only on non-success terminal.
    if tool_call.reason is not None:
        payload["reason"] = tool_call.reason
    if tool_call.detail is not None:
        payload["detail"] = tool_call.detail
    # feat-425: tool-carried emoji, present only when the tool declared one.
    if tool_call.emoji is not None:
        payload["emoji"] = tool_call.emoji
    # feat-434-M1: user-decision verdict, present only for cards the user decided.
    if tool_call.approval is not None:
        payload["approval"] = tool_call.approval
    # feat-439-M2: shared process-timeline seq (omit when unset/legacy).
    if tool_call.seq is not None:
        payload["seq"] = tool_call.seq
    return payload


def thinking_segment_to_dict(segment: ThinkingSegment) -> dict[str, Any]:
    """feat-439-M2: serialize one thinking process item for WS / history payloads.

    Mirrors ``IM.infra.repositories._encode_thinking`` so live events and persisted
    rows decode to the same {seq, text} shape on the frontend.
    """
    return {"seq": int(segment.seq), "text": segment.text}


def token_usage_to_dict(usage: TokenUsage | None) -> dict[str, int] | None:
    if usage is None:
        return None
    return {
        "output": int(usage.output),
        "context_used": int(usage.context_used),
        "context_window": int(usage.context_window),
        # M17/R8-3: per-turn total (prompt+completion). Falls back to
        # context_used+output for old persisted rows where total wasn't stored.
        "total": int(usage.total)
        if usage.total
        else int(usage.context_used) + int(usage.output),
        # feat-439-M1: 缓存命中两字段恒带出(无命中=0)，前端据此渲染命中行 + 百分比。
        "cache_read_tokens": int(usage.cache_read_tokens),
        "cache_total_input_tokens": int(usage.cache_total_input_tokens),
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
        # feat-439-M2: 整轮多段思考随气泡创建一并下发，历史回放还原过程盘。
        "thinking": [thinking_segment_to_dict(s) for s in (message.thinking or [])],
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
    elapsed_ms: int | None = None,
) -> dict[str, Any]:
    """Build payload for the ``message.completed`` event.

    Emitted on kernel run_status=completed. ``content`` is the final full string;
    front-end replaces accumulated delta state with this canonical text to avoid
    drift if any delta frames were dropped.

    Args:
        conversation_id: Conversation the message belongs to.
        message_id: Agent message that just completed.
        content: Final full text content (replaces accumulated deltas on the client).
        token_usage: Per-turn token accounting; ``None`` for legacy / non-LLM turns.
        elapsed_ms: feat-414 — 本轮墙钟耗时（毫秒）。None 表示未计算（历史消息）。
    """
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "content": content,
        "token_usage": token_usage_to_dict(token_usage),
        "elapsed_ms": elapsed_ms,
    }


def build_thinking_segment_payload(
    *, conversation_id: str, message_id: str, segment: ThinkingSegment
) -> dict[str, Any]:
    """Build payload for the ``thinking.segment`` event (one process item arrived)."""
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "thinking_segment": thinking_segment_to_dict(segment),
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
