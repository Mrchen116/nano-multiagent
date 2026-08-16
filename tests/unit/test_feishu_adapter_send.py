"""Behavior tests for Feishu outbound delivery."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import OutboundMessage
from personal_assistant.channels.feishu.adapter import (
    _build_runtime_card,
    FeishuAdapter,
)
from personal_assistant.channels.feishu.client import FeishuAPIError
from personal_assistant.config.local_store import DisplayConfig
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.runtime_footer import (
    TerminalFooterFacts,
    build_external_final_projection,
)


def _adapter(client_class: MagicMock) -> tuple[FeishuAdapter, MagicMock]:
    client = client_class.return_value
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(MagicMock())
    return adapter, client


@pytest.mark.parametrize(
    ("target", "receive_id", "receive_id_type"),
    [
        ("feishu:cli_a:dm:ou_user1", "ou_user1", "open_id"),
        ("feishu:cli_a:group:oc_group", "oc_group", "chat_id"),
    ],
)
@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_send_maps_stable_target_to_provider_address(
    client_class: MagicMock,
    target: str,
    receive_id: str,
    receive_id_type: str,
) -> None:
    adapter, client = _adapter(client_class)

    adapter.send(
        OutboundMessage(
            channel_name="feishu:plato",
            text="reply",
            target_chat_id=target,
            metadata={},
        )
    )

    client.send_message.assert_called_once_with(
        receive_id=receive_id,
        text="reply",
        receive_id_type=receive_id_type,
    )


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_send_final_runtime_footer_as_one_prepared_interactive_card(
    client_class: MagicMock,
) -> None:
    adapter, client = _adapter(client_class)
    client.prepare_outbound_markdown.return_value = "reply ![chart](img_card_1)"

    adapter.send(
        OutboundMessage(
            channel_name="feishu:plato",
            text="reply ![chart](https://example.test/chart.png)",
            target_chat_id="feishu:cli_a:dm:ou_user1",
            metadata={
                "reply_phase": "final",
                "runtime_footer": "gpt-5.4 · ctx 42%",
            },
        )
    )

    client.prepare_outbound_markdown.assert_called_once_with(
        "reply ![chart](https://example.test/chart.png)"
    )
    client.send_message.assert_not_called()
    client.send_interactive_message.assert_called_once()
    kwargs = client.send_interactive_message.call_args.kwargs
    assert kwargs["receive_id"] == "ou_user1"
    assert kwargs["receive_id_type"] == "open_id"
    assert kwargs["card"] == {
        "config": {"wide_screen_mode": True},
        "elements": [
            {"tag": "markdown", "content": "reply ![chart](img_card_1)"},
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "gpt-5.4 · ctx 42%",
                    }
                ],
            },
        ],
    }


def test_runtime_card_bounds_oversized_body_without_dropping_footer() -> None:
    card = _build_runtime_card(
        text="😀" * 40_000,
        runtime_footer="gpt-5.4 · ctx 42%",
    )

    assert len(json.dumps(card, ensure_ascii=False).encode()) < 30_000
    assert card["elements"][0]["content"].endswith("... truncated")
    assert card["elements"][2]["elements"][0]["content"] == "gpt-5.4 · ctx 42%"


def test_runtime_card_stays_bounded_for_an_oversized_configured_model() -> None:
    projection = build_external_final_projection(
        "Answer.",
        config=DisplayConfig(runtime_footer_enabled=True),
        channel_name="feishu:agent-a",
        facts=TerminalFooterFacts(model="x" * 30_000),
    )

    card = _build_runtime_card(
        text=projection.text,
        runtime_footer=projection.runtime_footer,
    )

    assert len(json.dumps(card, ensure_ascii=False).encode()) < 30_000
    assert card["elements"][2]["elements"][0]["content"] == projection.runtime_footer


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_runtime_footer_hint_does_not_change_nonfinal_transport(
    client_class: MagicMock,
) -> None:
    adapter, client = _adapter(client_class)

    adapter.send(
        OutboundMessage(
            channel_name="feishu:plato",
            text="progress",
            target_chat_id="feishu:cli_a:group:oc_group",
            metadata={
                "reply_phase": "intermediate",
                "runtime_footer": "gpt-5.4 · ctx 42%",
            },
        )
    )

    client.send_interactive_message.assert_not_called()
    client.prepare_outbound_markdown.assert_not_called()
    client.send_message.assert_called_once_with(
        receive_id="oc_group",
        text="progress",
        receive_id_type="chat_id",
    )


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_send_rejects_blank_text_before_provider_request(
    client_class: MagicMock,
) -> None:
    adapter, client = _adapter(client_class)

    with pytest.raises(ValueError, match="text must be non-empty"):
        adapter.send(
            OutboundMessage(
                channel_name="feishu:plato",
                text="   ",
                target_chat_id="feishu:cli_a:group:oc_group",
                metadata={},
            )
        )

    client.send_message.assert_not_called()


@pytest.mark.parametrize(
    ("reply_phase", "reaction_removed"),
    [("intermediate", False), ("final", True), ("control", True)],
)
@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_ack_reaction_clears_only_after_terminal_visible_reply(
    client_class: MagicMock,
    reply_phase: str,
    reaction_removed: bool,
) -> None:
    adapter, client = _adapter(client_class)
    client.add_reaction.return_value = "reaction-1"
    adapter.ack_message("message-1")

    adapter.send(
        OutboundMessage(
            channel_name="feishu:plato",
            text="reply",
            target_chat_id="feishu:cli_a:dm:ou_user1",
            metadata={
                "feishu_message_id": "message-1",
                "reply_phase": reply_phase,
            },
        )
    )

    if reaction_removed:
        client.delete_reaction.assert_called_once_with(
            message_id="message-1",
            reaction_id="reaction-1",
        )
    else:
        client.delete_reaction.assert_not_called()


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_send_failure_is_visible_and_keeps_ack_reaction(
    client_class: MagicMock,
) -> None:
    adapter, client = _adapter(client_class)
    client.add_reaction.return_value = "reaction-1"
    client.send_message.side_effect = FeishuAPIError("send failed", code=500)
    adapter.ack_message("message-1")

    with pytest.raises(FeishuAPIError):
        adapter.send(
            OutboundMessage(
                channel_name="feishu:plato",
                text="reply",
                target_chat_id="feishu:cli_a:dm:ou_user1",
                metadata={
                    "feishu_message_id": "message-1",
                    "reply_phase": "final",
                },
            )
        )

    client.delete_reaction.assert_not_called()
