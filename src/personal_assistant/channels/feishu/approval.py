"""Feishu native permission approval cards."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from personal_assistant.channels.feishu.client import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuCardActionEvent,
    FeishuClient,
)

logger = logging.getLogger(__name__)

_ACTION_PERMISSION_DECISION = "permission_decision"
_PENDING_TTL_SECONDS = 60 * 60
_MAX_INPUT_PREVIEW_CHARS = 3000


@dataclass(frozen=True, slots=True)
class _ApprovalOption:
    decision: str
    label: str


@dataclass(slots=True)
class _PendingApproval:
    approval_id: str
    request_id: str
    run_id: str
    target_chat_id: str
    receive_id: str
    receive_id_type: str
    owner_open_id: str
    options: set[str]
    request: dict[str, Any]
    feishu_message_id: str | None = None
    status: str = "pending"
    decision: str | None = None
    created_at: float = field(default_factory=time.monotonic)


class FeishuPermissionApprovalSurface:
    """Own Feishu approval card state for one adapter instance."""

    def __init__(
        self,
        *,
        adapter_name: str,
        agent_id: str,
        client_provider: Callable[[], FeishuClient | None],
        owner_open_id_provider: Callable[[], str | None],
        decision_callback: Callable[[Mapping[str, object]], bool | None] | None,
    ) -> None:
        self._adapter_name = adapter_name
        self._agent_id = agent_id
        self._client_provider = client_provider
        self._owner_open_id_provider = owner_open_id_provider
        self._decision_callback = decision_callback
        self._lock = threading.Lock()
        self._pending_by_approval_id: dict[str, _PendingApproval] = {}
        self._approval_id_by_request_id: dict[str, str] = {}

    def send_permission_request(
        self,
        *,
        target_chat_id: str,
        request: Mapping[str, Any],
        run_id: str,
    ) -> bool:
        """Send a Feishu interactive approval card for a kernel request."""
        client = self._client_provider()
        if client is None or self._decision_callback is None:
            return False

        request_id = str(request.get("request_id") or "").strip()
        if not request_id:
            return False
        options = _parse_options(request.get("options"))
        if not options:
            logger.warning(
                "skip feishu permission card without options",
                extra={
                    "request_id": request_id,
                    "adapter": self._adapter_name,
                    "agent_id": self._agent_id,
                },
            )
            return False

        owner_open_id = (self._owner_open_id_provider() or "").strip()
        if not owner_open_id:
            logger.warning(
                "skip feishu permission card because ownerOpenId is not bound",
                extra={
                    "request_id": request_id,
                    "adapter": self._adapter_name,
                    "agent_id": self._agent_id,
                },
            )
            return False
        with self._lock:
            existing_id = self._approval_id_by_request_id.get(request_id)
            existing = (
                self._pending_by_approval_id.get(existing_id) if existing_id else None
            )
            if existing is not None and existing.status == "pending":
                return True
        receive_id, receive_id_type = _receive_target(target_chat_id)
        approval_id = uuid.uuid4().hex
        request_payload = dict(request)
        pending = _PendingApproval(
            approval_id=approval_id,
            request_id=request_id,
            run_id=run_id,
            target_chat_id=target_chat_id,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            owner_open_id=owner_open_id,
            options={opt.decision for opt in options},
            request=request_payload,
        )
        card = _build_pending_card(
            request=request_payload,
            options=options,
            approval_id=approval_id,
        )
        try:
            feishu_message_id = client.send_interactive_message(
                receive_id=receive_id,
                receive_id_type=receive_id_type,
                card=card,
            )
        except (FeishuAuthError, FeishuAPIError, RuntimeError):
            logger.warning(
                "failed to send feishu permission approval card",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "adapter": self._adapter_name,
                    "agent_id": self._agent_id,
                },
            )
            return False

        pending.feishu_message_id = feishu_message_id
        with self._lock:
            self._pending_by_approval_id[approval_id] = pending
            self._approval_id_by_request_id[request_id] = approval_id
            self._reap_expired_locked()
        return True

    def mark_permission_resolved(self, *, request_id: str, decision: str) -> bool:
        """Mark a pending Feishu card as resolved by another approval surface."""
        pending = self._resolve_pending(request_id=request_id, decision=decision)
        if pending is None:
            return False
        self._update_card(pending, _build_resolved_card(pending, decision))
        return True

    def handle_card_action(
        self, event: FeishuCardActionEvent
    ) -> Mapping[str, Any] | None:
        """Validate one Feishu card click and submit the decision to the kernel."""
        value = event.action_value
        if value.get("nano_action") != _ACTION_PERMISSION_DECISION:
            return None
        approval_id = str(value.get("approval_id") or "").strip()
        decision = str(value.get("decision") or "").strip()
        if not approval_id or not decision:
            return None

        with self._lock:
            pending = self._pending_by_approval_id.get(approval_id)
            if pending is None:
                return _build_status_card(
                    title="Approval request is no longer available",
                    text="This tool request was already closed or expired.",
                    template="grey",
                )
            if pending.status != "pending":
                return _build_resolved_card(pending, pending.decision or decision)
            if time.monotonic() - pending.created_at > _PENDING_TTL_SECONDS:
                pending.status = "expired"
                return _build_status_card(
                    title="Approval request expired",
                    text="This tool request timed out. Ask the agent to retry if needed.",
                    template="grey",
                )
            if decision not in pending.options:
                return None
            if pending.owner_open_id and event.operator_open_id != pending.owner_open_id:
                logger.warning(
                    "reject feishu permission decision from non-owner",
                    extra={
                        "request_id": pending.request_id,
                        "adapter": self._adapter_name,
                        "agent_id": self._agent_id,
                    },
                )
                return None
            if (
                pending.receive_id_type == "chat_id"
                and event.open_chat_id
                and event.open_chat_id != pending.receive_id
            ):
                return None
            pending.status = "resolved"
            pending.decision = decision

        accepted = self._submit_decision(pending, decision)
        if not accepted:
            return _build_status_card(
                title="Approval request was already handled",
                text="The kernel no longer has this request pending.",
                template="grey",
            )
        return _build_resolved_card(pending, decision)

    def _resolve_pending(
        self, *, request_id: str, decision: str
    ) -> _PendingApproval | None:
        with self._lock:
            approval_id = self._approval_id_by_request_id.get(request_id)
            if not approval_id:
                return None
            pending = self._pending_by_approval_id.get(approval_id)
            if pending is None or pending.status != "pending":
                return None
            pending.status = "resolved"
            pending.decision = decision
            return pending

    def _submit_decision(self, pending: _PendingApproval, decision: str) -> bool:
        if self._decision_callback is None:
            return False
        try:
            result = self._decision_callback(
                {
                    "request_id": pending.request_id,
                    "decision": decision,
                    "reason": "",
                    "source": "feishu",
                    "agent_id": self._agent_id,
                    "run_id": pending.run_id,
                    "target_chat_id": pending.target_chat_id,
                }
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "failed to submit feishu permission decision",
                exc_info=True,
                extra={
                    "request_id": pending.request_id,
                    "adapter": self._adapter_name,
                    "agent_id": self._agent_id,
                },
            )
            return False
        return result is not False

    def _update_card(self, pending: _PendingApproval, card: Mapping[str, Any]) -> None:
        client = self._client_provider()
        if client is None or not pending.feishu_message_id:
            return
        try:
            client.update_interactive_message(
                message_id=pending.feishu_message_id,
                card=card,
            )
        except (FeishuAuthError, FeishuAPIError, RuntimeError):
            logger.warning(
                "failed to update feishu permission approval card",
                exc_info=True,
                extra={
                    "request_id": pending.request_id,
                    "adapter": self._adapter_name,
                    "agent_id": self._agent_id,
                },
            )

    def _reap_expired_locked(self) -> None:
        now = time.monotonic()
        expired_ids = [
            approval_id
            for approval_id, pending in self._pending_by_approval_id.items()
            if now - pending.created_at > _PENDING_TTL_SECONDS
        ]
        for approval_id in expired_ids:
            pending = self._pending_by_approval_id.pop(approval_id, None)
            if pending is not None:
                self._approval_id_by_request_id.pop(pending.request_id, None)


def _parse_options(raw_options: object) -> list[_ApprovalOption]:
    if not isinstance(raw_options, list):
        return []
    options: list[_ApprovalOption] = []
    for raw in raw_options:
        if isinstance(raw, str):
            decision = raw.strip()
            label = decision
        elif isinstance(raw, Mapping):
            decision = str(
                raw.get("id")
                or raw.get("value")
                or raw.get("decision")
                or raw.get("key")
                or ""
            ).strip()
            label = str(raw.get("label") or raw.get("name") or decision).strip()
        else:
            continue
        if decision:
            options.append(_ApprovalOption(decision=decision, label=label or decision))
    return options


def _receive_target(target_chat_id: str) -> tuple[str, str]:
    parts = target_chat_id.split(":")
    receive_id = parts[-1] if len(parts) >= 4 else target_chat_id
    receive_id_type = "open_id" if ":dm:" in target_chat_id else "chat_id"
    return receive_id, receive_id_type


def _build_pending_card(
    *,
    request: Mapping[str, Any],
    options: list[_ApprovalOption],
    approval_id: str,
) -> dict[str, Any]:
    request_id = str(request.get("request_id") or "")
    tool_name = str(request.get("tool_name") or "tool")
    question = str(request.get("question") or "Approve this tool call?")
    tool_input = request.get("tool_input") or {}
    input_text = _truncate(_json_preview(tool_input), _MAX_INPUT_PREVIEW_CHARS)
    actions = [
        {
            "tag": "button",
            "text": {"tag": "plain_text", "content": option.label},
            "type": _button_type(option.decision),
            "value": {
                "nano_action": _ACTION_PERMISSION_DECISION,
                "approval_id": approval_id,
                "request_id": request_id,
                "decision": option.decision,
            },
        }
        for option in options
    ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": "Tool approval required"},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": (
                    f"**Tool:** `{tool_name}`\n\n"
                    f"**Request:** {question}\n\n"
                    f"**Input**\n```json\n{input_text}\n```"
                ),
            },
            {"tag": "action", "actions": actions},
        ],
    }


def _build_resolved_card(
    pending: _PendingApproval, decision: str
) -> dict[str, Any]:
    tool_name = str(pending.request.get("tool_name") or "tool")
    return _build_status_card(
        title="Tool approval resolved",
        text=f"`{tool_name}` was resolved with decision `{decision}`.",
        template="green" if _decision_allows(decision) else "red",
    )


def _build_status_card(*, title: str, text: str, template: str) -> dict[str, Any]:
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": [{"tag": "markdown", "content": text}],
    }


def _json_preview(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        return str(value)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 15].rstrip() + "\n... truncated"


def _button_type(decision: str) -> str:
    return "primary" if _decision_allows(decision) else "danger"


def _decision_allows(decision: str) -> bool:
    normalized = decision.lower()
    return normalized in {"allow", "allowed", "approve", "approved", "yes"} or (
        normalized.startswith("allow_")
    )
