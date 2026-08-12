"""Feishu native permission approval cards."""

from __future__ import annotations

import json
from itertools import islice
import logging
import reprlib
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
_REASON_FIELD_NAME = "nano_permission_reason"
_PENDING_TTL_SECONDS = 60 * 60
_MAX_INPUT_PREVIEW_CHARS = 1200
_MAX_INPUT_FIELDS = 12
_MAX_INPUT_LABEL_CHARS = 80
_MAX_TOOL_DISPLAY_CHARS = 80
_MAX_REQUEST_DISPLAY_CHARS = 512
_MAX_OPTION_LABEL_CHARS = 80
_MAX_NESTED_ITEMS = 8
_MAX_NESTING_DEPTH = 3
_MAX_REASON_CHARS = 1000
_MAX_COMPACT_LINES = 2
_MAX_COMPACT_LINE_CHARS = 44


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
    reason: str = ""
    operator_open_id: str = ""
    operator_user_id: str = ""
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
            reveal_input_values=receive_id_type == "open_id",
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
        action = value.get("nano_action")
        if action != _ACTION_PERMISSION_DECISION:
            return None
        approval_id = str(value.get("approval_id") or "").strip()
        decision = str(value.get("decision") or "").strip()
        if not approval_id or not decision:
            return None
        collect_reason = value.get("collect_reason") is True and not _decision_allows(
            decision
        )

        with self._lock:
            pending = self._pending_by_approval_id.get(approval_id)
            if pending is None:
                return _build_status_card(
                    title="Approval request is no longer available",
                    text="This tool request was already closed or expired.",
                    template="grey",
                )
            if pending.status == "resolved" and pending.decision:
                return _build_resolved_card(pending, pending.decision)
            if pending.status == "expired":
                return _build_status_card(
                    title="Approval request expired",
                    text="This tool request timed out. Ask the agent to retry if needed.",
                    template="grey",
                )
            if pending.status != "pending":
                return _build_status_card(
                    title="Approval request was already handled",
                    text="The kernel no longer has this request pending.",
                    template="grey",
                )
            if time.monotonic() - pending.created_at > _PENDING_TTL_SECONDS:
                pending.status = "expired"
                return _build_status_card(
                    title="Approval request expired",
                    text="This tool request timed out. Ask the agent to retry if needed.",
                    template="grey",
                )
            if decision not in pending.options:
                return None
            if (
                pending.owner_open_id
                and event.operator_open_id != pending.owner_open_id
            ):
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
            if collect_reason:
                return _build_deny_reason_card(pending, decision)
            pending.status = "submitting"
            pending.decision = decision
            pending.reason = (
                "" if _decision_allows(decision) else _reason_from_event(event)
            )
            pending.operator_open_id = event.operator_open_id
            pending.operator_user_id = event.operator_user_id

        accepted = self._submit_decision(pending, decision)
        if not accepted:
            with self._lock:
                pending.status = "closed"
                pending.decision = None
            return _build_status_card(
                title="Approval request was already handled",
                text="The kernel no longer has this request pending.",
                template="grey",
            )
        with self._lock:
            pending.status = "resolved"
            pending.decision = decision
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
                    "reason": pending.reason,
                    "source": "feishu",
                    "operator_open_id": pending.operator_open_id,
                    "operator_user_id": pending.operator_user_id,
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
    reveal_input_values: bool,
) -> dict[str, Any]:
    request_id = str(request.get("request_id") or "")
    tool_name = str(request.get("tool_name") or "tool")
    question = str(request.get("question") or "Approve this tool call?")
    actions = [
        _approval_button(
            approval_id=approval_id,
            request_id=request_id,
            decision=option.decision,
            label=option.label,
            collect_reason=not _decision_allows(option.decision),
        )
        for option in options
    ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": "Tool approval required"},
        },
        "elements": [
            *_approval_metadata_elements(
                tool_name=tool_name,
                question=question,
                reveal_request_details=reveal_input_values,
            ),
            *_tool_input_elements(
                request.get("tool_input"),
                reveal_values=reveal_input_values,
            ),
            {
                "tag": "action",
                "actions": actions,
            },
        ],
    }


def _build_deny_reason_card(
    pending: _PendingApproval,
    decision: str,
) -> dict[str, Any]:
    tool_name = str(pending.request.get("tool_name") or "tool")
    question = str(pending.request.get("question") or "Approve this tool call?")
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red",
            "title": {"tag": "plain_text", "content": "Deny tool approval"},
        },
        "elements": [
            *_approval_metadata_elements(
                tool_name=tool_name,
                question=question,
                reveal_request_details=pending.receive_id_type == "open_id",
            ),
            *_tool_input_elements(
                pending.request.get("tool_input"),
                reveal_values=pending.receive_id_type == "open_id",
            ),
            {
                "tag": "form",
                "name": "nano_permission_deny_form",
                "elements": [
                    {
                        "tag": "input",
                        "name": _REASON_FIELD_NAME,
                        "label": {
                            "tag": "plain_text",
                            "content": "Reason for denial",
                        },
                        "placeholder": {
                            "tag": "plain_text",
                            "content": "Optional. Sent only when you deny.",
                        },
                    },
                    _approval_button(
                        approval_id=pending.approval_id,
                        request_id=pending.request_id,
                        decision=decision,
                        label="Deny",
                        action_type="form_submit",
                    ),
                ],
            },
        ],
    }


def _build_resolved_card(pending: _PendingApproval, decision: str) -> dict[str, Any]:
    tool_name = _truncate(
        str(pending.request.get("tool_name") or "tool"),
        _MAX_TOOL_DISPLAY_CHARS,
    )
    decision_display = _truncate(
        _decision_display(decision),
        _MAX_OPTION_LABEL_CHARS,
    )
    lines = [
        f"**Tool:** {_escape_lark_markdown(tool_name)}",
        f"**Decision:** {_escape_lark_markdown(decision_display)}",
    ]
    if pending.reason:
        lines.append(f"**Reason:** {_truncate(pending.reason, _MAX_REASON_CHARS)}")
    return _build_status_card(
        title="Tool approval approved"
        if _decision_allows(decision)
        else "Tool approval denied",
        text="\n".join(lines),
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


def _approval_button(
    *,
    approval_id: str,
    request_id: str,
    decision: str,
    label: str,
    action_type: str | None = None,
    collect_reason: bool = False,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "nano_action": _ACTION_PERMISSION_DECISION,
        "approval_id": approval_id,
        "request_id": request_id,
        "decision": decision,
    }
    if collect_reason:
        value["collect_reason"] = True
    button = {
        "tag": "button",
        "name": f"nano_permission_{decision}",
        "text": {
            "tag": "plain_text",
            "content": _truncate(label, _MAX_OPTION_LABEL_CHARS),
        },
        "type": _button_type(decision),
        "value": value,
    }
    if action_type:
        button["action_type"] = action_type
    return button


def _approval_metadata_elements(
    *,
    tool_name: str,
    question: str,
    reveal_request_details: bool,
) -> list[dict[str, Any]]:
    tool_name = _truncate(tool_name, _MAX_TOOL_DISPLAY_CHARS)
    tool_display = (
        f"<text_tag color='neutral'>{tool_name}</text_tag>"
        if _is_safe_text_tag_identifier(tool_name)
        else _escape_lark_markdown(tool_name)
    )
    request_display = (
        _escape_lark_markdown(_truncate(question, _MAX_REQUEST_DISPLAY_CHARS))
        if reveal_request_details
        else "Review details in internal IM."
    )
    return [
        {
            "tag": "markdown",
            "content": (f"**Tool:** {tool_display}\n**Request:** {request_display}"),
        },
        {"tag": "hr"},
    ]


def _is_safe_text_tag_identifier(text: str) -> bool:
    return bool(text) and all(char.isalnum() or char in "_.-" for char in text)


def _tool_input_elements(
    value: object,
    *,
    reveal_values: bool,
) -> list[dict[str, Any]]:
    if not value:
        return [{"tag": "markdown", "content": "**Input:** no input"}]
    if isinstance(value, Mapping):
        total_fields = len(value)
        items = list(islice(value.items(), _MAX_INPUT_FIELDS))
    else:
        total_fields = 1
        items = [("value", value)]
    value_limit = max(1, _MAX_INPUT_PREVIEW_CHARS // len(items))
    fields: list[dict[str, Any]] = []
    for field_index, (key, field_value) in enumerate(items):
        raw_label = _truncate(str(key), _MAX_INPUT_LABEL_CHARS)
        label = _escape_lark_markdown(raw_label)
        if not reveal_values:
            fields.append(
                _short_input_container(
                    label,
                    "hidden in group chat",
                    field_index=field_index,
                )
            )
            continue
        display = _truncate(_tool_input_value(field_value), value_limit)
        if not _needs_input_detail(display):
            fields.append(
                _short_input_container(label, display, field_index=field_index)
            )
            continue
        fields.append(
            _long_input_panel(
                _plain_input_label(raw_label),
                display,
                field_index=field_index,
            )
        )
    elements = [{"tag": "markdown", "content": "**Input**"}, *fields]
    omitted_fields = total_fields - len(items)
    if omitted_fields:
        elements.append(
            {
                "tag": "markdown",
                "content": f"*{omitted_fields} additional fields truncated*",
            }
        )
    if not reveal_values:
        elements.append(
            {
                "tag": "markdown",
                "content": (
                    "*Input values are hidden in group chats. "
                    "Review the internal IM approval for full details.*"
                ),
            }
        )
    return elements


def _short_input_container(
    label: str,
    display: str,
    *,
    field_index: int,
) -> dict[str, Any]:
    lines = _physical_lines(display)
    unit = "line" if len(lines) == 1 else "lines"
    return {
        "tag": "column_set",
        "element_id": f"inputField{field_index}",
        "flex_mode": "none",
        "background_style": "grey-50",
        "margin": "0px 0px 4px 0px",
        "columns": [
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "background_style": "grey-50",
                "vertical_spacing": "2px",
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"**{label} · {len(lines)} {unit}**",
                        "margin": "0px",
                    },
                    {
                        "tag": "markdown",
                        "content": _escape_input_value(display),
                        "margin": "0px",
                    },
                ],
            }
        ],
    }


def _long_input_panel(
    label: str,
    display: str,
    *,
    field_index: int,
) -> dict[str, Any]:
    lines = _physical_lines(display)
    unit = "line" if len(lines) == 1 else "lines"
    summary = _compact_input_value(display)
    return {
        "tag": "collapsible_panel",
        "element_id": f"inputField{field_index}",
        "expanded": False,
        "background_color": "grey",
        "border": {"color": "grey", "corner_radius": "5px"},
        "direction": "vertical",
        "vertical_spacing": "4px",
        "margin": "0px 0px 4px 0px",
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"{_plain_input_label(label)} · {len(lines)} {unit}\n{summary}",
            },
            "icon": {
                "tag": "standard_icon",
                "token": "down-small-ccm_outlined",
                "size": "16px 16px",
            },
            "icon_position": "right",
            "icon_expanded_angle": 180,
            "background_color": "grey",
            "width": "fill",
            "vertical_align": "top",
        },
        "elements": [
            {
                "tag": "markdown",
                "content": _escape_input_value(display),
                "margin": "0px",
            }
        ],
    }


def _plain_input_label(label: str) -> str:
    return label.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _needs_input_detail(text: str) -> bool:
    lines = _physical_lines(text)
    return len(lines) > _MAX_COMPACT_LINES or any(
        len(line) > _MAX_COMPACT_LINE_CHARS for line in lines
    )


def _compact_input_value(text: str) -> str:
    lines = _physical_lines(text)
    return "\n".join(
        _compact_line(line, _MAX_COMPACT_LINE_CHARS)
        for line in lines[:_MAX_COMPACT_LINES]
    )


def _compact_line(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    tail_chars = min(28, limit // 3)
    head_chars = limit - tail_chars - 3
    return f"{text[:head_chars].rstrip()}...{text[-tail_chars:].lstrip()}"


def _physical_lines(text: str) -> list[str]:
    return text.split("\n")


def _escape_input_value(text: str) -> str:
    return "\n".join(_escape_lark_markdown(line) for line in text.split("\n"))


def _tool_input_value(value: object) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(
            _bounded_input_value(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    except TypeError:
        return reprlib.repr(value)


def _bounded_input_value(value: object, *, depth: int = 0) -> object:
    if isinstance(value, str):
        return _truncate(value, _MAX_INPUT_PREVIEW_CHARS)
    if depth >= _MAX_NESTING_DEPTH:
        if isinstance(value, (Mapping, list, tuple)):
            return "... nested value truncated"
        return value
    if isinstance(value, Mapping):
        items = list(islice(value.items(), _MAX_NESTED_ITEMS))
        bounded = {
            _truncate(str(key), _MAX_INPUT_LABEL_CHARS): _bounded_input_value(
                nested,
                depth=depth + 1,
            )
            for key, nested in items
        }
        omitted = len(value) - len(items)
        if omitted:
            bounded["..."] = f"{omitted} additional items truncated"
        return bounded
    if isinstance(value, (list, tuple)):
        items = list(islice(value, _MAX_NESTED_ITEMS))
        bounded = [_bounded_input_value(item, depth=depth + 1) for item in items]
        omitted = len(value) - len(items)
        if omitted:
            bounded.append(f"... {omitted} additional items truncated")
        return bounded
    return value


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "... truncated"
    if limit <= len(marker):
        return marker[:limit]
    return text[: limit - len(marker) - 1].rstrip() + "\n" + marker


def _button_type(decision: str) -> str:
    return "primary" if _decision_allows(decision) else "danger"


def _escape_lark_markdown(text: str) -> str:
    return "".join(
        char if char.isalnum() or char in " -." else f"&#{ord(char)};" for char in text
    )


def _decision_allows(decision: str) -> bool:
    normalized = decision.lower()
    return normalized in {"allow", "allowed", "approve", "approved", "yes"} or (
        normalized.startswith("allow_")
    )


def _decision_display(decision: str) -> str:
    normalized = decision.strip().lower()
    if normalized in {"deny", "denied", "reject", "rejected", "no"}:
        return "Denied"
    if normalized in {"allow_once", "approve_once"}:
        return "Allowed once"
    if normalized in {"allow_session", "allow_for_session", "approve_session"}:
        return "Allowed for session"
    if _decision_allows(normalized):
        return "Allowed"
    return decision.replace("_", " ").strip().capitalize() or "Resolved"


def _reason_from_event(event: FeishuCardActionEvent) -> str:
    for key in (_REASON_FIELD_NAME, "reason", "permission_reason"):
        reason = _string_value(event.form_value.get(key))
        if reason:
            return _truncate(reason, _MAX_REASON_CHARS)
    reason = _string_value(event.action_value.get("reason"))
    if reason:
        return _truncate(reason, _MAX_REASON_CHARS)
    return _truncate(event.input_value.strip(), _MAX_REASON_CHARS)


def _string_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        for key in ("value", "text", "content"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return ""
