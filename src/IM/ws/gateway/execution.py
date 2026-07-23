from __future__ import annotations

import asyncio
import logging


from IM.application.event_bridge import EventBridge
from IM.application.metrics_service import MetricsService
from IM.infra.gateway_persistence import GatewayConversationPersistence
from IM.infra.repositories.config_boundaries import AgentConfigBoundaryRepository
from IM.infra.repositories.events import EventRepository
from IM.infra.repositories.messages import MessageRepository
from .protocol import (
    _not_registered_error,
    _optional_non_negative_int,
    _optional_text,
    _optional_usage,
    _parse_token_usage,
    _parse_tool_call,
    _require_text,
    parse_node_report_event,
    parse_streaming_delta_event,
)

_logger = logging.getLogger(__name__)

from .sessions import GatewaySessions


class GatewayExecution:
    """Own Gateway report and streaming translation into the IM EventBridge timeline."""

    def __init__(
        self,
        *,
        sessions: GatewaySessions,
        conversation_persistence: GatewayConversationPersistence | None = None,
        message_repository: MessageRepository | None = None,
        boundary_repository: AgentConfigBoundaryRepository | None = None,
        event_repository: EventRepository | None = None,
        metrics_service: MetricsService | None = None,
        event_bridge: EventBridge | None = None,
        lock: asyncio.Lock,
    ) -> None:
        self._sessions = sessions
        self._conversation_persistence = conversation_persistence
        self._message_repository = message_repository
        self._boundary_repository = boundary_repository
        self._event_repository = event_repository
        self._metrics_service = metrics_service
        self._event_bridge = event_bridge
        self._lock = lock
        self._reports: list[dict[str, object]] = []

    def can_emit_instant_message(self) -> bool:
        """Report whether this runtime can create browser-visible instant messages."""
        return self._event_bridge is not None

    def emit_instant_message(self, **kwargs: object):
        """Persist and notify a completed background notification through EventBridge."""
        if self._event_bridge is None:
            raise RuntimeError("event_bridge is not configured")
        return self._event_bridge.emit_instant_message(**kwargs)

    async def handle_report(self, *, payload: dict[str, object]) -> dict[str, object]:
        # Validate node_id first; a missing or empty node_id means the payload is structurally
        # invalid and we cannot even look up the connection. Return an error frame so the Gateway
        # knows the frame was rejected, but keep the WS connection alive.
        try:
            event = parse_node_report_event(payload)
            node_id = event.node_id
        except (RuntimeError, ValueError) as exc:
            return {
                "type": "error",
                "payload": {"code": "bad_payload", "message": str(exc)},
            }
        connection = await self._sessions.snapshot_connection(node_id=node_id)
        if connection is None:
            return _not_registered_error(node_id=node_id)
        connection.reports.append(payload)
        async with self._lock:
            self._reports.append(payload)
        # Persist errors (e.g. FK violations from synthetic conversation_id/message_id) must not
        # propagate out of the WS dispatch layer. A malformed heartbeat payload lacking real FK
        # rows in the messages table would raise sqlite3.IntegrityError here and close the
        # connection. The correct behaviour is to record the failure and return a normal ack
        # so the Gateway's connection stays alive.
        try:
            self._persist_report_event(payload=payload)
            self._persist_report_usage(payload=payload)
        except Exception as exc:  # noqa: BLE001
            # Non-fatal: persistence failed (likely FK violation from synthetic IDs).
            # Log via events so the failure is visible without severing the connection.
            _logger.warning(
                "node.report persist failed for node_id=%s: %s", node_id, exc
            )
        return {
            "type": "ack",
            "payload": {"message_type": "node.report", "node_id": node_id},
        }

    async def handle_agent_config_boundary(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist a non-message cache boundary before acknowledging its Gateway outbox item."""
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if self._boundary_repository is None:
            raise RuntimeError("boundary_repository is not configured")
        connection = await self._sessions.snapshot_connection(node_id=node_id)
        if connection is None:
            return _not_registered_error(node_id=node_id)
        boundary = self._boundary_repository.record_from_gateway(
            boundary_id=_require_text(
                payload.get("boundary_id"), field_name="boundary_id"
            ),
            node_id=node_id,
            owner_id=connection.owner_id,
            conversation_id=_require_text(
                payload.get("conversation_id"), field_name="conversation_id"
            ),
            agent_id=_require_text(payload.get("agent_id"), field_name="agent_id"),
            before_message_id=_require_text(
                payload.get("before_message_id"), field_name="before_message_id"
            ),
            runtime_fingerprint=_require_text(
                payload.get("runtime_fingerprint"), field_name="runtime_fingerprint"
            ),
            fingerprint_schema=_require_text(
                payload.get("fingerprint_schema"), field_name="fingerprint_schema"
            ),
            profile_version=_optional_non_negative_int(
                payload.get("profile_version"), field_name="profile_version"
            ),
            applied_at=_require_text(
                payload.get("applied_at"), field_name="applied_at"
            ),
        )
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.config.boundary",
                "boundary_id": boundary.id,
                "event_id": boundary.event_id,
            },
        }

    async def handle_streaming_delta(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Translate gateway streaming events into IM WS fan-out via EventBridge.

        The gateway (personal_assistant) calls this with sub-types keyed by ``kind``:
        - ``turn_start``: agent begins a reply; EventBridge inserts placeholder message.
        - ``message_delta``: incremental text chunk; EventBridge appends content.
        - ``message_completed``: run finished; EventBridge marks message completed with token_usage.
        - ``message_discarded``: silent run; EventBridge removes the provisional message.
        - ``tool_call_upserted``: tool call started; EventBridge upserts tool_calls JSON.
        - ``tool_call_completed``: tool call done; EventBridge settles tool_calls JSON.

        Cross-tenant isolation: every frame carries ``owner_id``; EventBridge → notify callback
        → build_notify_enqueue reads conversation_participants which already gates by owner.
        The broadcast_to_users path is never called here (streaming delta is owner-scoped only).
        """
        if self._event_bridge is None:
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta"}}

        event = parse_streaming_delta_event(payload)
        kind = event.kind

        if kind == "turn_start":
            agent_id = _require_text(event.agent_id, field_name="agent_id")
            to_user_id = event.to_user_id
            raw_conversation_id = event.conversation_id

            if to_user_id is not None and raw_conversation_id is None:
                # feat-393: heartbeat/cron lazy-resolution mode.  Gateway sends to_user_id
                # (the owner) instead of conversation_id; we resolve/create the canonical
                # (owner, agent) direct conversation here, then fall through to the shared
                # on_turn_start path.  The ack returns both conversation_id and message_id
                # so the gateway can seed run_context_store with both values.
                #
                # Two modes are mutually exclusive: conversation_id → normal eager-bubble
                # path (unchanged); to_user_id → lazy canonical-conv resolution path.
                if self._conversation_persistence is None:
                    return {
                        "type": "ack",
                        "payload": {
                            "message_type": "node.streaming_delta",
                            "kind": kind,
                            "skipped": "repositories_not_configured",
                        },
                    }
                agent_user_id = event.agent_user_id
                if agent_user_id is None:
                    agent_user_id = self._conversation_persistence.agent_user_id(
                        agent_id=agent_id
                    )
                    if agent_user_id is None:
                        return {
                            "type": "ack",
                            "payload": {
                                "message_type": "node.streaming_delta",
                                "kind": kind,
                                "skipped": "agent_user_id_not_found",
                            },
                        }
                # feat-393 fix-r1: owner lookup / canonical-conv creation can fail when
                # config.node.user_id is stale or the ephemeral IM DB has no such user yet.
                # Must NOT raise out of this handler — that would close the WS connection and
                # cause the Gateway to reconnect immediately, producing the 413-open/close flap
                # seen in round-1 acceptance (refactor-387 "坏帧关连接" pattern re-introduced).
                # Per design decision-6: delivery failure ≠ run failure; log and return skipped
                # ack so the Gateway can continue and this heartbeat run completes normally.
                try:
                    conversation_id = self._conversation_persistence.resolve_user_agent_conversation(
                        agent_id=agent_id,
                        user_id=to_user_id,
                        # Pass the owner's own id as caller_owner_id so the created
                        # conversation is visible via list_conversations_for_owner.
                        # Without this, the conversation is created with the owner_id
                        # derived from the users table, which may be stale across e2e runs.
                        caller_owner_id=to_user_id,
                    )
                except (ValueError, Exception) as exc:  # noqa: BLE001
                    _logger.warning(
                        "turn_start to_user_id=%s owner_unresolved — skipping delivery: %s",
                        to_user_id,
                        exc,
                    )
                    return {
                        "type": "ack",
                        "payload": {
                            "message_type": "node.streaming_delta",
                            "kind": kind,
                            "skipped": "owner_unresolved",
                        },
                    }
                created_message = self._event_bridge.on_turn_start(
                    conversation_id=conversation_id,
                    agent_user_id=agent_user_id,
                    agent_id=agent_id,
                )
                # Return both conversation_id and message_id so the gateway can update
                # run_context_store with the resolved canonical conversation (feat-393 design §接口与数据流).
                return {
                    "type": "ack",
                    "payload": {
                        "message_type": "node.streaming_delta",
                        "kind": kind,
                        "conversation_id": conversation_id,
                        "message_id": created_message.id,
                    },
                }

            # Normal path: conversation_id is provided (eager placeholder for regular chat).
            conversation_id = _require_text(
                payload.get("conversation_id"), field_name="conversation_id"
            )
            # Resolve IM user ID from agent_id; gateway sends agent_id (e.g. "alpha"),
            # IM stores the agent as username="agent:<agent_id>" in the users table.
            agent_user_id = event.agent_user_id
            if agent_user_id is None and self._conversation_persistence is not None:
                agent_user_id = self._conversation_persistence.agent_user_id(
                    agent_id=agent_id
                )
            if agent_user_id is None:
                return {
                    "type": "ack",
                    "payload": {
                        "message_type": "node.streaming_delta",
                        "kind": kind,
                        "skipped": "agent_user_id_not_found",
                    },
                }
            created_message = self._event_bridge.on_turn_start(
                conversation_id=conversation_id,
                agent_user_id=agent_user_id,
                agent_id=agent_id,
            )
            # Return message_id in ack so PA observer can update run_context_store;
            # without this, observer keeps empty message_id and delta targets user message.
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": kind,
                    "message_id": created_message.id,
                },
            }

        elif kind == "message_delta":
            message_id = _require_text(event.message_id, field_name="message_id")
            delta_text = event.delta_text or ""
            self._event_bridge.on_message_delta(
                message_id=message_id, delta_text=delta_text
            )

        elif kind == "message_completed":
            message_id = _require_text(event.message_id, field_name="message_id")
            final_content = event.final_content
            token_usage = _parse_token_usage(event.token_usage)
            raw_ds = event.delivery_status
            # bugfix-380: delivery_status is optional (back-compat: absent → "completed");
            # if provided it must be a known terminal value. Silent fallback was a
            # regression trap — any new failure semantic added upstream (e.g. "cancelled"
            # / "timeout") that wasn't whitelisted here would degrade back to the
            # bugfix-380 pre-fix bug: empty bubble silently marked "completed".
            if raw_ds is None:
                ds = "completed"
            elif raw_ds in {"completed", "failed"}:
                ds = raw_ds
            else:
                raise ValueError(
                    f"delivery_status must be 'completed' or 'failed' when provided, got {raw_ds!r}"
                )
            # feat-445-M1: per-bubble kernel message_id forwarded by the gateway relay so
            # this bubble row is stamped with the assistant message that produced it.
            kernel_message_id = event.kernel_message_id
            self._event_bridge.on_message_completed(
                message_id=message_id,
                final_content=final_content,
                token_usage=token_usage,
                delivery_status=ds,
                kernel_message_id=kernel_message_id,
            )

        elif kind == "message_discarded":
            message_id = _require_text(event.message_id, field_name="message_id")
            reason = _require_text(event.reason, field_name="reason")
            self._event_bridge.on_message_discarded(
                message_id=message_id, reason=reason
            )

        elif kind == "run_heartbeat":
            # bugfix-417-M3 R4: kernel liveness heartbeat (tool / LLM-await /
            # parked-permission). EventBridge appends a conversation_events row so the
            # message's last_evt advances and the relay watchdog sees the run as alive —
            # the single uniform liveness signal that replaces the permission marker.
            message_id = _require_text(event.message_id, field_name="message_id")
            source = event.source or ""
            self._event_bridge.on_run_heartbeat(message_id=message_id, source=source)

        elif kind == "thinking_segment":
            # feat-439-M2: 一段思考过程项。EventBridge 持久化进 thinking_json 并广播
            # thinking.segment。seq 在 repo 持久化边界赋予(= 当前 tool_calls 数)。
            message_id = _require_text(event.message_id, field_name="message_id")
            text = event.text or ""
            self._event_bridge.on_thinking_segment(message_id=message_id, text=text)

        elif kind == "tool_call_upserted":
            message_id = _require_text(event.message_id, field_name="message_id")
            tc = _parse_tool_call(event.tool_call)
            self._event_bridge.on_tool_call_upserted(
                message_id=message_id, tool_call=tc
            )

        elif kind == "tool_call_completed":
            message_id = _require_text(event.message_id, field_name="message_id")
            tc = _parse_tool_call(event.tool_call)
            self._event_bridge.on_tool_call_completed(
                message_id=message_id, tool_call=tc
            )

        elif kind == "permission_request":
            # PA → IM: agent is awaiting a user decision; EventBridge persists the pending
            # request and fans out permission.request to connected browser clients.
            message_id = _require_text(event.message_id, field_name="message_id")
            permission_request = event.permission_request
            if not isinstance(permission_request, dict):
                raise ValueError("permission_request must be a dict")
            self._event_bridge.on_permission_request(
                message_id=message_id,
                permission_request=permission_request,
            )

        elif kind == "permission_resolved":
            # PA → IM: user's decision has been forwarded to the agent; update persisted
            # status and notify browser clients so the card can settle.
            message_id = _require_text(event.message_id, field_name="message_id")
            request_id = _require_text(event.request_id, field_name="request_id")
            decision = _require_text(event.decision, field_name="decision")
            self._event_bridge.on_permission_resolved(
                message_id=message_id,
                request_id=request_id,
                decision=decision,
            )

        elif kind == "permission_response":
            # IM → PA direction: user's decision is forwarded to the agent kernel.
            # Routing to the pending PA WS connection is handled elsewhere (REST endpoint
            # + GatewayControl.push_permission_response); streaming_delta is only PA→IM.
            pass

        return {
            "type": "ack",
            "payload": {"message_type": "node.streaming_delta", "kind": kind},
        }

    def _persist_report_event(self, *, payload: dict[str, object]) -> None:
        if self._event_repository is None:
            return
        conversation_id = _require_text(
            payload.get("conversation_id"), field_name="conversation_id"
        )
        message_id = _require_text(payload.get("message_id"), field_name="message_id")
        status = _require_text(payload.get("status"), field_name="status")
        summary = _optional_text(payload.get("summary"))
        run_id = _optional_text(payload.get("run_id"))
        guidance = _optional_text(payload.get("guidance"))
        progress_state = (
            "processing"
            if status == "running"
            else ("completed" if status == "completed" else "failed")
        )
        semantic = (
            "agent_run_processing"
            if progress_state == "processing"
            else (
                "agent_run_completed"
                if progress_state == "completed"
                else "agent_run_failed"
            )
        )
        report_payload: dict[str, object] = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "node_id": _require_text(payload.get("node_id"), field_name="node_id"),
            "run_id": run_id,
            "summary": summary,
            "status": status,
            "progress_state": progress_state,
            "semantic": semantic,
            "guidance": guidance,
        }
        # Carry token_usage in relay.report so the browser Token Chip can render real counts.
        usage = _optional_usage(payload.get("usage"))
        if usage is not None and progress_state == "completed":
            report_payload["token_usage"] = {
                "prompt": usage["prompt_tokens"],
                "completion": usage["completion_tokens"],
                "total": usage["total_tokens"],
            }
        self._event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type="relay.processing"
            if progress_state == "processing"
            else "relay.report",
            delivery_status=status,
            payload=report_payload,
        )
        if progress_state == "failed":
            self._event_repository.append_event(
                conversation_id=conversation_id,
                message_id=message_id,
                event_type="conversation.notice",
                delivery_status="failed",
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "run_id": run_id,
                    "summary": summary,
                    "status": status,
                    "progress_state": "failed",
                    "semantic": "agent_run_failed",
                    "guidance": guidance
                    or "检查节点连接和执行日志后重试；如需要可重新发送消息。",
                    "notice_type": "action_required",
                },
            )
            self._event_repository.update_message_delivery_status(
                message_id=message_id,
                delivery_status="failed",
            )

    def _persist_report_usage(self, *, payload: dict[str, object]) -> None:
        if self._metrics_service is None or self._conversation_persistence is None:
            return
        if _optional_text(payload.get("status")) != "completed":
            return
        conversation_id = _optional_text(payload.get("conversation_id"))
        usage = _optional_usage(payload.get("usage"))
        if conversation_id is None or usage is None:
            return
        owner_id = self._conversation_persistence.conversation_usage_scope(
            conversation_id=conversation_id
        )
        self._metrics_service.record_usage(
            owner_id=owner_id,
            conversation_id=None,
            agent_id=None,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            turns=1,
        )
        self._metrics_service.record_usage(
            owner_id=owner_id,
            conversation_id=conversation_id,
            agent_id=None,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            turns=1,
        )
        agent_id = _optional_text(payload.get("agent_id"))
        if agent_id is not None:
            self._metrics_service.record_usage(
                owner_id=owner_id,
                conversation_id=conversation_id,
                agent_id=agent_id,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                turns=1,
            )
