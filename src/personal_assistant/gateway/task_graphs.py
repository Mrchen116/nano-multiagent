"""Bridge task records using real PA provenance and the existing IM transport."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urljoin
from uuid import uuid4

from personal_assistant.tools.task_graph import unavailable_result, validate_arguments


class TaskGraphBridge:
    """Translate explicit chat targets without treating prompt sources as scopes."""

    def __init__(self, *, manager: Any, binder: Any, inbox: Any) -> None:
        self._manager = manager
        self._binder = binder
        self._inbox = inbox

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Authorize one live PA session and await its correlated IM result.

        No conversation is inferred from the caller's channel or recent messages.
        After handoff, loss of confirmation retains the original request_key.
        """
        args = payload.get("args", {})
        try:
            action = validate_arguments(args)
        except ValueError as exc:
            return {
                "ok": False,
                "error": {"code": "invalid_arguments", "message": str(exc)},
            }
        agent_id = payload.get("source_agent_id")
        session_id = payload.get("origin_kernel_session_id")
        call_id = payload.get("tool_call_id")
        provenance = None
        if self._binder is not None and all(
            isinstance(item, str) and item.strip()
            for item in (agent_id, session_id, call_id)
        ):
            provenance = self._binder.capture_session_provenance(
                session_id, expected_agent_id=agent_id
            )
        if provenance is None:
            return {
                "ok": False,
                "error": {
                    "code": "unsupported_context",
                    "message": "This session has no registered PA Agent provenance. Return child results to the PA Agent to record.",
                },
            }
        if not self._binder.session_provenance_is_current(provenance):
            return {
                "ok": False,
                "error": {
                    "code": "unsupported_context",
                    "message": "Agent runtime provenance is no longer current.",
                },
            }
        if "task_graph" not in provenance.agent.config.tool_allowlist:
            return {
                "ok": False,
                "error": {
                    "code": "tool_not_allowed",
                    "message": "task_graph is not enabled in this Agent's tool configuration.",
                },
            }
        manager = self._manager
        if manager is None or not manager.connected:
            return {"ok": False, "error": unavailable_result(args, uncertain=False)}
        business = {key: value for key, value in args.items() if key != "action"}
        if "target" in business:
            target = business.pop("target")
            mapped = self._inbox.get_target(agent_id, target) if self._inbox else None
            conversation_id = (
                mapped.get("conversation_id")
                if mapped
                else target
                if target.startswith("c_")
                else None
            )
            if not isinstance(conversation_id, str) or not conversation_id:
                return {
                    "ok": False,
                    "error": {
                        "code": "source_unavailable",
                        "message": "This target has no existing IM conversation mapping yet. Retry after mapping recovers.",
                    },
                }
            business["conversation_id"] = conversation_id
        try:
            async with asyncio.timeout(40):
                response = await manager.send_json_await_ack(
                    "task_graph.command",
                    {
                        "request_id": uuid4().hex,
                        "agent_id": provenance.agent.agent_id,
                        "action": action,
                        "args": business,
                    },
                )
        except Exception:
            return {"ok": False, "error": unavailable_result(args, uncertain=True)}
        if response.get("ok") is not True:
            return {
                "ok": False,
                "error": response.get("error")
                or unavailable_result(args, uncertain=True),
            }
        result = response.get("result")
        if not isinstance(result, dict):
            return {"ok": False, "error": unavailable_result(args, uncertain=True)}
        # Registration owns the public base URL; neither model args nor local bind
        # addresses can advertise an unreachable task link to another device.
        base = manager.im_user_url
        if base:
            result = dict(result)
            for item in [result, *result.get("items", [])]:
                if item.get("relative_url"):
                    item["web_url"] = urljoin(base, item["relative_url"])
        return {"ok": True, "result": result}
