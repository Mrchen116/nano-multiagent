"""Behavior tests for Feishu outbound delivery."""

from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import OutboundImage, OutboundMessage
from personal_assistant.channels.feishu.adapter import (
    _build_runtime_card,
    FeishuAdapter,
)
from personal_assistant.channels.feishu.client import FeishuAPIError, FeishuClient
from personal_assistant.gateway.group_context_store import GroupContextStore


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


@pytest.mark.parametrize("footer", [False, True])
def test_prepared_images_reject_partial_results_without_publishing(
    footer: bool,
) -> None:
    rest = MagicMock()
    success = MagicMock()
    success.success.return_value = True
    success.data.image_key = "img_uploaded"
    failure = MagicMock()
    failure.success.return_value = False
    failure.code = 500
    failure.msg = "provider failure"
    rest.im.v1.image.create.side_effect = [success, failure]
    rest.im.v1.message.create.return_value = success
    client = FeishuClient(app_id="cli_a", app_secret="secret")
    client._rest_client = rest
    adapter = FeishuAdapter(
        name="feishu:plato",
        app_id="cli_a",
        app_secret="secret",
        group_context_store=MagicMock(),
    )
    adapter._client = client
    outbound = OutboundMessage(
        channel_name=adapter.name,
        target_chat_id="feishu:cli_a:dm:ou_user1",
        text="before ![a](nano-image-pending:0) ![b](nano-image-pending:1) after ![c](nano-image-pending:2)",
        images=(
            OutboundImage(0, b"a", "image/png", "a.png"),
            OutboundImage(1, b"b", "image/png", "b.png"),
            OutboundImage(2, b"", "image/png", "c.png", image_key="img_existing"),
        ),
        metadata={"reply_phase": "final", "runtime_footer": "model · ctx 42%"}
        if footer
        else {},
    )
    prepared = adapter.prepare_images(outbound)
    assert prepared.app_id == prepared.connector_account_id == "cli_a"
    assert prepared.entries[0].image_key == "img_uploaded"
    assert prepared.entries[1].error_code
    assert prepared.entries[2].image_key == "img_existing"
    rest.im.v1.message.create.assert_not_called()
    assert rest.im.v1.image.create.call_count == 2
    admitted = False

    def before() -> bool:
        nonlocal admitted
        admitted = True
        return True

    def after() -> None:
        nonlocal admitted
        admitted = False

    def create(request: object) -> MagicMock:
        assert admitted
        return success

    rest.im.v1.message.create.side_effect = create
    from personal_assistant.gateway.reply_images import ImageDeliveryError

    with pytest.raises(ImageDeliveryError):
        adapter.send_prepared(outbound, prepared, before, after)
    assert not admitted
    assert rest.im.v1.image.create.call_count == 2
    rest.im.v1.message.create.assert_not_called()
    with pytest.raises(ValueError, match="another application"):
        adapter.send_prepared(
            outbound, replace(prepared, app_id="cli_other"), before, after
        )
    rest.im.v1.message.create.assert_not_called()


def test_prepared_feishu_retry_keeps_provider_uuid_and_receipt() -> None:
    rest = MagicMock()
    response = MagicMock()
    response.success.return_value = True
    response.data.message_id = "om_confirmed"
    rest.im.v1.message.create.return_value = response
    client = FeishuClient(app_id="cli_a", app_secret="secret")
    client._rest_client = rest
    for _ in range(2):
        receipt = client.send_prepared_message(
            receive_id="chat",
            text="prepared",
            idempotency_key="run:bubble:feishu:chat",
            before_publish=lambda: True,
            after_publish=lambda: None,
        )
        assert receipt == "delivered"
        assert receipt.message_id == "om_confirmed"
    requests = [call.args[0] for call in rest.im.v1.message.create.call_args_list]
    assert requests[0].request_body.uuid == requests[1].request_body.uuid
    assert len(requests[0].request_body.uuid) == 32
