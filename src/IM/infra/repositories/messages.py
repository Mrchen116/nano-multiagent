"""SQLite repositories for IM users, conversations, and messages."""

from collections.abc import Callable
from dataclasses import replace
import hashlib
import json
import sqlite3
from uuid import uuid4

from IM.domain.models import (
    Actor,
    Attachment,
    ConversationEvent,
    Message,
    ThinkingSegment,
    TokenUsage,
    ToolCall,
)
from IM.infra._helpers import (
    _optional_text,
)


from IM.infra._timestamps import utc_now
from IM.infra.repositories._event_rows import insert_event_row

from IM.infra.repositories._message_projection import (
    _attachment_to_dict,
    _decode_attachments,
    _decode_thinking,
    _decode_token_usage,
    _decode_tool_calls,
    _encode_attachments,
    _encode_thinking,
    _encode_token_usage,
    _encode_tool_calls,
    _load_permission_requests,
    _message_created_payload,
    _next_process_seq,
    _synthetic_message_id_from_event_payload,
    _to_message_preview,
    _upsert_message,
    _visible_content_from_event,
)


class MessageRepository:
    """Persist and query conversation messages."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        notify: Callable[[ConversationEvent], None] | None = None,
    ) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
            notify: 可选；消息相关事件在事务提交后广播（与 EventRepository 独立写路径）。
        """
        self._connection = connection
        self._notify = notify

    def create_message(
        self,
        *,
        conversation_id: str,
        sender_user_id: str,
        content: str,
        sender_type: str = "user",
        attachments: list[Attachment] | None = None,
        auto_complete_delivery: bool = True,
        tool_calls: list[ToolCall] | None = None,
        token_usage: TokenUsage | None = None,
        allow_empty: bool = False,
        kernel_message_id: str | None = None,
        delivery_status: str | None = None,
        sender_display_name: str | None = None,
        emit_created_event: bool = False,
        caller_idempotency_key: str | None = None,
    ) -> Message:
        """Create a message in a conversation.

        Args:
            conversation_id: Target conversation identifier.
            sender_user_id: Sender user identifier.
            content: Plain text body of the message.
            sender_type: Sender kind; must be user, agent, or system.
            attachments: Attachment descriptors stored alongside the message.
            auto_complete_delivery: When True, local-only writes synchronously close delivery to completed
                and persist both message.sent and message.delivered. Relay-backed writes pass False so
                gateway receipts remain the single source of truth for completion.

        Returns:
            Created message entity.

        Raises:
            ValueError: When conversation/sender is missing, owner scope mismatches, sender type is invalid,
                or sender is not a participant for user-originated messages.
        """
        normalized_attachments = _normalize_attachments(attachments)
        # feat-340-M2: agent-runtime messages start empty and stream content via update_runtime_state;
        # callers opt in with allow_empty so we don't break the user-message invariant.
        if not allow_empty and not content.strip() and not normalized_attachments:
            raise ValueError("message must include content or attachments")
        if sender_type not in {"user", "agent", "system"}:
            raise ValueError("sender_type must be one of: user, agent, system")
        normalized_idempotency_key = (
            caller_idempotency_key.strip() if caller_idempotency_key else None
        )
        if normalized_idempotency_key == "":
            raise ValueError("caller_idempotency_key must be non-empty")
        conversation_exists = self._connection.execute(
            "SELECT owner_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if conversation_exists is None:
            raise ValueError("conversation_id not found")
        stored_idempotency_key = (
            _scoped_caller_idempotency_key(conversation_id, normalized_idempotency_key)
            if normalized_idempotency_key is not None
            else None
        )
        if stored_idempotency_key is not None:
            existing = self._connection.execute(
                """
                SELECT
                    messages.id,
                    messages.conversation_id,
                    messages.sender_user_id,
                    messages.sender_type,
                    messages.content,
                    messages.attachments_json,
                    messages.delivery_status,
                    messages.created_at,
                    messages.tool_calls_json,
                    messages.thinking_json,
                    messages.token_usage_json,
                    messages.elapsed_ms,
                    messages.permission_request_json,
                    messages.kernel_message_id,
                    users.username AS sender_username,
                    COALESCE(messages.sender_display_name, users.display_name)
                        AS sender_display_name
                FROM messages
                LEFT JOIN users ON users.id = messages.sender_user_id
                WHERE messages.conversation_id = ?
                  AND messages.caller_idempotency_key IN (?, ?)
                """,
                (
                    conversation_id,
                    stored_idempotency_key,
                    normalized_idempotency_key,
                ),
            ).fetchone()
            if existing is not None:
                return self._message_from_row(existing)

        sender_user = self._resolve_sender_user_row(
            sender_user_id=sender_user_id,
            sender_type=sender_type,
        )
        if sender_user is None:
            raise ValueError("sender_user_id not found")
        resolved_sender_user_id = str(sender_user["id"])
        display_name_override = (
            sender_display_name.strip() if sender_display_name is not None else None
        )
        if display_name_override == "":
            display_name_override = None
        sender_actor = self._actor_from_sender_row(
            sender_type=sender_type,
            sender_user_id=resolved_sender_user_id,
            sender_username=str(sender_user["username"]),
            sender_display_name=display_name_override
            or (
                str(sender_user["display_name"])
                if sender_user["display_name"] is not None
                else None
            ),
        )
        participant_exists = self._connection.execute(
            """
            SELECT 1
            FROM conversation_participants
            WHERE conversation_id = ? AND user_id = ?
            """,
            (conversation_id, resolved_sender_user_id),
        ).fetchone()
        # System messages are server-originated and bypass the owner scope check;
        # they can be injected into any conversation regardless of participant/owner alignment.
        if sender_type != "system":
            if participant_exists is None and str(sender_user["owner_id"]) != str(
                conversation_exists["owner_id"]
            ):
                raise ValueError("sender_user_id is outside conversation owner scope")

        if sender_type == "user" and participant_exists is None:
            raise ValueError("sender_user_id is not a participant of conversation")

        message_id = uuid4().hex
        created_at = utc_now()
        initial_status = "sent"
        # feat-445-M2 #8: an explicit delivery_status (used by fork's history copy) wins
        # so a copied bubble preserves the source's terminal state (e.g. "failed") instead
        # of being force-rewritten to "completed".
        if delivery_status is not None:
            final_status = delivery_status
        else:
            final_status = "completed" if auto_complete_delivery else initial_status
        attachments_json = _encode_attachments(normalized_attachments)
        event_attachments = [
            _attachment_to_dict(item) for item in normalized_attachments
        ]
        sent_payload = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "sender_user_id": resolved_sender_user_id,
            "sender_type": sender_type,
            "sender": {"type": sender_actor.type, "id": sender_actor.id},
            "attachments": event_attachments,
            "progress_state": "pending",
            "semantic": "persisted_to_im",
        }
        pending_live_events: list[ConversationEvent] = []
        normalized_tool_calls = _normalize_tool_calls(tool_calls)
        tool_calls_json = (
            _encode_tool_calls(normalized_tool_calls)
            if normalized_tool_calls is not None
            else None
        )
        token_usage_json = _encode_token_usage(token_usage)
        created_message = Message(
            id=message_id,
            conversation_id=conversation_id,
            sender_user_id=resolved_sender_user_id,
            sender_type=sender_type,
            sender=sender_actor,
            content=content,
            attachments=normalized_attachments,
            delivery_status=final_status,
            created_at=created_at,
            tool_calls=normalized_tool_calls,
            token_usage=token_usage,
            # feat-414: 建行时始终为 None，由 on_message_completed 写入。
            elapsed_ms=None,
            kernel_message_id=kernel_message_id,
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO messages(
                    id,
                    conversation_id,
                    sender_user_id,
                    sender_type,
                    content,
                    attachments_json,
                    delivery_status,
                    created_at,
                    tool_calls_json,
                    token_usage_json,
                    kernel_message_id,
                    sender_display_name,
                    caller_idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    resolved_sender_user_id,
                    sender_type,
                    content,
                    attachments_json,
                    initial_status,
                    created_at,
                    tool_calls_json,
                    token_usage_json,
                    kernel_message_id,
                    display_name_override,
                    stored_idempotency_key,
                ),
            )
            pending_live_events.append(
                self._insert_event(
                    conversation_id=conversation_id,
                    message_id=message_id,
                    event_type="message.sent",
                    delivery_status=initial_status,
                    payload=sent_payload,
                )
            )
            if emit_created_event:
                pending_live_events.append(
                    self._insert_event(
                        conversation_id=conversation_id,
                        message_id=message_id,
                        event_type="message.created",
                        delivery_status=final_status,
                        payload=_message_created_payload(created_message),
                    )
                )
            if auto_complete_delivery:
                # feat-445-M3 清理-1: the delivered event must carry the message's actual
                # terminal status (final_status), not a hardcoded "completed". fork copies a
                # source "failed" bubble with delivery_status="failed" + auto_complete=True;
                # hardcoding "completed" here made a subscriber see the bubble flash completed
                # then flip back to failed on refresh (the DB UPDATE below already uses
                # final_status — this kept the SSE event out of sync).
                pending_live_events.append(
                    self._insert_event(
                        conversation_id=conversation_id,
                        message_id=message_id,
                        event_type="message.delivered",
                        delivery_status=final_status,
                        payload={
                            **sent_payload,
                            "progress_state": "completed",
                            "semantic": "message_history_ready",
                        },
                    )
                )
                self._connection.execute(
                    "UPDATE messages SET delivery_status = ? WHERE id = ?",
                    (final_status, message_id),
                )
            # Only increment unread_count for messages from other participants, not the conversation owner's own messages.
            owner_id = str(conversation_exists["owner_id"])
            is_own_message = resolved_sender_user_id == owner_id
            if is_own_message:
                self._connection.execute(
                    "UPDATE conversations SET last_message_preview = ?, last_message_at = ? WHERE id = ?",
                    (
                        _to_message_preview(
                            content=content, attachments=normalized_attachments
                        ),
                        created_at,
                        conversation_id,
                    ),
                )
            else:
                self._connection.execute(
                    "UPDATE conversations SET last_message_preview = ?, last_message_at = ?, unread_count = unread_count + 1 WHERE id = ?",
                    (
                        _to_message_preview(
                            content=content, attachments=normalized_attachments
                        ),
                        created_at,
                        conversation_id,
                    ),
                )
        if self._notify is not None:
            for live_event in pending_live_events:
                self._notify(live_event)
        return created_message

    def discard_running_agent_message(
        self, *, message_id: str, reason: str
    ) -> ConversationEvent | None:
        """Atomically remove a provisional agent message and persist its tombstone.

        Args:
            message_id: Running agent placeholder selected for rollback.
            reason: Stable machine-readable reason included in the tombstone payload.

        Returns:
            The persisted tombstone, or None when the message was already discarded.

        Raises:
            ValueError: When the target exists but is not a running agent message.

        Side Effects:
            Deletes the message and its message-scoped events. A ``message.discarded``
            event with a null foreign key remains replayable for connected clients.
        """

        with self._connection:
            row = self._connection.execute(
                "SELECT conversation_id, sender_type, delivery_status "
                "FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return None
            if row["sender_type"] != "agent" or row["delivery_status"] != "running":
                raise ValueError("only a running agent message can be discarded")
            conversation_id = str(row["conversation_id"])
            deleted = self._connection.execute(
                "DELETE FROM messages "
                "WHERE id = ? AND sender_type = 'agent' AND delivery_status = 'running'",
                (message_id,),
            )
            if deleted.rowcount != 1:
                raise ValueError("only a running agent message can be discarded")
            latest = self._connection.execute(
                """
                SELECT content, attachments_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
            latest_preview = (
                _to_message_preview(
                    content=str(latest["content"]),
                    attachments=_decode_attachments(str(latest["attachments_json"])),
                )
                if latest is not None
                else ""
            )
            latest_at = str(latest["created_at"]) if latest is not None else None
            # turn_start increments unread_count for an agent placeholder. Roll back
            # that projection too; MAX handles a user who read the conversation while
            # the run was still in flight.
            self._connection.execute(
                """
                UPDATE conversations
                SET last_message_preview = ?,
                    last_message_at = ?,
                    unread_count = MAX(unread_count - 1, 0)
                WHERE id = ?
                """,
                (latest_preview, latest_at, conversation_id),
            )
            # Insert after the delete so the message's cascaded stream events disappear
            # first. The tombstone intentionally has no message FK and survives replay.
            tombstone = self._insert_event(
                conversation_id=conversation_id,
                message_id=None,
                event_type="message.discarded",
                delivery_status="completed",
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "reason": reason,
                },
            )
        # Publish only after the delete + tombstone transaction commits. Repeated
        # discard calls return above, so connected clients receive exactly one rollback.
        if self._notify is not None:
            self._notify(tombstone)
        return tombstone

    def update_runtime_state(
        self,
        *,
        message_id: str,
        content_append: str | None = None,
        content_replace: str | None = None,
        tool_calls_upsert: list[ToolCall] | None = None,
        token_usage: TokenUsage | None = None,
        delivery_status: str | None = None,
        elapsed_ms: int | None = None,
        kernel_message_id: str | None = None,
    ) -> Message:
        """Apply one runtime-stream patch to an agent message.

        Designed for feat-340-M2 event bridge: kernel emits incremental deltas which
        we accumulate into the persisted message row, so that ``list_messages`` can
        reconstruct the final agent reply (text + tool calls + token usage) on reload
        without replaying every event.

        Args:
            message_id: Target message identifier.
            content_append: When provided, concatenated onto current message content.
                Mutually exclusive with ``content_replace``.
            content_replace: When provided, overwrites current message content.
            tool_calls_upsert: Tool calls to upsert by ``id`` into ``tool_calls_json``.
                New ids append; existing ids replace in place to preserve display order.
            token_usage: When provided, overwrites ``token_usage_json``.
            delivery_status: When provided, updates ``delivery_status`` column.
            elapsed_ms: feat-414 — 本轮墙钟耗时（毫秒）。非 None 时写入列；None（默认）时
                使用 Sentinel 机制跳过（同 token_usage），不清掉已有值。

        Returns:
            Refreshed Message entity reflecting the patch.

        Raises:
            ValueError: When ``message_id`` does not exist or arguments conflict.
        """
        if content_append is not None and content_replace is not None:
            raise ValueError(
                "content_append and content_replace are mutually exclusive"
            )
        row = self._connection.execute(
            "SELECT content, tool_calls_json, thinking_json, token_usage_json, conversation_id FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"message_id not found: {message_id}")

        next_content: str | None = None
        if content_replace is not None:
            next_content = content_replace
        elif content_append is not None:
            next_content = (
                str(row["content"]) if row["content"] is not None else ""
            ) + content_append

        next_tool_calls_json: str | None | object = _UNSET
        if tool_calls_upsert is not None:
            existing = _decode_tool_calls(row["tool_calls_json"]) or []
            existing_thinking = (
                _decode_thinking(row["thinking_json"])
                if "thinking_json" in row.keys()
                else None
            ) or []
            existing_by_id = {tc.id: tc for tc in existing}
            order: list[str] = [tc.id for tc in existing]
            for upsert in _normalize_tool_calls(tool_calls_upsert) or []:
                if upsert.id not in existing_by_id:
                    # feat-439-M2: new tool id → assign the shared process-timeline seq
                    # (max over current thinking + tools, +1) so thinking/tools share one
                    # monotonic arrival order. A later same-id upsert (completed) keeps it.
                    order.append(upsert.id)
                    seq = _next_process_seq(
                        existing_thinking, list(existing_by_id.values())
                    )
                    existing_by_id[upsert.id] = replace(upsert, seq=seq)
                else:
                    # Preserve the seq assigned at first upsert; the gateway never sends
                    # seq (IM owns assignment), so a None on the incoming completed frame
                    # must not wipe it.
                    prior_seq = existing_by_id[upsert.id].seq
                    existing_by_id[upsert.id] = replace(
                        upsert, seq=upsert.seq if upsert.seq is not None else prior_seq
                    )
            merged = [existing_by_id[tcid] for tcid in order]
            next_tool_calls_json = _encode_tool_calls(merged)

        next_token_usage_json: str | None | object = _UNSET
        if token_usage is not None:
            next_token_usage_json = _encode_token_usage(token_usage)

        sets: list[str] = []
        values: list[object] = []
        if next_content is not None:
            sets.append("content = ?")
            values.append(next_content)
        if next_tool_calls_json is not _UNSET:
            sets.append("tool_calls_json = ?")
            values.append(next_tool_calls_json)
        if next_token_usage_json is not _UNSET:
            sets.append("token_usage_json = ?")
            values.append(next_token_usage_json)
        # feat-414: Sentinel 同 token_usage — None 表示"不改"，有值则写入。
        if elapsed_ms is not None:
            sets.append("elapsed_ms = ?")
            values.append(elapsed_ms)
        if delivery_status is not None:
            sets.append("delivery_status = ?")
            values.append(delivery_status)
        # feat-445-M1: relay 收尾把该气泡的 kernel message_id 落库。None（默认）= 不改，
        # 不清掉已写入值（同 token_usage/elapsed_ms 的 sentinel 语义）。
        if kernel_message_id is not None:
            sets.append("kernel_message_id = ?")
            values.append(kernel_message_id)
        if not sets:
            raise ValueError(
                "update_runtime_state requires at least one field to change"
            )
        values.append(message_id)
        with self._connection:
            self._connection.execute(
                f"UPDATE messages SET {', '.join(sets)} WHERE id = ?",
                tuple(values),
            )
        refreshed = self._connection.execute(
            """
            SELECT
                messages.id,
                messages.conversation_id,
                messages.sender_user_id,
                messages.sender_type,
                messages.content,
                messages.attachments_json,
                messages.delivery_status,
                messages.created_at,
                messages.tool_calls_json,
                messages.thinking_json,
                messages.token_usage_json,
                messages.elapsed_ms,
                messages.permission_request_json,
                messages.kernel_message_id,
                users.username AS sender_username,
                COALESCE(messages.sender_display_name, users.display_name) AS sender_display_name
            FROM messages
            LEFT JOIN users ON users.id = messages.sender_user_id
            WHERE messages.id = ?
            """,
            (message_id,),
        ).fetchone()
        return self._message_from_row(refreshed)

    def append_thinking_segment(self, *, message_id: str, text: str) -> Message:
        """feat-439-M2: 追加一段思考到 ``messages.thinking_json``，返回刷新后的消息。

        ``seq`` 在此（持久化边界）统一赋予：思考与工具**共享一个 per-message 单调递增
        计数器**（= 当前所有过程项 seq 的 max + 1），按真实到达序赋值且全局唯一。这样
        渲染端按 seq 把思考与工具 merge 成一条时间线，且唯一 seq 让 live WS 事件可幂等
        去重（重放/双投递不重复）。live 与历史回放都读同一持久化值，口径一致。
        """
        # code-review fix: 计 seq 的 SELECT 与写入的 UPDATE 必须在同一事务内（对齐
        # update_runtime_state 写法），避免并发/崩溃下读到旧 seq 后半写导致序号错乱。
        with self._connection:
            row = self._connection.execute(
                "SELECT tool_calls_json, thinking_json FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"message_id not found: {message_id}")
            existing_tools = _decode_tool_calls(row["tool_calls_json"]) or []
            existing = _decode_thinking(row["thinking_json"]) or []
            seq = _next_process_seq(existing, existing_tools)
            existing.append(ThinkingSegment(seq=seq, text=text))
            self._connection.execute(
                "UPDATE messages SET thinking_json = ? WHERE id = ?",
                (_encode_thinking(existing), message_id),
            )
        refreshed = self._connection.execute(
            """
            SELECT
                messages.id,
                messages.conversation_id,
                messages.sender_user_id,
                messages.sender_type,
                messages.content,
                messages.attachments_json,
                messages.delivery_status,
                messages.created_at,
                messages.tool_calls_json,
                messages.thinking_json,
                messages.token_usage_json,
                messages.elapsed_ms,
                messages.permission_request_json,
                messages.kernel_message_id,
                users.username AS sender_username,
                COALESCE(messages.sender_display_name, users.display_name) AS sender_display_name
            FROM messages
            LEFT JOIN users ON users.id = messages.sender_user_id
            WHERE messages.id = ?
            """,
            (message_id,),
        ).fetchone()
        return self._message_from_row(refreshed)

    def get_conversation_id(self, *, message_id: str) -> str | None:
        """Return a message's conversation_id without mutating the row (bugfix-417-M3).

        Used by the run_heartbeat liveness path, which must append a conversation_events
        row but must NOT patch the message (content / tool_calls / delivery_status).
        Returns ``None`` for an unknown message id.
        """
        row = self._connection.execute(
            "SELECT conversation_id FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row["conversation_id"])

    def list_all_messages(self, *, conversation_id: str) -> list[Message]:
        """Return the FULL message timeline (oldest→newest), no pagination cap.

        feat-445-M2 #3: ``list_messages`` is the UI pagination read — it clamps to
        ``min(limit, 200)`` and returns only the last page (``[-200:]``). fork must copy
        the *entire* start→fork-point history and locate the fork point anywhere in it,
        so it reads here instead. Same timeline source as ``list_messages``, just without
        the page window.
        """
        return self._list_message_timeline(conversation_id=conversation_id)

    def list_messages(
        self,
        *,
        conversation_id: str,
        limit: int = 50,
        before_message_id: str | None = None,
        mark_as_read: bool = False,
    ) -> list[Message]:
        """List messages for a conversation in insertion order.

        Args:
            conversation_id: Target conversation identifier.
            limit: Maximum number of recent messages to return.
            before_message_id: Exclusive cursor; return messages older than this message.
            mark_as_read: Whether to clear unread_count for the conversation after loading latest page.

        Returns:
            Messages ordered from oldest to newest within the selected page.
        """
        bounded_limit = max(1, min(limit, 200))
        merged_messages = self._list_message_timeline(conversation_id=conversation_id)
        if before_message_id is not None:
            cursor_index = next(
                (
                    index
                    for index, message in enumerate(merged_messages)
                    if message.id == before_message_id
                ),
                None,
            )
            if cursor_index is None:
                raise ValueError("before_message_id not found")
            merged_messages = merged_messages[:cursor_index]
        paged_messages = merged_messages[-bounded_limit:]
        if mark_as_read and before_message_id is None:
            with self._connection:
                self._connection.execute(
                    "UPDATE conversations SET unread_count = 0 WHERE id = ?",
                    (conversation_id,),
                )
        return paged_messages

    def _list_message_timeline(self, *, conversation_id: str) -> list[Message]:
        """Return persisted messages merged with visible relay-history messages."""
        message_rows = self._connection.execute(
            """
            SELECT
                messages.id,
                messages.conversation_id,
                messages.sender_user_id,
                messages.sender_type,
                messages.content,
                messages.attachments_json,
                messages.delivery_status,
                messages.created_at,
                messages.tool_calls_json,
                messages.thinking_json,
                messages.token_usage_json,
                messages.elapsed_ms,
                messages.permission_request_json,
                messages.kernel_message_id,
                users.username AS sender_username,
                COALESCE(messages.sender_display_name, users.display_name) AS sender_display_name
            FROM messages
            LEFT JOIN users ON users.id = messages.sender_user_id
            WHERE conversation_id = ?
            ORDER BY messages.rowid
            """,
            (conversation_id,),
        ).fetchall()
        merged = [self._message_from_row(row) for row in message_rows]
        # M17/R8-1: once a turn produces a real agent message (M16 streaming chain),
        # the relay.completed mirror becomes a duplicate. Suppress synthetic rows
        # whenever the conversation already has any real agent-typed message —
        # keeps legacy threads that only have relay events intact (no real agent
        # row → still synthesise from events).
        has_real_agent_message = any(m.sender_type == "agent" for m in merged)
        event_rows = self._connection.execute(
            """
            SELECT event_id, conversation_id, message_id, event_type, delivery_status, payload_json, created_at
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()
        for row in event_rows:
            synthetic_message = self._message_from_visible_event_row(row)
            if synthetic_message is None:
                continue
            if has_real_agent_message and ":relay:" in synthetic_message.id:
                continue
            merged = _upsert_message(merged, synthetic_message)
        return merged

    def append_permission_request(
        self,
        *,
        message_id: str,
        permission_data: dict[str, object],
    ) -> str:
        """Append one permission_request dict to the message's list, dedup by request_id.

        bugfix-367: 同一 message 上多次 ask 不再相互覆盖。同 request_id 的二次写入
        视为 idempotent 替换(网络重传等);新 request_id 追加到 list 尾,以便 UI
        按时间顺序渲染历史小条 + 当前 pending 卡。

        Args:
            message_id: Target message; must exist.
            permission_data: Full permission request dict to append/replace. Caller
                supplies ``status="pending"`` (and ``request_id``).

        Returns:
            The conversation_id of the target message (needed by the bridge).

        Raises:
            ValueError: When ``message_id`` does not exist or ``permission_data``
                lacks ``request_id``.
        """
        request_id = permission_data.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("permission_data must include a non-empty request_id")

        row = self._connection.execute(
            "SELECT conversation_id, permission_request_json FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"message_id not found: {message_id}")
        existing = _load_permission_requests(row["permission_request_json"])
        replaced = False
        for index, entry in enumerate(existing):
            if entry.get("request_id") == request_id:
                existing[index] = dict(permission_data)
                replaced = True
                break
        if not replaced:
            existing.append(dict(permission_data))
        # bugfix-410-M2 (#98): stamp the awaiting_permission liveness marker so the
        # relay watchdog exempts this running message from the 120s idle reap while
        # the user decides. The Gateway heartbeat refreshes it; resolution clears it.
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET permission_request_json = ?, awaiting_permission_at = ? WHERE id = ?",
                (json.dumps(existing), utc_now(), message_id),
            )
        return str(row["conversation_id"])

    def update_permission_resolution(
        self,
        *,
        message_id: str,
        request_id: str,
        decision: str,
    ) -> str:
        """Mark one specific permission_request entry as resolved within the list.

        bugfix-367: list 化后 resolved 写入必须按 request_id 定位 —— 不再覆盖整列
        (那会丢掉同泡内其他历史 ask)。未匹配到 request_id 时 raise,防止前端
        reducer 状态机被静默放空。

        Args:
            message_id: Target message; must exist.
            request_id: Stable identifier matching a pending request.
            decision: User-chosen option id (e.g. ``"allow_once"``, ``"deny"``).

        Returns:
            The conversation_id of the target message.

        Raises:
            ValueError: When ``message_id`` does not exist or ``request_id`` is not
                found in the message's permission_requests list.
        """
        row = self._connection.execute(
            "SELECT conversation_id, permission_request_json FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"message_id not found: {message_id}")
        existing = _load_permission_requests(row["permission_request_json"])
        target_index: int | None = None
        for index, entry in enumerate(existing):
            if entry.get("request_id") == request_id:
                target_index = index
                break
        if target_index is None:
            raise ValueError(
                f"request_id {request_id!r} not found in permission_requests of message {message_id}"
            )
        existing[target_index] = {
            **existing[target_index],
            "status": "resolved",
            "decision": decision,
        }
        # bugfix-410-M2 (#98): clear the awaiting_permission marker only when no other
        # ask on this message is still pending (a message can carry several asks).
        # While any remains pending the marker stays set (and heartbeat-refreshed).
        any_still_pending = any(entry.get("status") == "pending" for entry in existing)
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET permission_request_json = ?, "
                "awaiting_permission_at = CASE WHEN ? THEN awaiting_permission_at ELSE NULL END "
                "WHERE id = ?",
                (json.dumps(existing), 1 if any_still_pending else 0, message_id),
            )
        return str(row["conversation_id"])

    def clear_awaiting_permission_marker(self, *, message_id: str) -> None:
        """Drop the awaiting_permission marker (bugfix-410-M2 #98).

        Called when a run reaches a terminal state (failed/cancelled/completed)
        so a marker left set by a never-resolved ask cannot keep exempting the
        message after the run is already over.
        """
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET awaiting_permission_at = NULL WHERE id = ?",
                (message_id,),
            )

    def refresh_awaiting_permission_markers(self, *, agent_ids: list[str]) -> int:
        """Touch awaiting_permission_at for the given agents' still-running, still-
        marked messages (bugfix-410-M2 #98).

        Invoked from the owning node's heartbeat handler: while the Gateway is
        alive it keeps refreshing the marker timestamp, so the relay watchdog's
        crash-threshold check treats the wait as live and never reaps it. A
        Gateway crash stops the heartbeat → the marker goes stale → the message
        is reaped normally. Only refreshes rows already marked (never sets a new
        marker), so it cannot resurrect a resolved/terminal message.

        Agents are stored as users with ``username = 'agent:<agent_id>'``; we
        resolve via that join so callers pass the same agent_ids the heartbeat
        node owns.

        Returns:
            Number of marker timestamps refreshed.
        """
        if not agent_ids:
            return 0
        usernames = [f"agent:{agent_id}" for agent_id in agent_ids]
        placeholders = ",".join("?" for _ in usernames)
        with self._connection:
            cursor = self._connection.execute(
                f"UPDATE messages SET awaiting_permission_at = ? "
                f"WHERE delivery_status = 'running' "
                f"AND awaiting_permission_at IS NOT NULL "
                f"AND sender_user_id IN ("
                f"  SELECT id FROM users WHERE username IN ({placeholders})"
                f")",
                (utc_now(), *usernames),
            )
        return cursor.rowcount if cursor.rowcount is not None else 0

    def _message_from_row(self, row: sqlite3.Row) -> Message:
        """Convert one stored SQLite row into a Message domain model."""
        tool_calls_value = (
            row["tool_calls_json"] if "tool_calls_json" in row.keys() else None
        )
        thinking_value = row["thinking_json"] if "thinking_json" in row.keys() else None
        token_usage_value = (
            row["token_usage_json"] if "token_usage_json" in row.keys() else None
        )
        permission_request_value = (
            row["permission_request_json"]
            if "permission_request_json" in row.keys()
            else None
        )
        # feat-414: 旧行无此列时（key 不在 row.keys()）回落 None，不报 KeyError。
        elapsed_ms_value: int | None = (
            row["elapsed_ms"] if "elapsed_ms" in row.keys() else None
        )
        # feat-445-M1: 旧行 / 非来自含该列 SELECT 的 row 回落 None，不报 KeyError。
        kernel_message_id_value: str | None = (
            row["kernel_message_id"] if "kernel_message_id" in row.keys() else None
        )
        permission_requests = _load_permission_requests(permission_request_value)
        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            sender_user_id=row["sender_user_id"],
            sender_type=row["sender_type"],
            sender=self._actor_from_sender_row(
                sender_type=str(row["sender_type"]),
                sender_user_id=str(row["sender_user_id"]),
                sender_username=str(row["sender_username"])
                if row["sender_username"] is not None
                else None,
                sender_display_name=(
                    str(row["sender_display_name"])
                    if row["sender_display_name"] is not None
                    else None
                ),
            ),
            content=row["content"],
            attachments=_decode_attachments(row["attachments_json"]),
            delivery_status=row["delivery_status"],
            created_at=row["created_at"],
            tool_calls=_decode_tool_calls(tool_calls_value),
            thinking=_decode_thinking(thinking_value),
            token_usage=_decode_token_usage(token_usage_value),
            elapsed_ms=elapsed_ms_value,
            permission_requests=permission_requests,
            kernel_message_id=kernel_message_id_value,
        )

    def _message_from_visible_event_row(self, row: sqlite3.Row) -> Message | None:
        """Convert one relay-visible event row into the synthetic message shown in history."""
        event_type = str(row["event_type"])
        if event_type not in {"relay.completed", "relay.failed"}:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        # bugfix-365: when the real `messages` row for this event is already an
        # agent row in a terminal state (failed/completed), the synthetic mirror
        # would just paint a second bubble for the same logical message — the
        # watchdog path is the canonical case (writes `relay.failed` after flipping
        # the real row to `failed`). Suppress the synthetic; the real row carries
        # the detail text via the watchdog's content backfill in `relay_watchdog`.
        # Scoping to `sender_type='agent'` preserves the legacy pattern where one
        # *user* message_id fans out into multiple synthetic agent reply rows.
        real_message_id = _optional_text(payload.get("message_id"))
        if real_message_id is not None:
            real_row = self._connection.execute(
                "SELECT delivery_status, sender_type FROM messages WHERE id = ?",
                (real_message_id,),
            ).fetchone()
            if (
                real_row is not None
                and str(real_row["sender_type"]) == "agent"
                and str(real_row["delivery_status"]) in {"failed", "completed"}
            ):
                return None
        synthetic_message_id = _synthetic_message_id_from_event_payload(payload)
        if synthetic_message_id is None:
            return None
        content = _visible_content_from_event(event_type=event_type, payload=payload)
        if content is None:
            return None
        sender = self._actor_from_event_payload(payload)
        sender_user_id = sender.user_id or sender.id
        delivery_status = (
            "running"
            if event_type == "relay.processing"
            else "failed"
            if event_type == "relay.failed"
            else "completed"
        )
        return Message(
            id=synthetic_message_id,
            conversation_id=str(row["conversation_id"]),
            sender_user_id=sender_user_id,
            sender_type="agent",
            sender=sender,
            content=content,
            attachments=[],
            delivery_status=delivery_status,
            created_at=str(row["created_at"]),
        )

    def _actor_from_event_payload(self, payload: dict[str, object]) -> Actor:
        """Build the agent actor identity exposed for synthetic relay history rows."""
        agent_id = _optional_text(payload.get("agent_id"))
        sender_display_name = (
            _optional_text(payload.get("sender_display_name"))
            or _optional_text(payload.get("display_name"))
            or _optional_text(payload.get("agent_display_name"))
        )
        if agent_id is not None:
            sender_row = self._connection.execute(
                "SELECT id, display_name FROM users WHERE username = ?",
                (f"agent:{agent_id}",),
            ).fetchone()
            return Actor(
                type="agent",
                id=agent_id,
                display_name=sender_display_name
                or (
                    str(sender_row["display_name"]) if sender_row is not None else None
                ),
                user_id=str(sender_row["id"])
                if sender_row is not None
                else f"agent:{agent_id}",
            )
        fallback_display_name = sender_display_name or "Agent"
        return Actor(
            type="agent",
            id=fallback_display_name,
            display_name=sender_display_name,
            user_id=f"agent:{fallback_display_name}",
        )

    def _resolve_sender_user_row(
        self, *, sender_user_id: str, sender_type: str
    ) -> sqlite3.Row | None:
        """Resolve sender identity by stable actor id to concrete IM user row."""
        normalized_sender = sender_user_id.strip()
        if not normalized_sender:
            return None
        if normalized_sender.startswith("user:"):
            normalized_sender = normalized_sender[len("user:") :].strip()
            if not normalized_sender:
                return None
        if sender_type == "agent" and normalized_sender.startswith("agent:"):
            normalized_sender = normalized_sender[len("agent:") :].strip()
            if not normalized_sender:
                return None

        by_id = self._connection.execute(
            "SELECT id, username, display_name, owner_id FROM users WHERE id = ?",
            (normalized_sender,),
        ).fetchone()
        if by_id is not None:
            return by_id
        if sender_type == "agent":
            return self._connection.execute(
                "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
                (f"agent:{normalized_sender}",),
            ).fetchone()
        return self._connection.execute(
            "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
            (normalized_sender,),
        ).fetchone()

    @staticmethod
    def _actor_from_sender_row(
        *,
        sender_type: str,
        sender_user_id: str,
        sender_username: str | None,
        sender_display_name: str | None,
    ) -> Actor:
        """Build actor-first sender identity from message row and user metadata."""
        if (
            sender_type == "agent"
            and sender_username is not None
            and sender_username.startswith("agent:")
        ):
            actor_id = sender_username[len("agent:") :].strip() or sender_user_id
            return Actor(
                type="agent",
                id=actor_id,
                display_name=sender_display_name,
                user_id=sender_user_id,
            )
        return Actor(
            type=sender_type,
            id=sender_user_id,
            display_name=sender_display_name,
            user_id=sender_user_id,
        )

    def _insert_event(
        self,
        *,
        conversation_id: str,
        message_id: str | None,
        event_type: str,
        delivery_status: str,
        payload: dict[str, object],
    ) -> ConversationEvent:
        """Insert an event row inside this message transaction."""
        return insert_event_row(
            self._connection,
            conversation_id=conversation_id,
            message_id=message_id,
            event_type=event_type,
            delivery_status=delivery_status,
            payload=payload,
            created_at=utc_now(),
        )


def _normalize_attachments(attachments: list[Attachment] | None) -> list[Attachment]:
    """Validate and normalize attachment payloads before persistence."""
    normalized = attachments or []
    results: list[Attachment] = []
    for item in normalized:
        url = item.url.strip()
        if not url:
            raise ValueError("attachments[].url must be non-empty")
        content_type = item.content_type.strip() if item.content_type else None
        file_name = item.file_name.strip() if item.file_name else None
        results.append(
            Attachment(
                url=url,
                content_type=content_type or None,
                file_name=file_name or None,
            )
        )
    return results


_UNSET: object = object()


def _normalize_tool_calls(tool_calls: list[ToolCall] | None) -> list[ToolCall] | None:
    """Return tool_calls list passthrough, validating non-None entries by construction."""
    if tool_calls is None:
        return None
    return list(tool_calls)


def _scoped_caller_idempotency_key(
    conversation_id: str, caller_idempotency_key: str
) -> str:
    """Return an opaque retry key that is unique only within one conversation."""
    digest = hashlib.sha256()
    digest.update(conversation_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(caller_idempotency_key.encode("utf-8"))
    return digest.hexdigest()
