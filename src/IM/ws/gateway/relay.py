from __future__ import annotations

import asyncio
import logging


from IM.application.relay_service import RelayService
from IM.domain.models import Actor, Message, SystemNotice
from IM.infra.gateway_persistence import (
    AgentDispatchRecord,
    DispatchTarget,
    GatewayConversationPersistence,
)
from IM.infra.repositories.events import EventRepository
from IM.infra.repositories.messages import MessageRepository
from .protocol import (
    _not_registered_error,
    _require_text,
    parse_delivery_receipt_event,
)

_logger = logging.getLogger(__name__)

from .execution import GatewayExecution
from .sessions import GatewaySessions


class GatewayRelay:
    """Own relay delivery, receipts, peer fanout, and Gateway-originated messages."""

    def __init__(
        self,
        *,
        sessions: GatewaySessions,
        execution: GatewayExecution,
        relay_service: RelayService,
        conversation_persistence: GatewayConversationPersistence | None = None,
        message_repository: MessageRepository | None = None,
        event_repository: EventRepository | None = None,
        lock: asyncio.Lock,
    ) -> None:
        self._sessions = sessions
        self._execution = execution
        self._relay_service = relay_service
        self._conversation_persistence = conversation_persistence
        self._message_repository = message_repository
        self._event_repository = event_repository
        self._lock = lock
        self._agent_message_lock = asyncio.Lock()

    async def push_relay_message(
        self, *, relay_task_id: str, target_node_id: str, payload: dict[str, object]
    ) -> bool:
        """Push a relay frame, then durably mark it dispatched after send succeeds."""
        sent = await self._sessions.send(
            target_node_id=target_node_id,
            message_type="relay.message",
            payload={**payload, "relay_task_id": relay_task_id},
        )
        if not sent:
            return False
        self._relay_service.mark_dispatched(relay_task_id=relay_task_id)
        return True

    async def handle_delivery_receipt(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        event = parse_delivery_receipt_event(payload)
        node_id = event.node_id
        relay_task_id = event.relay_task_id
        delivery_status = event.delivery_status
        detail = event.detail
        if not await self._sessions.is_connected(node_id=node_id):
            return _not_registered_error(node_id=node_id)
        task = self._relay_service.apply_delivery_receipt(
            relay_task_id=relay_task_id,
            delivery_status=delivery_status,
            detail=detail,
        )
        self._persist_receipt_events(task=task, node_id=node_id, detail=detail)
        if delivery_status == "completed":
            await self._broadcast_group_reply_context(
                task=task, node_id=node_id, detail=detail
            )
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.delivery_receipt",
                "node_id": node_id,
                "relay_task_id": relay_task_id,
                "status": task.status,
            },
        }

    async def _broadcast_group_reply_context(
        self, *, task, node_id: str, detail: str | None
    ) -> None:  # noqa: ANN001
        if self._conversation_persistence is None:
            return
        if (
            detail is None
            or not detail.strip()
            or detail.strip() == "NO_REPLY"
            or "suppressed_by=no_reply_token" in detail
        ):
            return
        relay_metadata = task.payload.get("metadata", {})
        if (
            not isinstance(relay_metadata, dict)
            or relay_metadata.get("conversation_type") != "group"
        ):
            return
        source_agent_id = task.payload.get("agent_id")
        if not isinstance(source_agent_id, str) or not source_agent_id.strip():
            return
        route = self._conversation_persistence.group_reply_route(
            conversation_id=task.conversation_id,
            source_agent_id=source_agent_id,
        )
        if route is None:
            return

        # bugfix-358: IM 在此处只做哑路由——给每个 peer agent 各扇出一份 group relay。
        # 是否触发回复(MENTION gate)的判断完全交给 Gateway:Gateway 看 enqueue_message_relay
        # 内部从 content 里 <mention type="agent" target_id="X"/> 标签解出的 mentioned_agent_ids,
        # 自己 in 列表 → 触发;否则 buffer 进 group_context_store 当背景上下文(inbound_pipeline §3.1)。
        # content 不在 IM 端预加 sender 前缀:Gateway pipeline 会按 _format_sender_text(sender_label, text)
        # 自己拼 [sender] 前缀;IM 再加一遍会 double-prefix。
        synthetic_message = Message(
            id=task.message_id,
            conversation_id=task.conversation_id,
            sender_user_id=route.sender_user_id,
            sender_type="agent",
            sender=Actor(
                type="agent",
                id=source_agent_id,
                display_name=route.sender_display_name,
                user_id=route.sender_user_id,
            ),
            content=detail.strip(),
            attachments=[],
            delivery_status="completed",
            created_at=task.updated_at,
        )
        for target in route.targets:
            target_node_id = self._conversation_persistence.agent_node_id(
                agent_id=target.agent_id
            )
            if target_node_id is None:
                continue
            result = self._relay_service.enqueue_message_relay(
                message=synthetic_message,
                target_node_id=target_node_id,
                idempotency_key=f"agent-reply:{task.relay_task_id}:{target.agent_id}",
                sender_user_id=route.sender_user_id,
                conversation_type="group",
                extra_metadata={
                    "source_agent_id": source_agent_id,
                    "sender_display_name": route.sender_display_name,
                },
                _override_agent_id=target.agent_id,
            )
            if result.created:
                await self.push_relay_message(
                    relay_task_id=result.relay_task.relay_task_id,
                    target_node_id=target_node_id,
                    payload=result.relay_task.payload,
                )

    async def handle_agent_message(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist one gateway-dispatched send_message payload into IM conversations.

        For user-target messages (background agent notifications), this method uses
        EventBridge (on_turn_start + on_message_completed) rather than calling
        create_message directly.  That ensures a message.created event is written to
        conversation_events so the front-end user-stream picks it up in real time and
        renders the bubble without a manual refresh.

        For agent-target messages (agent-to-agent relay), the prior direct
        create_message path is preserved — those messages are forwarded via relay and
        the target agent does not need a live WS bubble.
        """
        if self._conversation_persistence is None or self._message_repository is None:
            return {
                "type": "error",
                "payload": {
                    "code": "gateway_not_configured",
                    "message": "conversation_repository and user_repository must be configured",
                },
            }

        try:
            text = _require_text(payload.get("text"), field_name="text").strip()
            target = _require_text(payload.get("to"), field_name="to").strip()
            source_raw = _require_text(
                payload.get("from_session_id"), field_name="from_session_id"
            ).strip()
            source_agent_id, dispatch_request_id = (
                self._resolve_dispatch_source_from_session_id(source_raw=source_raw)
            )
            resolution = self._conversation_persistence.resolve_send_target(
                source_agent_id=source_agent_id,
                target=target,
                caller_owner_id=None,
            )
            resolved_target = resolution.target
            conversation_id = resolution.conversation_id
            dispatch_request_key = (
                f"{source_agent_id}:{dispatch_request_id}"
                if dispatch_request_id is not None
                else None
            )
            existing = (
                self._conversation_persistence.find_dispatch(
                    dispatch_request_key=dispatch_request_key
                )
                if dispatch_request_key is not None
                else None
            )
            if existing is None:
                async with self._agent_message_lock:
                    existing = (
                        self._conversation_persistence.find_dispatch(
                            dispatch_request_key=dispatch_request_key
                        )
                        if dispatch_request_key is not None
                        else None
                    )
                    if existing is None:
                        sender_user_id = self._conversation_persistence.agent_user_id(
                            agent_id=source_agent_id
                        )
                        if sender_user_id is None:
                            raise ValueError(
                                f"username not found: agent:{source_agent_id}"
                            )
                        # bugfix-404 fix-realtime: user-target notifications must flow
                        # through EventBridge so message.created is written to
                        # conversation_events and the front-end real-time stream picks it
                        # up without a manual refresh.  Agent-target messages go via the
                        # direct create_message + relay path unchanged — the target agent
                        # receives the content through the relay channel, not the WS stream.
                        #
                        # emit_instant_message is used instead of on_turn_start/on_message_completed
                        # because background notifications carry the full text upfront — no streaming
                        # phase.  message.created is emitted with final content + delivery_status=
                        # "completed" so the front-end renders the settled bubble immediately with no
                        # empty-window spinner (bugfix-404 reviewer feedback).
                        if (
                            resolved_target.kind in {"user_id", "conversation_id"}
                            and self._execution.can_emit_instant_message()
                        ):
                            message = self._execution.emit_instant_message(
                                conversation_id=conversation_id,
                                agent_user_id=sender_user_id,
                                agent_id=source_agent_id,
                                content=text,
                            )
                        else:
                            message = self._message_repository.create_message(
                                conversation_id=conversation_id,
                                sender_user_id=sender_user_id,
                                sender_type="agent",
                                content=text,
                            )
                        # The asyncio lock is process-local. The durable first write is
                        # the authority when another handler/process races this message.
                        owns_durable_dispatch = True
                        if dispatch_request_key is not None:
                            durable_dispatch = (
                                self._conversation_persistence.record_dispatch(
                                    AgentDispatchRecord(
                                        dispatch_request_key=dispatch_request_key,
                                        source_agent_id=source_agent_id,
                                        target_kind=resolved_target.kind,
                                        target_id=resolved_target.id,
                                        conversation_id=conversation_id,
                                        message_id=message.id,
                                    )
                                )
                            )
                            owns_durable_dispatch = (
                                durable_dispatch.message_id == message.id
                            )
                        if (
                            owns_durable_dispatch
                            and resolved_target.kind == "agent_id"
                            and self._relay_service is not None
                        ):
                            target_node_id = (
                                self._conversation_persistence.agent_node_id(
                                    agent_id=resolved_target.id
                                )
                            )
                            if target_node_id is not None:
                                _relay_result = self._relay_service.enqueue_message_relay(
                                    message=message,
                                    target_node_id=target_node_id,
                                    idempotency_key=f"agent-dm:{message.id}:{resolved_target.id}",
                                    sender_user_id=sender_user_id,
                                    conversation_type="direct",
                                    _override_agent_id=resolved_target.id,
                                )
                                if _relay_result.created:
                                    await self.push_relay_message(
                                        relay_task_id=_relay_result.relay_task.relay_task_id,
                                        target_node_id=target_node_id,
                                        payload=_relay_result.relay_task.payload,
                                    )
                        if not owns_durable_dispatch:
                            existing = durable_dispatch
                            conversation_id = durable_dispatch.conversation_id
                            resolved_target = DispatchTarget(
                                kind=durable_dispatch.target_kind,
                                id=durable_dispatch.target_id,
                            )
                            message_id = durable_dispatch.message_id
                    else:
                        conversation_id = existing.conversation_id
                        resolved_target = DispatchTarget(
                            kind=existing.target_kind,
                            id=existing.target_id,
                        )
                        message_id = existing.message_id
            else:
                conversation_id = existing.conversation_id
                resolved_target = DispatchTarget(
                    kind=existing.target_kind,
                    id=existing.target_id,
                )
                message_id = existing.message_id
        except ValueError as exc:
            return {
                "type": "error",
                "payload": {
                    "code": "invalid_agent_message",
                    "message": str(exc),
                },
            }
        except RuntimeError as exc:
            return {
                "type": "error",
                "payload": {
                    "code": "gateway_not_configured",
                    "message": str(exc),
                },
            }

        if existing is None:
            message_id = message.id
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.message",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "target_kind": resolved_target.kind,
                "target_id": resolved_target.id,
                "source_agent_id": source_agent_id,
            },
        }

    @staticmethod
    def _resolve_source_agent_id_from_dispatch(*, source_raw: str) -> str:
        """Resolve source agent id forwarded in dispatch payload."""
        source_agent_id, _ = GatewayRelay._resolve_dispatch_source_from_session_id(
            source_raw=source_raw
        )
        return source_agent_id

    @staticmethod
    def _resolve_dispatch_source_from_session_id(
        *, source_raw: str
    ) -> tuple[str, str | None]:
        """Resolve source agent id and optional dispatch request id from one source payload."""
        normalized = source_raw.strip()
        if normalized.startswith("agent:"):
            normalized = normalized[len("agent:") :].strip()
        dispatch_request_id = None
        if "|tool_call:" in normalized:
            source_part, dispatch_part = normalized.split("|tool_call:", 1)
            normalized = source_part.strip()
            dispatch_request_id = dispatch_part.strip() or None
            if dispatch_request_id is None:
                raise ValueError("from_session_id tool_call suffix must be non-empty")
        if not normalized:
            raise ValueError("from_session_id must carry source agent id")
        return (normalized, dispatch_request_id)

    async def handle_system_message(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist one server-originated system notification into an IM conversation.

        System messages are non-first-person notifications injected by the gateway
        (e.g. self_evolution_review notifications).  They use ``sender_type='system'``
        so the IM frontend can render them with a distinct visual style.

        Args:
            payload: Must include ``conversation_id`` (str) and ``text`` (str).

        Returns:
            Ack dict with ``message_id`` on success, or error dict on failure.
        """
        if self._conversation_persistence is None or self._message_repository is None:
            return {
                "type": "error",
                "payload": {
                    "code": "gateway_not_configured",
                    "message": "conversation_repository must be configured",
                },
            }

        try:
            conversation_id = _require_text(
                payload.get("conversation_id"), field_name="conversation_id"
            ).strip()
            text = _require_text(payload.get("text"), field_name="text").strip()

            notice: SystemNotice | None = None
            caller_idempotency_key: str | None = None
            raw_notice = payload.get("system_notice")
            if raw_notice is not None:
                if not isinstance(raw_notice, dict):
                    raise ValueError("system_notice must be an object")
                kind = _require_text(
                    raw_notice.get("kind"), field_name="system_notice.kind"
                ).strip()
                if kind != "self_evolution_review":
                    raise ValueError("unsupported system_notice.kind")
                source_agent_id = _require_text(
                    raw_notice.get("source_agent_id"),
                    field_name="system_notice.source_agent_id",
                ).strip()
                raw_targets = raw_notice.get("updated_targets")
                if not isinstance(raw_targets, list) or not raw_targets:
                    raise ValueError(
                        "system_notice.updated_targets must be a non-empty list"
                    )
                if not all(isinstance(target, str) for target in raw_targets):
                    raise ValueError(
                        "system_notice.updated_targets must contain strings"
                    )
                unknown_targets = set(raw_targets) - {"skills", "memory"}
                if unknown_targets:
                    raise ValueError(
                        "system_notice.updated_targets contains unknown value"
                    )
                updated_targets = tuple(
                    target for target in ("skills", "memory") if target in raw_targets
                )
                node_id = _require_text(
                    payload.get("node_id"), field_name="node_id"
                ).strip()
                caller_idempotency_key = _require_text(
                    payload.get("idempotency_key"), field_name="idempotency_key"
                ).strip()
                display_name = self._conversation_persistence.resolve_system_notice_source_display_name(
                    conversation_id=conversation_id,
                    source_agent_id=source_agent_id,
                    node_id=node_id,
                )
                notice = SystemNotice(
                    kind=kind,
                    source_agent_id=source_agent_id,
                    source_agent_display_name=display_name,
                    updated_targets=updated_targets,
                )

            message = self._message_repository.create_message(
                conversation_id=conversation_id,
                sender_user_id=self._conversation_persistence.system_user_id(),
                sender_type="system",
                content=text,
                system_notice=notice,
                emit_created_event=notice is not None,
                caller_idempotency_key=caller_idempotency_key,
            )
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.system_message",
                    "message_id": message.id,
                },
            }
        except ValueError as exc:
            return {
                "type": "error",
                "payload": {"code": "invalid_system_message", "message": str(exc)},
            }

    def record_relay_failure(
        self,
        *,
        conversation_id: str,
        message_id: str,
        relay_task_id: str,
        target_node_id: str,
        reason: str,
        guidance: str,
    ) -> None:
        """Persist actionable conversation events for relay failures before execution starts."""
        if self._event_repository is None:
            return
        base_payload = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "relay_task_id": relay_task_id,
            "target_node_id": target_node_id,
            "reason": reason,
            "guidance": guidance,
            "progress_state": "failed",
            "semantic": "relay_failed_before_processing",
        }
        self._event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type="relay.failed",
            delivery_status="failed",
            payload=base_payload,
        )
        self._event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type="conversation.notice",
            delivery_status="failed",
            payload={
                **base_payload,
                "notice_type": "action_required",
            },
        )
        self._event_repository.update_message_delivery_status(
            message_id=message_id,
            delivery_status="failed",
        )

    def _persist_receipt_events(
        self, *, task, node_id: str, detail: str | None
    ) -> None:  # noqa: ANN001
        if self._event_repository is None:
            return
        progress_map = {
            "sent": ("relay.accepted", "accepted", "accepted_by_gateway"),
            "completed": ("relay.completed", "completed", "agent_run_completed"),
            "failed": ("relay.failed", "failed", "agent_run_failed"),
        }
        event_type, progress_state, semantic = progress_map[
            task.receipt_status or task.status
        ]
        payload = {
            "conversation_id": task.conversation_id,
            "message_id": task.message_id,
            "relay_task_id": task.relay_task_id,
            "target_node_id": task.target_node_id,
            "node_id": node_id,
            "agent_id": task.payload.get("agent_id"),
            "idempotency_key": task.idempotency_key,
            "relay_metadata": task.payload.get("metadata", {}),
            "detail": detail,
            "progress_state": progress_state,
            "semantic": semantic,
        }
        self._event_repository.append_event(
            conversation_id=task.conversation_id,
            message_id=task.message_id,
            event_type=event_type,
            delivery_status=task.status,
            payload=payload,
        )
        if progress_state == "completed":
            self._event_repository.append_event(
                conversation_id=task.conversation_id,
                message_id=task.message_id,
                event_type="message.delivered",
                delivery_status="completed",
                payload={
                    **payload,
                    "progress_state": "completed",
                    "semantic": "agent_run_completed",
                },
            )
            self._event_repository.update_message_delivery_status(
                message_id=task.message_id,
                delivery_status="completed",
            )
        elif progress_state == "failed":
            self._event_repository.append_event(
                conversation_id=task.conversation_id,
                message_id=task.message_id,
                event_type="conversation.notice",
                delivery_status="failed",
                payload={
                    **payload,
                    "notice_type": "action_required",
                    "guidance": "检查目标节点连接、查看执行日志后重试；如持续失败可切换节点。",
                },
            )
            self._event_repository.update_message_delivery_status(
                message_id=task.message_id,
                delivery_status="failed",
            )
