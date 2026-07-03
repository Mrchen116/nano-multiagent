"""Tests for FeishuAdapter native permission approval cards."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import FeishuCardActionEvent
from personal_assistant.gateway.group_context_store import GroupContextStore


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
    allow_value = call_kwargs["card"]["elements"][1]["actions"][0]["value"]
    assert allow_value["request_id"] == "req-1"
    assert allow_value["decision"] == "allow_once"

    response_card = adapter._handle_card_action(
        FeishuCardActionEvent(
            action_value=allow_value,
            operator_open_id="ou_owner",
            operator_user_id="u_owner",
            open_chat_id="oc_group",
        )
    )

    decision_callback.assert_called_once_with(
        {
            "request_id": "req-1",
            "decision": "allow_once",
            "reason": "",
            "source": "feishu",
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
    value = mock_fc.send_interactive_message.call_args.kwargs["card"]["elements"][1][
        "actions"
    ][0]["value"]

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
    value = mock_fc.send_interactive_message.call_args.kwargs["card"]["elements"][1][
        "actions"
    ][0]["value"]

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
