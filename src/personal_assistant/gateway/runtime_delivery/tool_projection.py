"""Own tool event interpretation and in-flight state for both delivery views."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .context import RunDeliveryContext


@dataclass(frozen=True, slots=True)
class ToolCallProjection:
    """Carry the existing durable and live wire shapes of one tool fact."""

    shadow: dict[str, Any]
    live: dict[str, Any]


class ToolCallProjector:
    """Keep tool lifecycle state independent of transport and shadow persistence."""

    def __init__(self, running: dict[str, dict[str, dict[str, Any]]]) -> None:
        self._running = running

    def project(self, event: Mapping[str, Any]) -> ToolCallProjection:
        """Interpret one admitted tool start/end and update its in-flight state.

        Args:
            event: A tool_start or tool_end event already admitted by the observer.

        Returns:
            Separate destination payloads retaining their existing wire conventions.
        """
        run_id = str(event.get("run_id") or "").strip()
        call_id = str(event.get("call_id") or "").strip() or run_id
        starting = event["event"] == "tool_start"
        call: dict[str, Any] = {
            "id": call_id,
            "name": str(event.get("name") or ""),
            "status": "running"
            if starting
            else "failed"
            if event.get("error")
            else "completed",
            "input": event.get("arguments")
            if isinstance(event.get("arguments"), dict)
            else {},
        }
        presentation = event.get("presentation")
        if isinstance(presentation, Mapping):
            if presentation.get("summary"):
                call["output"] = str(presentation["summary"])
            if presentation.get("detail") is not None:
                call["detail"] = presentation["detail"]
            if presentation.get("emoji"):
                call["emoji"] = str(presentation["emoji"])
        if starting:
            self._running.setdefault(run_id, {})[call_id] = {
                key: value for key, value in call.items() if key not in {"id", "status"}
            }
            return ToolCallProjection(shadow=call, live=dict(call))

        inner = self._running.get(run_id)
        if inner is not None:
            inner.pop(call_id, None)
            if not inner:
                self.finish(run_id)
        duration = event.get("duration_ms")
        if isinstance(duration, (int, float)):
            call["duration_ms"] = int(duration)
        reason = event.get("reason_code")
        if isinstance(reason, str) and reason:
            call["reason"] = reason
        approval = event.get("approval")
        if isinstance(approval, str) and approval:
            call["approval"] = approval
        # Live frames historically include null end fields and trim classifications;
        # durable snapshots omit absent fields and preserve the original strings.
        live = dict(call)
        live.update(
            reason=reason.strip() if isinstance(reason, str) else None,
            output=call.get("output"),
            duration_ms=call.get("duration_ms"),
        )
        if "approval" in live:
            live["approval"] = live["approval"].strip()
        return ToolCallProjection(shadow=call, live=live)

    def for_live(
        self, projection: ToolCallProjection, context: RunDeliveryContext
    ) -> dict[str, Any]:
        """Apply the live-only revalidation annotation after the offline gate.

        Args:
            projection: The already interpreted tool event.
            context: The live run's delivery context.

        Returns:
            The live wire payload, without altering the shadow view.
        """
        live = projection.live
        if (
            live["status"] == "running"
            and context.revalidate_output
            and live["name"] == "send_message"
            and live["input"].get("target") == context.conversation_id
        ):
            live["detail"] = {
                **(live.get("detail") or {}),
                "status": "pending_revalidation",
            }
            self._running[context.run_id][live["id"]]["detail"] = live["detail"]
        return live

    def reconcile(self, event: Mapping[str, Any]) -> dict[str, ToolCallProjection]:
        """Take remaining calls once and project their abnormal terminal state.

        Args:
            event: The observer's run_terminal_reconcile event.

        Returns:
            Failed calls indexed by call id; already completed calls are absent.
        """
        run_id = str(event.get("run_id") or "").strip()
        reason = str(event.get("reason") or "interrupted").strip()
        output = event.get("content")
        results = {}
        for call_id, running in self._running.pop(run_id, {}).items():
            # Retain the existing bare-name recovery shape at this one seam.
            call = dict(running) if isinstance(running, Mapping) else {}
            shadow = {
                **call,
                "id": call_id,
                "name": str(call.get("name") or running),
                "status": "failed",
                "reason": reason,
                "input": call.get("input")
                if isinstance(call.get("input"), dict)
                else {},
            }
            live = {
                "id": call_id,
                "name": str(call.get("name") or "")
                if isinstance(running, Mapping)
                else str(running),
                "status": "failed",
                "reason": reason or "interrupted",
                "input": call.get("input") or {},
            }
            for key in ("output", "detail", "emoji"):
                if call.get(key) is not None:
                    live[key] = call[key]
            if isinstance(output, str) and output:
                shadow["output"] = live["output"] = output
            results[call_id] = ToolCallProjection(shadow=shadow, live=live)
        return results

    def finish(self, run_id: str) -> None:
        """Release any remaining tool state at normal run completion.

        Args:
            run_id: The completed run identity.
        """
        self._running.pop(run_id, None)
