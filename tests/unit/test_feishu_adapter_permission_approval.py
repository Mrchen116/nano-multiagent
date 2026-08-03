"""Security and first-wins behavior for Feishu permission cards."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import FeishuCardActionEvent
from personal_assistant.gateway.group_context_store import GroupContextStore

_REASON_FIELD = "nano_permission_reason"


def _adapter(decision_callback: MagicMock) -> FeishuAdapter:
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        owner_open_id="ou_owner",
        permission_decision_callback=decision_callback,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(MagicMock())
    return adapter


def _request() -> dict[str, object]:
    return {
        "request_id": "request-1",
        "tool_name": "bash",
        "tool_input": {
            "command": "cat ~/.ssh/id_rsa",
            "path": ".gitconfig",
            "token": "secret-token-value",
        },
        "question": "Allow bash?",
        "options": [
            {"id": "allow_once", "label": "Allow once"},
            {"id": "deny", "label": "Deny"},
        ],
        "status": "pending",
    }


def _action_value(card: object, decision: str) -> dict[str, object]:
    if isinstance(card, dict):
        value = card.get("value")
        if isinstance(value, dict) and value.get("decision") == decision:
            return value
        for child in card.values():
            try:
                return _action_value(child, decision)
            except LookupError:
                pass
    elif isinstance(card, list):
        for child in card:
            try:
                return _action_value(child, decision)
            except LookupError:
                pass
    raise LookupError(decision)


def _event(
    action_value: dict[str, object],
    *,
    operator_open_id: str = "ou_owner",
    reason: str = "",
) -> FeishuCardActionEvent:
    return FeishuCardActionEvent(
        action_value=action_value,
        operator_open_id=operator_open_id,
        operator_user_id="user-operator",
        open_chat_id="oc_group",
        form_value={_REASON_FIELD: reason} if reason else {},
    )


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_card_is_idempotent_and_only_owner_can_decide(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    callback = MagicMock(return_value=True)
    adapter = _adapter(callback)

    assert adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    assert adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    client.send_interactive_message.assert_called_once()
    card = client.send_interactive_message.call_args.kwargs["card"]
    allow = _action_value(card, "allow_once")

    assert adapter._handle_card_action(
        _event(allow, operator_open_id="ou_not_owner")
    ) is None
    callback.assert_not_called()
    adapter._handle_card_action(_event(allow))
    adapter._handle_card_action(_event(allow))

    callback.assert_called_once()
    decision = callback.call_args.args[0]
    assert decision["request_id"] == "request-1"
    assert decision["decision"] == "allow_once"
    assert decision["operator_open_id"] == "ou_owner"


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_card_summarizes_keys_without_sensitive_values(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    adapter = _adapter(MagicMock(return_value=True))

    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )

    rendered = str(client.send_interactive_message.call_args.kwargs["card"])
    assert "command" in rendered
    assert "path" in rendered
    assert "token" in rendered
    assert "cat ~/.ssh/id_rsa" not in rendered
    assert ".gitconfig" not in rendered
    assert "secret-token-value" not in rendered


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_deny_reason_reaches_kernel_without_exposing_operator_identity(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    callback = MagicMock(return_value=True)
    adapter = _adapter(callback)
    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    pending_card = client.send_interactive_message.call_args.kwargs["card"]
    reason_card = adapter._handle_card_action(_event(_action_value(pending_card, "deny")))
    assert reason_card is not None

    resolved_card = adapter._handle_card_action(
        _event(_action_value(reason_card, "deny"), reason="  too risky  ")
    )

    decision = callback.call_args.args[0]
    assert decision["decision"] == "deny"
    assert decision["reason"] == "too risky"
    assert resolved_card is not None
    assert "ou_owner" not in str(resolved_card)
    assert "user-operator" not in str(resolved_card)


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_im_resolution_or_kernel_rejection_prevents_later_card_decision(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    callback = MagicMock(return_value=False)
    adapter = _adapter(callback)
    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    card = client.send_interactive_message.call_args.kwargs["card"]
    allow = _action_value(card, "allow_once")

    first_response = adapter._handle_card_action(_event(allow))
    adapter._handle_card_action(_event(allow))

    callback.assert_called_once()
    assert first_response is not None
    assert "already" in str(first_response).lower()
