"""Provider-boundary tests for the Feishu client."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.client import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuClient,
    _parse_feishu_event,
)


@patch("personal_assistant.channels.feishu.client.FeishuWorkerRuntime")
def test_start_and_stop_own_one_worker_runtime(worker_class: MagicMock) -> None:
    worker = worker_class.return_value
    on_message = MagicMock()
    client = FeishuClient(app_id="cli_a", app_secret="secret")

    client.start(on_message)
    client.stop()

    assert worker_class.call_args.kwargs["app_id"] == "cli_a"
    assert worker_class.call_args.kwargs["on_event"] is on_message
    worker.start.assert_called_once()
    worker.stop.assert_called_once_with(drain=True)


def _sdk_event(
    *,
    chat_type: str = "p2p",
    content: str = '{"text":"hello"}',
    message_type: str = "text",
    mentions: list[MagicMock] | None = None,
) -> MagicMock:
    event = MagicMock()
    event.event.sender.sender_id.open_id = "ou_user"
    event.event.message.chat_id = "oc_chat"
    event.event.message.chat_type = chat_type
    event.event.message.content = content
    event.event.message.message_type = message_type
    event.event.message.message_id = "message-1"
    event.event.message.create_time = "1786324620000"
    event.event.message.mentions = mentions or []
    return event


@pytest.mark.parametrize(
    ("chat_type", "content", "expected_text", "is_group"),
    [
        ("p2p", '{"text":"hello"}', "hello", False),
        ("group", '{"text":"group update"}', "group update", True),
        ("p2p", "non-json attachment body", "non-json attachment body", False),
    ],
)
def test_event_parsing_preserves_visible_message_identity(
    chat_type: str,
    content: str,
    expected_text: str,
    is_group: bool,
) -> None:
    parsed = _parse_feishu_event(_sdk_event(chat_type=chat_type, content=content))

    assert parsed.text == expected_text
    assert parsed.sender_open_id == "ou_user"
    assert parsed.chat_id == "oc_chat"
    assert parsed.message_id == "message-1"
    assert parsed.is_group is is_group
    assert parsed.source_timestamp == datetime(2026, 8, 10, 1, 17, tzinfo=timezone.utc)


def test_event_parsing_normalizes_mentions() -> None:
    mention = MagicMock()
    mention.id.open_id = "ou_bot"
    mention.name = "nano"
    mention.key = "@_user_1"

    parsed = _parse_feishu_event(
        _sdk_event(
            content='{"text":"@_user_1 hello"}',
            mentions=[mention],
        )
    )

    assert parsed.text == "@nano hello"
    assert [(item.open_id, item.name) for item in parsed.mentions] == [
        ("ou_bot", "nano")
    ]


def _client_with_response(response: MagicMock) -> tuple[FeishuClient, MagicMock]:
    rest = MagicMock()
    rest.im.v1.message.create.return_value = response
    client = FeishuClient(app_id="cli_a", app_secret="secret")
    client._rest_client = rest
    return client, rest


def _response(*, success: bool, code: int, msg: str = "") -> MagicMock:
    response = MagicMock()
    response.success.return_value = success
    response.code = code
    response.msg = msg
    return response


def test_send_message_builds_provider_request() -> None:
    client, rest = _client_with_response(_response(success=True, code=0))

    client.send_message(
        receive_id="oc_group",
        text="hello",
        receive_id_type="chat_id",
    )

    request = rest.im.v1.message.create.call_args.args[0]
    assert request.receive_id_type == "chat_id"
    assert request.request_body.receive_id == "oc_group"
    assert request.request_body.msg_type == "post"
    assert json.loads(request.request_body.content) == {
        "zh_cn": {
            "content": [[{"tag": "md", "text": "hello"}]],
        }
    }


def test_empty_receive_id_is_rejected_before_provider_request() -> None:
    client, rest = _client_with_response(_response(success=True, code=0))

    with pytest.raises(ValueError, match="receive_id"):
        client.send_message(receive_id="  ", text="hello")

    rest.im.v1.message.create.assert_not_called()


@pytest.mark.parametrize(
    ("code", "error_type"),
    [(401, FeishuAuthError), (403, FeishuAuthError), (99999, FeishuAPIError)],
)
def test_send_errors_are_classified_and_fail_loud(
    code: int,
    error_type: type[Exception],
) -> None:
    client, _ = _client_with_response(
        _response(success=False, code=code, msg="provider rejected request")
    )

    with pytest.raises(error_type):
        client.send_message(receive_id="oc_group", text="hello")


def test_reaction_create_and_delete_use_message_identity() -> None:
    rest = MagicMock()
    create_response = _response(success=True, code=0)
    create_response.data.reaction_id = "reaction-1"
    rest.im.v1.message_reaction.create.return_value = create_response
    rest.im.v1.message_reaction.delete.return_value = _response(success=True, code=0)
    client = FeishuClient(app_id="cli_a", app_secret="secret")
    client._rest_client = rest

    reaction_id = client.add_reaction(
        message_id="message-1",
        emoji_type="THINKING",
    )
    client.delete_reaction(message_id="message-1", reaction_id=reaction_id)

    create_request = rest.im.v1.message_reaction.create.call_args.args[0]
    delete_request = rest.im.v1.message_reaction.delete.call_args.args[0]
    assert reaction_id == "reaction-1"
    assert create_request.message_id == "message-1"
    assert delete_request.message_id == "message-1"
    assert delete_request.reaction_id == "reaction-1"
