"""Authenticated Gateway work journal, history RPC and permission control transport."""

from __future__ import annotations

import asyncio
import json
import sqlite3

from IM.application.work_conversations import WorkConversationQuery
from IM.infra.repositories.agent_work import AgentWorkRepository
from IM.infra.repositories.agents import AgentProfileRepository
from IM.ws.gateway.sessions import GatewaySessions
from IM.ws.user_stream import UserStreamRegistry


class GatewayWork:
    """Route only authenticated node work, keeping it outside chat message containers."""

    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        repository: AgentWorkRepository,
        sessions: GatewaySessions,
        registry: UserStreamRegistry,
    ) -> None:
        self.repository = repository
        self.db = connection
        self.sessions = sessions
        self.registry = registry
        self.queries = WorkConversationQuery(connection, repository)
        self.waiters: dict[tuple[str, str], asyncio.Future] = {}

    async def append(self, *, payload: dict) -> dict:
        """ACK only a durable contiguous batch and invalidate affected browser pages."""
        try:
            result = self.repository.append(
                node_id=payload["node_id"],
                journal_id=payload["journal_id"],
                from_seq=payload["from_seq"],
                events=payload["events"],
            )
            if "expected_seq" not in result:
                roots = {e["root_agent_id"] for e in payload["events"]}
                for root in roots:
                    profile = AgentProfileRepository(self.db).get_profile(agent_id=root)
                    view = self.repository.view(root)
                    await self.registry.broadcast_to_user(
                        profile.owner_id,
                        json.dumps(
                            {
                                "op": "event",
                                "event_type": "agent.work.updated",
                                "data": {
                                    "agent_id": root,
                                    "revision": view["revision"],
                                },
                            }
                        ),
                    )
            return {"type": "agent.work.ack", "payload": result}
        except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            return {
                "type": "error",
                "payload": {
                    "message_type": "agent.work.append",
                    "journal_id": payload.get("journal_id"),
                    "code": "storage_unavailable"
                    if isinstance(exc, sqlite3.Error)
                    else str(exc),
                    "from_seq": payload.get("from_seq"),
                },
            }

    async def query(self, *, payload: dict) -> dict:
        """Return public conversation content with no browser read side effect."""
        request_id = payload.get("request_id")
        try:
            args = {k: v for k, v in payload.items() if k not in {"request_id"}}
            result = self.queries.query(**args)
            return {
                "type": "conversation.query.result",
                "payload": {"request_id": request_id, "ok": True, "result": result},
            }
        except (ValueError, KeyError, TypeError) as exc:
            return {
                "type": "conversation.query.result",
                "payload": {"request_id": request_id, "ok": False, "error": str(exc)},
            }

    async def permission(
        self,
        *,
        node_id: str,
        root: str,
        request_id: str,
        session_id: str,
        decision: str,
        reason: str,
    ) -> dict:
        """Wait for the actual Gateway broker decision rather than socket-send success."""
        key = (node_id, request_id)
        if key in self.waiters:
            raise ValueError("request_in_progress")
        waiter = asyncio.get_running_loop().create_future()
        self.waiters[key] = waiter
        try:
            sent = await self.sessions.send(
                target_node_id=node_id,
                message_type="agent.work.permission",
                payload={
                    "request_id": request_id,
                    "root_agent_id": root,
                    "session_id": session_id,
                    "decision": decision,
                    "reason": reason,
                },
            )
            if not sent:
                raise ValueError("node_offline")
            try:
                return await asyncio.wait_for(waiter, 10)
            except asyncio.TimeoutError:
                raise ValueError("source_unavailable") from None
        finally:
            self.waiters.pop(key, None)

    async def permission_result(self, *, payload: dict) -> dict:
        """Complete only a waiter belonging to this authenticated node and request."""
        waiter = self.waiters.get((payload.get("node_id"), payload.get("request_id")))
        if waiter is not None and not waiter.done():
            waiter.set_result(payload)
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.work.permission.result",
                "request_id": payload.get("request_id"),
            },
        }
