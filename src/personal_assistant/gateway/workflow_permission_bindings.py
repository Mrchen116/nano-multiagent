"""Bind asynchronous Workflow child permissions to their launch surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

_TERMINAL_WORKFLOW_STATUSES = frozenset({"completed", "failed", "stopped"})


@dataclass(frozen=True, slots=True)
class WorkflowPermissionDeliveryAnchor:
    """Keep the immutable launch surface for one foreground Workflow tool call."""

    parent_session_id: str
    parent_run_id: str
    parent_tool_call_id: str
    conversation_id: str
    message_id: str
    external_metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowPermissionDelivery:
    """Pair one tagged permission event with its exact launch anchor."""

    anchor: WorkflowPermissionDeliveryAnchor
    event: Mapping[str, Any]


class WorkflowPermissionDeliveryBindingRegistry:
    """Route Workflow child permission events without a latest-anchor fallback."""

    def __init__(self) -> None:
        self._pre_anchors: dict[tuple[str, str], WorkflowPermissionDeliveryAnchor] = {}
        self._run_anchors: dict[str, WorkflowPermissionDeliveryAnchor] = {}
        self._request_bindings: dict[
            tuple[str, str, str], WorkflowPermissionDeliveryAnchor
        ] = {}
        self._resolved_requests: set[tuple[str, str, str]] = set()
        self._buffered: dict[str, list[dict[str, Any]]] = {}
        self._closing: set[str] = set()

    def register_pre_anchor(self, anchor: WorkflowPermissionDeliveryAnchor) -> None:
        """Register the foreground launch row before a Workflow run id exists."""

        key = (anchor.parent_session_id, anchor.parent_tool_call_id)
        existing = self._pre_anchors.get(key)
        if existing is not None and existing != anchor:
            raise ValueError("Workflow launch correlation already has another anchor")
        self._pre_anchors[key] = anchor

    def bind_run(
        self,
        *,
        parent_session_id: str,
        parent_tool_call_id: str,
        workflow_run_id: str,
    ) -> tuple[WorkflowPermissionDelivery, ...]:
        """Bind tool-result machine correlation and flush earlier child events."""

        if not parent_session_id or not parent_tool_call_id or not workflow_run_id:
            return ()
        key = (parent_session_id, parent_tool_call_id)
        anchor = self._pre_anchors.pop(key, None)
        existing = self._run_anchors.get(workflow_run_id)
        if existing is not None:
            if anchor is not None and existing != anchor:
                raise ValueError("Workflow run already has another launch anchor")
            return self._flush(workflow_run_id)
        if anchor is None:
            return ()
        self._run_anchors[workflow_run_id] = anchor
        deliveries = self._flush(workflow_run_id)
        self._cleanup_if_closed(workflow_run_id)
        return deliveries

    def accept_event(
        self,
        *,
        parent_session_id: str,
        event: Mapping[str, Any],
    ) -> tuple[WorkflowPermissionDelivery, ...]:
        """Accept one tagged session event and return newly routable deliveries."""

        declared_session = _text(
            event.get("parent_session_id")
            or event.get("workflow_parent_session_id")
        )
        if declared_session and declared_session != parent_session_id:
            return ()
        workflow_run_id = _text(event.get("workflow_run_id"))
        if not workflow_run_id:
            return ()
        event_name = _text(event.get("event"))
        if event_name == "workflow_run_updated":
            if _text(event.get("status")) in _TERMINAL_WORKFLOW_STATUSES:
                self._closing.add(workflow_run_id)
                self._cleanup_if_closed(workflow_run_id)
            return ()
        if event_name not in {"permission_request", "permission_resolved"}:
            return ()
        normalized = dict(event)
        status, delivery = self._try_deliver(workflow_run_id, normalized)
        if status == "blocked":
            self._buffered.setdefault(workflow_run_id, []).append(normalized)
            return ()
        deliveries = [delivery] if delivery is not None else []
        deliveries.extend(self._flush(workflow_run_id))
        self._cleanup_if_closed(workflow_run_id)
        return tuple(deliveries)

    def has_run(self, workflow_run_id: str) -> bool:
        """Return whether routing state is retained for one Workflow run."""

        return (
            workflow_run_id in self._run_anchors
            or workflow_run_id in self._buffered
            or workflow_run_id in self._closing
        )

    def _try_deliver(
        self, workflow_run_id: str, event: dict[str, Any]
    ) -> tuple[
        Literal["delivered", "ignored", "blocked"],
        WorkflowPermissionDelivery | None,
    ]:
        anchor = self._run_anchors.get(workflow_run_id)
        if anchor is None:
            return "blocked", None
        key = _request_key(workflow_run_id, event)
        if key is None:
            return "ignored", None
        event_name = _text(event.get("event"))
        if event_name == "permission_request":
            if key in self._request_bindings or key in self._resolved_requests:
                return "ignored", None
            self._request_bindings[key] = anchor
            return "delivered", WorkflowPermissionDelivery(anchor=anchor, event=event)
        if key in self._resolved_requests:
            return "ignored", None
        request_anchor = self._request_bindings.pop(key, None)
        if request_anchor is None:
            return "blocked", None
        self._resolved_requests.add(key)
        return "delivered", WorkflowPermissionDelivery(
            anchor=request_anchor,
            event=event,
        )

    def _flush(self, workflow_run_id: str) -> tuple[WorkflowPermissionDelivery, ...]:
        buffered = self._buffered.get(workflow_run_id)
        if not buffered or workflow_run_id not in self._run_anchors:
            return ()
        pending = sorted(buffered, key=_event_sequence)
        deliveries: list[WorkflowPermissionDelivery] = []
        while pending:
            progressed = False
            blocked: list[dict[str, Any]] = []
            for event in pending:
                status, delivery = self._try_deliver(workflow_run_id, event)
                if status == "blocked":
                    blocked.append(event)
                    continue
                progressed = True
                if delivery is not None:
                    deliveries.append(delivery)
            pending = blocked
            if not progressed:
                break
        if pending:
            self._buffered[workflow_run_id] = pending
        else:
            self._buffered.pop(workflow_run_id, None)
        return tuple(deliveries)

    def _cleanup_if_closed(self, workflow_run_id: str) -> None:
        if workflow_run_id not in self._closing:
            return
        if workflow_run_id not in self._run_anchors:
            return
        if self._buffered.get(workflow_run_id):
            return
        if any(key[0] == workflow_run_id for key in self._request_bindings):
            return
        self._run_anchors.pop(workflow_run_id, None)
        self._closing.discard(workflow_run_id)
        self._resolved_requests = {
            key for key in self._resolved_requests if key[0] != workflow_run_id
        }


def _request_key(
    workflow_run_id: str, event: Mapping[str, Any]
) -> tuple[str, str, str] | None:
    agent_call_id = _text(event.get("agent_call_id"))
    request_id = _text(event.get("request_id"))
    if not agent_call_id or not request_id:
        return None
    return workflow_run_id, agent_call_id, request_id


def _event_sequence(event: Mapping[str, Any]) -> int:
    raw = event.get("_id") or event.get("sequence_num")
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else 0


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = [
    "WorkflowPermissionDelivery",
    "WorkflowPermissionDeliveryAnchor",
    "WorkflowPermissionDeliveryBindingRegistry",
]
