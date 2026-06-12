"""Kernel RuntimeEvent → IM ConversationEvent translation layer (feat-340-M2 design §5).

The bridge owns three responsibilities for a single agent run:

1. Persist the agent's reply onto the conversation timeline (so refresh / sync recovers
   the same view as live streaming).
2. Maintain the per-message tool_calls / token_usage JSON columns so the chat panel can
   render Tool Calls / Token Chip without replaying every event.
3. Emit the WS event_types schema events (message.created / .delta / .completed /
   tool_call.upserted / .completed) by appending to ``conversation_events`` and
   triggering the registered notify callback.

Kept inside ``IM.application`` (not the Gateway or kernel) because the WS event schema
is an IM concept; kernel stays product-agnostic and Gateway stays a thin relay. Decision
5 of design.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from IM.api.ws.event_types import (
    EVENT_MESSAGE_COMPLETED,
    EVENT_MESSAGE_CREATED,
    EVENT_MESSAGE_DELTA,
    EVENT_PERMISSION_REQUEST,
    EVENT_PERMISSION_RESOLVED,
    EVENT_TOOL_CALL_COMPLETED,
    EVENT_TOOL_CALL_UPSERTED,
    build_message_completed_payload,
    build_message_created_payload,
    build_message_delta_payload,
    build_tool_call_completed_payload,
    build_tool_call_upserted_payload,
)
from IM.domain.models import ConversationEvent, Message, TokenUsage, ToolCall
from IM.infra.repositories import EventRepository, MessageRepository


NotifyCallable = Callable[[ConversationEvent], None]


@dataclass(slots=True)
class EventBridge:
    """Translate kernel run events into persisted IM state and live WS events.

    Args:
        message_repository: Used to insert the placeholder agent message and patch its
            runtime state (content / tool_calls / token_usage / delivery_status).
        event_repository: Used to append conversation_events rows.
        notify: Optional sync callback fired *after* event persistence; the wiring in
            ``IM.ws.user_stream.build_notify_enqueue`` forwards to the user-stream
            registry. When ``None``, events are only persisted (e.g. unit tests).
    """

    message_repository: MessageRepository
    event_repository: EventRepository
    notify: NotifyCallable | None = None

    def emit_instant_message(
        self,
        *,
        conversation_id: str,
        agent_user_id: str,
        agent_id: str,
        content: str,
    ) -> Message:
        """Persist a one-shot completed agent message and emit message.created + message.completed.

        Designed for background-task notifications (e.g. bugfix-404 agent.message frames
        to a human user): the full text is known upfront, so there is no streaming phase.
        Unlike ``on_turn_start``, the ``message.created`` event is emitted with final content
        and ``delivery_status="completed"`` immediately — no visible empty-bubble window.

        Args:
            conversation_id: Conversation that receives the notification.
            agent_user_id: IM user-row id for the sending agent.
            agent_id: Stable agent identifier (currently forwarded in the WS payload).
            content: Final message text; must be non-empty.

        Returns:
            The persisted message entity with ``delivery_status="completed"``.
        """
        del agent_id  # forwarded in WS payloads; unused internally.
        message = self.message_repository.create_message(
            conversation_id=conversation_id,
            sender_user_id=agent_user_id,
            content=content,
            sender_type="agent",
            # Disable the auto-complete path: we control delivery_status explicitly below
            # so the two event emissions (created + completed) are the sole source of truth.
            auto_complete_delivery=False,
        )
        # Settle delivery_status to completed before emitting so any reader that fetches
        # the message row after the event lands sees the terminal state.
        message = self.message_repository.update_runtime_state(
            message_id=message.id,
            delivery_status="completed",
        )
        # message.created carries final content + completed status: no spinner / empty-bubble.
        self._emit(
            conversation_id=conversation_id,
            message_id=message.id,
            event_type=EVENT_MESSAGE_CREATED,
            delivery_status="completed",
            payload=build_message_created_payload(message=message),
        )
        # message.completed lets the frontend reducer settle token_usage and final content
        # through the same patch path used by streaming turns.
        self._emit(
            conversation_id=conversation_id,
            message_id=message.id,
            event_type=EVENT_MESSAGE_COMPLETED,
            delivery_status="completed",
            payload=build_message_completed_payload(
                conversation_id=conversation_id,
                message_id=message.id,
                content=message.content or "",
                token_usage=None,
            ),
        )
        return message

    def on_turn_start(
        self,
        *,
        conversation_id: str,
        agent_user_id: str,
        agent_id: str,
    ) -> Message:
        """Create the agent's empty placeholder message and emit ``message.created``.

        Args:
            conversation_id: Conversation that owns this run.
            agent_user_id: User row id representing the agent inside IM (typically the
                row with username ``agent:<agent_id>``).
            agent_id: Stable agent identifier; available for callers that wish to log
                or correlate, currently unused inside the bridge.

        Returns:
            The created placeholder message.
        """
        del agent_id  # currently unused; reserved for richer payloads later.
        created = self.message_repository.create_message(
            conversation_id=conversation_id,
            sender_user_id=agent_user_id,
            content="",
            sender_type="agent",
            auto_complete_delivery=False,
            allow_empty=True,
        )
        # Surface the agent message as "running" so /sync replays mark unfinished turns,
        # and live UIs render the pulse / spinner immediately.
        message = self.message_repository.update_runtime_state(
            message_id=created.id,
            delivery_status="running",
        )
        self._emit(
            conversation_id=conversation_id,
            message_id=message.id,
            event_type=EVENT_MESSAGE_CREATED,
            delivery_status="running",
            payload=build_message_created_payload(message=message),
        )
        return message

    def on_message_delta(self, *, message_id: str, delta_text: str) -> None:
        """Append an incremental text token to the agent message and emit a delta event."""
        if not delta_text:
            # Drop empty deltas before any DB write — they would still emit a no-op event
            # which the frontend has to filter; safer to ignore at the source.
            return
        updated = self.message_repository.update_runtime_state(
            message_id=message_id,
            content_append=delta_text,
        )
        self._emit(
            conversation_id=updated.conversation_id,
            message_id=message_id,
            event_type=EVENT_MESSAGE_DELTA,
            delivery_status="running",
            payload=build_message_delta_payload(
                conversation_id=updated.conversation_id,
                message_id=message_id,
                delta_text=delta_text,
            ),
        )

    def on_tool_call_upserted(self, *, message_id: str, tool_call: ToolCall) -> None:
        """Upsert one tool call row and emit ``tool_call.upserted``."""
        updated = self.message_repository.update_runtime_state(
            message_id=message_id,
            tool_calls_upsert=[tool_call],
        )
        self._emit(
            conversation_id=updated.conversation_id,
            message_id=message_id,
            event_type=EVENT_TOOL_CALL_UPSERTED,
            delivery_status="running",
            payload=build_tool_call_upserted_payload(
                conversation_id=updated.conversation_id,
                message_id=message_id,
                tool_call=tool_call,
            ),
        )

    def on_tool_call_completed(self, *, message_id: str, tool_call: ToolCall) -> None:
        """Mark one tool call completed (or failed) and emit ``tool_call.completed``."""
        updated = self.message_repository.update_runtime_state(
            message_id=message_id,
            tool_calls_upsert=[tool_call],
        )
        self._emit(
            conversation_id=updated.conversation_id,
            message_id=message_id,
            event_type=EVENT_TOOL_CALL_COMPLETED,
            delivery_status="running",
            payload=build_tool_call_completed_payload(
                conversation_id=updated.conversation_id,
                message_id=message_id,
                tool_call=tool_call,
            ),
        )

    def on_message_completed(
        self,
        *,
        message_id: str,
        final_content: str | None = None,
        token_usage: TokenUsage | None = None,
        delivery_status: str = "completed",
    ) -> None:
        """Close the agent message with terminal content + optional token usage."""
        updated = self.message_repository.update_runtime_state(
            message_id=message_id,
            content_replace=final_content,
            token_usage=token_usage,
            delivery_status=delivery_status,
        )
        self._emit(
            conversation_id=updated.conversation_id,
            message_id=message_id,
            event_type=EVENT_MESSAGE_COMPLETED,
            delivery_status=delivery_status,
            payload=build_message_completed_payload(
                conversation_id=updated.conversation_id,
                message_id=message_id,
                content=updated.content,
                token_usage=token_usage,
            ),
        )

    def on_permission_request(
        self,
        *,
        message_id: str,
        permission_request: dict[str, object],
    ) -> None:
        """Persist a pending permission request and emit ``permission.request``.

        Embeds ``status="pending"`` before writing so the frontend can distinguish
        pending vs. resolved without an extra query.

        Args:
            message_id: Agent message that owns this request.
            permission_request: Raw permission payload from the gateway (must contain
                at minimum ``request_id`` and ``tool_name``).

        Raises:
            ValueError: When ``message_id`` does not exist.
        """
        # bugfix-367: append 而不是覆盖 —— 同一 message 上多次 ask 全部按时间顺序保留。
        # 同 request_id 重复写入 idempotent(repository 内 dedup 替换)。
        data = {**permission_request, "status": "pending"}
        conversation_id = self.message_repository.append_permission_request(
            message_id=message_id,
            permission_data=data,
        )
        self._emit(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type=EVENT_PERMISSION_REQUEST,
            delivery_status="running",
            payload={
                "conversation_id": conversation_id,
                "message_id": message_id,
                "event_type": EVENT_PERMISSION_REQUEST,
                "permission_request": data,
            },
        )

    def on_permission_resolved(
        self,
        *,
        message_id: str,
        request_id: str,
        decision: str,
    ) -> None:
        """Mark a permission request resolved and emit ``permission.resolved``.

        Reads the existing ``permission_request_json`` from the message and updates its
        ``status`` and ``decision`` fields so the frontend can show the settled state
        without re-fetching the full conversation.

        Args:
            message_id: Agent message that owns the request.
            request_id: Stable identifier matching the pending request.
            decision: User-chosen option id (e.g. ``"allow_once"``, ``"deny"``).

        Raises:
            ValueError: When ``message_id`` does not exist.
        """
        # bugfix-367: 按 request_id 在 list 中定位、就地改 status/decision,
        # 不再覆盖整条 permission_request_json(那会丢同泡其他历史 ask)。
        conversation_id = self.message_repository.update_permission_resolution(
            message_id=message_id,
            request_id=request_id,
            decision=decision,
        )
        self._emit(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type=EVENT_PERMISSION_RESOLVED,
            delivery_status="running",
            payload={
                "conversation_id": conversation_id,
                "message_id": message_id,
                "event_type": EVENT_PERMISSION_RESOLVED,
                "request_id": request_id,
                "decision": decision,
            },
        )

    def _emit(
        self,
        *,
        conversation_id: str,
        message_id: str,
        event_type: str,
        delivery_status: str,
        payload: dict[str, object],
    ) -> None:
        event = self.event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type=event_type,
            delivery_status=delivery_status,
            payload=payload,
        )
        if self.notify is not None:
            self.notify(event)
