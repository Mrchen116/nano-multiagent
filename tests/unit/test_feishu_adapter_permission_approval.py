"""Tests for FeishuAdapter native permission approval cards."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import FeishuCardActionEvent
from personal_assistant.gateway.group_context_store import GroupContextStore

_REASON_FIELD = "nano_permission_reason"


def _adapter(decision_callback: MagicMock) -> FeishuAdapter:
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        owner_open_id="ou_owner",
        permission_decision_callback=decision_callback,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(MagicMock())
    return adapter


def _request(
    *,
    request_id: str = "req-1",
    options: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "tool_name": "bash",
        "tool_input": {"command": "pwd"},
        "question": "Allow bash?",
        "options": options
        if options is not None
        else [
            {"id": "allow_once", "label": "Allow once"},
            {"id": "deny", "label": "Deny"},
        ],
        "status": "pending",
    }


def _buttons(card: dict[str, object]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if value.get("tag") == "button":
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(card)
    return found


def _action_value(card: dict[str, object], decision: str) -> dict[str, object]:
    for action in _buttons(card):
        value = action.get("value")
        if isinstance(value, dict) and value.get("decision") == decision:
            return value
    raise AssertionError(f"decision {decision!r} not found in card")


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_request_sends_interactive_card_and_click_submits_decision(
    mock_fc_cls: MagicMock,
) -> None:
    mock_fc = MagicMock()
    mock_fc.send_interactive_message.return_value = "om_card_001"
    mock_fc_cls.return_value = mock_fc
    decision_callback = MagicMock(return_value=True)
    adapter = _adapter(decision_callback)

    sent = adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )

    assert sent is True
    mock_fc.send_interactive_message.assert_called_once()
    sent_again = adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    assert sent_again is True
    mock_fc.send_interactive_message.assert_called_once()
    call_kwargs = mock_fc.send_interactive_message.call_args.kwargs
    assert call_kwargs["receive_id"] == "oc_group"
    assert call_kwargs["receive_id_type"] == "chat_id"
    card = call_kwargs["card"]
    summary = card["elements"][0]
    assert summary["tag"] == "markdown"
    assert "```" not in summary["content"]
    assert "\n\n" not in summary["content"]
    action_row = card["elements"][1]
    assert action_row["tag"] == "action"
    assert [button["tag"] for button in action_row["actions"]] == [
        "button",
        "button",
    ]
    assert all("action_type" not in button for button in action_row["actions"])
    assert all(element["tag"] != "form" for element in card["elements"])
    allow_value = _action_value(call_kwargs["card"], "allow_once")
    assert allow_value["request_id"] == "req-1"
    assert allow_value["decision"] == "allow_once"
    deny_value = _action_value(call_kwargs["card"], "deny")
    assert deny_value["collect_reason"] is True

    response_card = adapter._handle_card_action(
        FeishuCardActionEvent(
            action_value=allow_value,
            operator_open_id="ou_owner",
            operator_user_id="u_owner",
            open_chat_id="oc_group",
            form_value={_REASON_FIELD: "stale allow reason should be ignored"},
        )
    )

    decision_callback.assert_called_once_with(
        {
            "request_id": "req-1",
            "decision": "allow_once",
            "reason": "",
            "source": "feishu",
            "operator_open_id": "ou_owner",
            "operator_user_id": "u_owner",
            "agent_id": "plato",
            "run_id": "run-1",
            "target_chat_id": "feishu:cli_a:group:oc_group",
        }
    )
    assert response_card is not None
    assert response_card["header"]["template"] == "green"

    adapter._handle_card_action(
        FeishuCardActionEvent(
            action_value=allow_value,
            operator_open_id="ou_owner",
            operator_user_id="u_owner",
            open_chat_id="oc_group",
        )
    )
    decision_callback.assert_called_once()


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_deny_submits_reason_and_resolved_card_shows_it(
    mock_fc_cls: MagicMock,
) -> None:
    mock_fc = MagicMock()
    mock_fc.send_interactive_message.return_value = "om_card_001"
    mock_fc_cls.return_value = mock_fc
    decision_callback = MagicMock(return_value=True)
    adapter = _adapter(decision_callback)
    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    card = mock_fc.send_interactive_message.call_args.kwargs["card"]
    deny_value = _action_value(card, "deny")

    reason_card = adapter._handle_card_action(
        FeishuCardActionEvent(
            action_value=deny_value,
            operator_open_id="ou_owner",
            operator_user_id="u_owner",
            open_chat_id="oc_group",
        )
    )

    decision_callback.assert_not_called()
    assert reason_card is not None
    assert reason_card["header"]["title"]["content"] == "Deny tool approval"
    reason_form = reason_card["elements"][1]
    assert reason_form["tag"] == "form"
    assert reason_form["elements"][0]["tag"] == "input"
    assert reason_form["elements"][0]["name"] == _REASON_FIELD
    reason_buttons = [
        child
        for child in reason_form["elements"]
        if isinstance(child, dict) and child.get("tag") == "button"
    ]
    assert len(reason_buttons) == 1
    assert reason_buttons[0]["action_type"] == "form_submit"

    response_card = adapter._handle_card_action(
        FeishuCardActionEvent(
            action_value=_action_value(reason_card, "deny"),
            operator_open_id="ou_owner",
            operator_user_id="u_owner",
            open_chat_id="oc_group",
            form_value={_REASON_FIELD: "  too risky  "},
        )
    )

    decision_callback.assert_called_once_with(
        {
            "request_id": "req-1",
            "decision": "deny",
            "reason": "too risky",
            "source": "feishu",
            "operator_open_id": "ou_owner",
            "operator_user_id": "u_owner",
            "agent_id": "plato",
            "run_id": "run-1",
            "target_chat_id": "feishu:cli_a:group:oc_group",
        }
    )
    assert response_card is not None
    assert response_card["header"]["template"] == "red"
    assert response_card["header"]["title"]["content"] == "Tool approval denied"
    content = response_card["elements"][0]["content"]
    assert content == "**Tool:** `bash`\n**Decision:** Denied\n**Reason:** too risky"
    assert "Operator" not in content
    assert "ou_owner" not in content
    assert "\n\n" not in content


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_click_from_non_owner_is_rejected(mock_fc_cls: MagicMock) -> None:
    mock_fc = MagicMock()
    mock_fc.send_interactive_message.return_value = "om_card_001"
    mock_fc_cls.return_value = mock_fc
    decision_callback = MagicMock(return_value=True)
    adapter = _adapter(decision_callback)
    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(options=[{"id": "allow_once", "label": "Allow once"}]),
    )
    value = _action_value(
        mock_fc.send_interactive_message.call_args.kwargs["card"], "allow_once"
    )

    card = adapter._handle_card_action(
        FeishuCardActionEvent(
            action_value=value,
            operator_open_id="ou_someone_else",
            operator_user_id="u_other",
            open_chat_id="oc_group",
        )
    )

    assert card is None
    decision_callback.assert_not_called()


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_mark_permission_resolved_updates_card_and_prevents_later_click(
    mock_fc_cls: MagicMock,
) -> None:
    mock_fc = MagicMock()
    mock_fc.send_interactive_message.return_value = "om_card_001"
    mock_fc_cls.return_value = mock_fc
    decision_callback = MagicMock(return_value=True)
    adapter = _adapter(decision_callback)
    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(options=[{"id": "deny", "label": "Deny"}]),
    )
    value = _action_value(
        mock_fc.send_interactive_message.call_args.kwargs["card"], "deny"
    )

    resolved = adapter.mark_permission_resolved(request_id="req-1", decision="deny")

    assert resolved is True
    mock_fc.update_interactive_message.assert_called_once()
    update_kwargs = mock_fc.update_interactive_message.call_args.kwargs
    assert update_kwargs["message_id"] == "om_card_001"
    assert update_kwargs["card"]["header"]["template"] == "red"

    adapter._handle_card_action(
        FeishuCardActionEvent(
            action_value=value,
            operator_open_id="ou_owner",
            operator_user_id="u_owner",
            open_chat_id="oc_group",
        )
    )
    decision_callback.assert_not_called()
