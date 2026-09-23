"""Translate registered Gateway task commands into durable service receipts."""

import sqlite3

from IM.application.task_graphs import TaskGraphActor, TaskGraphService
from IM.domain.task_graphs import TaskGraphError, require_text


class GatewayTaskGraphs:
    """Handle one task command without running agents or modifying chat messages."""

    def __init__(self, service: TaskGraphService) -> None:
        self.service = service

    async def command(self, *, payload: dict) -> dict:
        """Return a correlated success or actionable error for one registered sender."""
        body = {"request_id": payload.get("request_id")}
        try:
            require_text(payload.get("request_id"), "request_id")
            actor = TaskGraphActor(
                "agent",
                require_text(payload.get("agent_id"), "agent_id"),
                require_text(payload.get("node_id"), "node_id"),
            )
            result = self.service.execute(
                actor, payload.get("action"), payload.get("args")
            )
            body.update(ok=True, result=result)
        except TaskGraphError as exc:
            body.update(ok=False, error=exc.as_dict())
        except sqlite3.Error:
            body.update(
                ok=False,
                error={
                    "code": "source_unavailable",
                    "message": "Task storage is temporarily unavailable",
                },
            )
        return {"type": "task_graph.result", "payload": body}
