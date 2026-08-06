"""Private message and timeline serialization helpers."""

from __future__ import annotations

import json

from IM.domain.models import (
    Actor,
    Attachment,
    Message,
    SystemNotice,
    ThinkingSegment,
    TokenUsage,
    ToolCall,
)
from IM.infra._helpers import _optional_text, _preview_from_event


def _attachment_to_dict(attachment: Attachment) -> dict[str, object]:
    """Convert one attachment dataclass to persisted/event payload shape."""
    payload: dict[str, object] = {"url": attachment.url}
    if attachment.content_type is not None:
        payload["content_type"] = attachment.content_type
    if attachment.file_name is not None:
        payload["file_name"] = attachment.file_name
    return payload


def _actor_to_event_dict(
    actor: Actor | None, *, fallback_type: str, fallback_id: str
) -> dict[str, str | None]:
    """Serialize an actor for live events without depending on API modules."""
    return {
        "type": actor.type if actor is not None else fallback_type,
        "id": actor.id if actor is not None else fallback_id,
        "display_name": actor.display_name if actor is not None else None,
    }


def _token_usage_to_event_dict(usage: TokenUsage | None) -> dict[str, int] | None:
    """Serialize token usage using the same shape as websocket payloads."""
    if usage is None:
        return None
    return {
        "output": int(usage.output),
        "context_used": int(usage.context_used),
        "context_window": int(usage.context_window),
        "total": int(usage.total)
        if usage.total is not None
        else int(usage.context_used) + int(usage.output),
        "cache_read_tokens": int(usage.cache_read_tokens),
        "cache_total_input_tokens": int(usage.cache_total_input_tokens),
    }


def _message_created_payload(message: Message) -> dict[str, object]:
    """Build the canonical live insert payload for a persisted message."""
    sender = _actor_to_event_dict(
        message.sender,
        fallback_type=message.sender_type,
        fallback_id=message.sender_user_id,
    )
    return {
        "conversation_id": message.conversation_id,
        "message_id": message.id,
        "sender_user_id": message.sender_user_id,
        "sender_type": message.sender_type,
        "sender": sender,
        "sender_display_name": sender.get("display_name"),
        "content": message.content,
        "attachments": [_attachment_to_dict(item) for item in message.attachments],
        "tool_calls": [_tool_call_to_dict(tc) for tc in (message.tool_calls or [])],
        "thinking": [
            {"seq": int(segment.seq), "text": segment.text}
            for segment in (message.thinking or [])
        ],
        "token_usage": _token_usage_to_event_dict(message.token_usage),
        "delivery_status": message.delivery_status,
        "created_at": message.created_at,
        "system_notice": _system_notice_to_dict(message.system_notice),
    }


def _system_notice_to_dict(notice: SystemNotice | None) -> dict[str, object] | None:
    """Serialize a structured system-notice snapshot for storage and live events."""
    if notice is None:
        return None
    return {
        "kind": notice.kind,
        "source_agent_id": notice.source_agent_id,
        "source_agent_display_name": notice.source_agent_display_name,
        "updated_targets": list(notice.updated_targets),
    }


def _encode_system_notice(notice: SystemNotice | None) -> str | None:
    payload = _system_notice_to_dict(notice)
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _decode_system_notice(value: object) -> SystemNotice | None:
    """Decode known complete sidecars; malformed history falls back to text."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    targets = parsed.get("updated_targets")
    if not isinstance(targets, list) or not all(
        isinstance(target, str) for target in targets
    ):
        return None
    try:
        return SystemNotice(
            kind=str(parsed.get("kind", "")),
            source_agent_id=str(parsed.get("source_agent_id", "")),
            source_agent_display_name=str(parsed.get("source_agent_display_name", "")),
            updated_targets=tuple(targets),
        )
    except ValueError:
        return None


def _message_reconciled_payload(message: Message) -> dict[str, object]:
    """Build a complete terminal projection for same-identity browser upsert."""

    return {
        **_message_created_payload(message),
        "elapsed_ms": message.elapsed_ms,
        "kernel_message_id": message.kernel_message_id,
        "permission_requests": list(message.permission_requests),
    }


def _encode_attachments(attachments: list[Attachment]) -> str:
    """Encode attachments JSON with stable field ordering."""
    payload = [_attachment_to_dict(item) for item in attachments]
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _tool_call_to_dict(tool_call: ToolCall) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": tool_call.id,
        "name": tool_call.name,
        "status": tool_call.status,
        "input": tool_call.input,
    }
    if tool_call.duration_ms is not None:
        payload["duration_ms"] = tool_call.duration_ms
    if tool_call.output is not None:
        payload["output"] = tool_call.output
    # bugfix-410-M2 (#97): persist sidecar badge reason alongside the call.
    if tool_call.reason is not None:
        payload["reason"] = tool_call.reason
    if tool_call.detail is not None:
        payload["detail"] = tool_call.detail
    # feat-425: persist tool-carried emoji alongside detail (omit when unset).
    if tool_call.emoji is not None:
        payload["emoji"] = tool_call.emoji
    # feat-434-M1: persist the user-decision verdict (omit when unset).
    if tool_call.approval is not None:
        payload["approval"] = tool_call.approval
    # feat-439-M2: persist the shared process-timeline seq (omit when unset/legacy).
    if tool_call.seq is not None:
        payload["seq"] = tool_call.seq
    return payload


def _encode_tool_calls(tool_calls: list[ToolCall]) -> str:
    return json.dumps(
        [_tool_call_to_dict(tc) for tc in tool_calls],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _load_permission_requests(raw_value: object) -> list[dict]:
    """Parse permission_request_json (always list-shaped, bugfix-367).

    开发态实现:列里必须存 list。坏数据(非 list / 解析失败)直接返回空 list,
    呼叫方可以从干净基线开始重试。不做旧 dict 形态的兼容(参见 fix.md "修复"段
    第二节:开发态,不做数据兼容)。
    """
    if raw_value is None:
        return []
    if not isinstance(raw_value, str) or not raw_value.strip():
        return []
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [dict(item) for item in parsed if isinstance(item, dict)]


def _decode_tool_calls(value: object) -> list[ToolCall] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    out: list[ToolCall] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                ToolCall(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    status=str(item.get("status", "")),
                    duration_ms=(
                        int(item["duration_ms"])
                        if isinstance(item.get("duration_ms"), (int, float))
                        else None
                    ),
                    input=dict(item.get("input"))
                    if isinstance(item.get("input"), dict)
                    else {},
                    output=item.get("output")
                    if isinstance(item.get("output"), str)
                    else None,
                    reason=item.get("reason")
                    if isinstance(item.get("reason"), str)
                    else None,
                    detail=item.get("detail")
                    if isinstance(item.get("detail"), dict)
                    else None,
                    emoji=item.get("emoji")
                    if isinstance(item.get("emoji"), str)
                    else None,
                    approval=item.get("approval")
                    if isinstance(item.get("approval"), str)
                    else None,
                    seq=item.get("seq") if isinstance(item.get("seq"), int) else None,
                )
            )
        except ValueError:
            # Malformed historical row — surface loudly: better than silently dropping a row's tool history.
            raise
    return out


def _next_process_seq(thinking: list[ThinkingSegment], tools: list[ToolCall]) -> int:
    """feat-439-M2: 下一个「过程项」seq = 思考与工具现有 seq 的 max + 1（从 0 起）。

    思考与工具共享这一个 per-message 计数器，按真实到达序单调递增、全局唯一 —— 渲染端
    据此 merge 成时间线，唯一性让 live 事件可幂等去重。旧工具行 seq 为 None，忽略。
    """
    seqs = [s.seq for s in thinking]
    seqs += [t.seq for t in tools if t.seq is not None]
    return (max(seqs) + 1) if seqs else 0


def _encode_thinking(segments: list[ThinkingSegment]) -> str:
    return json.dumps(
        [{"seq": int(s.seq), "text": s.text} for s in segments],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _decode_thinking(value: object) -> list[ThinkingSegment] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    out: list[ThinkingSegment] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append(
            ThinkingSegment(
                seq=int(item["seq"]) if isinstance(item.get("seq"), int) else 0,
                text=str(item.get("text", "")),
            )
        )
    return out or None


def _encode_token_usage(usage: TokenUsage | None) -> str | None:
    if usage is None:
        return None
    return json.dumps(
        {
            "output": int(usage.output),
            "context_used": int(usage.context_used),
            "context_window": int(usage.context_window),
            "total": int(usage.total),
            # feat-439-M1: 缓存命中两字段持久化。
            "cache_read_tokens": int(usage.cache_read_tokens),
            "cache_total_input_tokens": int(usage.cache_total_input_tokens),
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _decode_token_usage(value: object) -> TokenUsage | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    try:
        output = int(parsed["output"])
        context_used = int(parsed["context_used"])
        context_window = int(parsed["context_window"])
        # bugfix-390 FIX-1: pre-M17 rows have "total": null in JSON.
        # parsed.get("total", 0) returns None when the key exists with a null value
        # (dict.get default only fires when the key is absent), so int(None) would
        # raise TypeError → the except block silently returned None → chip not rendered.
        # Derive total here — this is the single authoritative decode entry point.
        _raw_total = parsed.get("total")
        total = int(_raw_total) if _raw_total is not None else context_used + output
        # feat-439-M1: 旧行无缓存字段 → 默认 0(同 total 兜底思路，缺键不致整体解码失败)。
        _raw_cache_read = parsed.get("cache_read_tokens")
        cache_read = int(_raw_cache_read) if _raw_cache_read is not None else 0
        _raw_cache_total = parsed.get("cache_total_input_tokens")
        cache_total_input = int(_raw_cache_total) if _raw_cache_total is not None else 0
        return TokenUsage(
            output=output,
            context_used=context_used,
            context_window=context_window,
            total=total,
            cache_read_tokens=cache_read,
            cache_total_input_tokens=cache_total_input,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _visible_content_from_event(
    *, event_type: str, payload: dict[str, object]
) -> str | None:
    """Return the visible bubble content represented by one event payload."""
    return _preview_from_event(event_type, payload)


def _synthetic_message_id_from_event_payload(payload: dict[str, object]) -> str | None:
    """Build the same stable synthetic message ids used by the frontend relay mapper."""
    message_id = _optional_text(payload.get("message_id"))
    if message_id is None:
        return None
    relay_task_id = _optional_text(payload.get("relay_task_id"))
    if relay_task_id is not None:
        return f"{message_id}:relay:{relay_task_id}"
    agent_id = _optional_text(payload.get("agent_id"))
    if agent_id is not None:
        return f"{message_id}:agent:{agent_id}"
    return f"{message_id}:agent"


def _upsert_message(messages: list[Message], candidate: Message) -> list[Message]:
    """Insert or refresh one message while preserving chronological ordering."""
    existing_index = next(
        (index for index, item in enumerate(messages) if item.id == candidate.id), -1
    )
    if existing_index == -1:
        return _sort_messages(messages + [candidate])
    existing = messages[existing_index]
    next_messages = list(messages)
    next_messages[existing_index] = Message(
        id=existing.id,
        conversation_id=existing.conversation_id,
        sender_user_id=candidate.sender_user_id,
        sender_type=candidate.sender_type,
        sender=candidate.sender,
        content=candidate.content
        if len(candidate.content) >= len(existing.content)
        else existing.content,
        attachments=candidate.attachments
        if candidate.attachments
        else existing.attachments,
        delivery_status=candidate.delivery_status,
        created_at=candidate.created_at,
        system_notice=candidate.system_notice or existing.system_notice,
    )
    return _sort_messages(next_messages)


def _sort_messages(messages: list[Message]) -> list[Message]:
    """Return messages ordered by created_at, then stable id."""
    return sorted(messages, key=lambda item: (item.created_at, item.id))


def _to_message_preview(*, content: str, attachments: list[Attachment]) -> str:
    """Choose the best lightweight inbox preview for one persisted message."""
    normalized_content = content.strip()
    if normalized_content:
        return normalized_content
    first_attachment = attachments[0] if attachments else None
    if first_attachment and first_attachment.file_name:
        return first_attachment.file_name
    return ""


def _decode_attachments(raw_value: str) -> list[Attachment]:
    """Decode attachments JSON into a stable list shape."""
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    results: list[Attachment] = []
    for item in decoded:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        content_type = item.get("content_type")
        file_name = item.get("file_name")
        results.append(
            Attachment(
                url=url,
                content_type=str(content_type)
                if content_type not in {None, ""}
                else None,
                file_name=str(file_name) if file_name not in {None, ""} else None,
            )
        )
    return results
