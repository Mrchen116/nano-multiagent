"""Feishu rich-text and image provider-boundary behavior."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.client import (
    FeishuClient,
    FeishuContentPart,
    FeishuImageTooLargeError,
    _parse_feishu_event,
)


def _sdk_event(
    *,
    content: str,
    message_type: str,
    mentions: list[MagicMock] | None = None,
) -> MagicMock:
    event = MagicMock()
    event.event.sender.sender_id.open_id = "ou_user"
    event.event.message.chat_id = "oc_chat"
    event.event.message.chat_type = "p2p"
    event.event.message.content = content
    event.event.message.message_type = message_type
    event.event.message.message_id = "message-1"
    event.event.message.mentions = mentions or []
    return event


def _response(*, success: bool = True, code: int = 0) -> MagicMock:
    response = MagicMock()
    response.success.return_value = success
    response.code = code
    response.msg = ""
    return response


def _client_with_response(response: MagicMock) -> tuple[FeishuClient, MagicMock]:
    rest = MagicMock()
    rest.im.v1.message.create.return_value = response
    client = FeishuClient(app_id="cli_a", app_secret="secret")
    client._rest_client = rest
    return client, rest


def test_event_parsing_normalizes_feishu_post_to_readable_markdown() -> None:
    content = json.dumps(
        {
            "title": "",
            "content_v2": [
                [{"tag": "text", "text": "一直在想，主要有两个", "style": []}],
                [
                    {"tag": "text", "text": "1. ", "style": []},
                    {
                        "tag": "text",
                        "text": "用multi agent，agent团队来做需求对齐和设计。",
                        "style": [],
                    },
                ],
                [
                    {"tag": "text", "text": "2. ", "style": []},
                    {
                        "tag": "text",
                        "text": "真正能loop起来，一天到晚运行。",
                        "style": [],
                    },
                ],
            ],
        },
        ensure_ascii=False,
    )

    parsed = _parse_feishu_event(_sdk_event(content=content, message_type="post"))

    assert parsed.text == (
        "一直在想，主要有两个\n"
        "1. 用multi agent，agent团队来做需求对齐和设计。\n"
        "2. 真正能loop起来，一天到晚运行。"
    )
    assert not parsed.text.startswith("{")


def test_event_parsing_preserves_post_styles_links_and_mentions() -> None:
    mention = MagicMock()
    mention.id.open_id = "ou_bot"
    mention.name = "nano"
    mention.key = "@_user_1"
    content = json.dumps(
        {
            "title": "重点",
            "content": [
                [
                    {"tag": "text", "text": "加粗", "style": ["bold"]},
                    {"tag": "text", "text": "和", "style": []},
                    {
                        "tag": "a",
                        "text": "文档",
                        "href": "https://open.feishu.cn/",
                    },
                ],
                [{"tag": "at", "user_id": "ou_bot", "user_name": "nano"}],
            ],
        },
        ensure_ascii=False,
    )

    parsed = _parse_feishu_event(
        _sdk_event(content=content, message_type="post", mentions=[mention])
    )

    assert parsed.text == "重点\n\n**加粗**和[文档](https://open.feishu.cn/)\n@nano"


def test_event_parsing_preserves_post_whitespace_and_code_indentation() -> None:
    content = json.dumps(
        {
            "content": [
                [{"tag": "text", "text": "A  B", "style": []}],
                [{"tag": "text", "text": "    indented", "style": []}],
            ]
        }
    )

    parsed = _parse_feishu_event(_sdk_event(content=content, message_type="post"))
    assert parsed.text == "A  B\n    indented"

    leading_code = json.dumps(
        {"content": [[{"tag": "text", "text": "    first line", "style": []}]]}
    )
    parsed = _parse_feishu_event(_sdk_event(content=leading_code, message_type="post"))
    assert parsed.text == "    first line"


def test_event_parsing_exposes_post_image_keys_as_attachments() -> None:
    content = json.dumps(
        {
            "title": "看图",
            "content": [
                [
                    {"tag": "text", "text": "截图如下：", "style": []},
                    {"tag": "img", "image_key": "img_post_1"},
                    {"tag": "text", "text": "请解释", "style": []},
                ]
            ],
        },
        ensure_ascii=False,
    )

    parsed = _parse_feishu_event(_sdk_event(content=content, message_type="post"))

    assert parsed.text == "看图\n\n截图如下：[图片]请解释"
    assert parsed.image_keys == ("img_post_1",)
    assert parsed.content_parts == (
        FeishuContentPart(kind="text", text="看图\n\n截图如下："),
        FeishuContentPart(kind="image", image_key="img_post_1"),
        FeishuContentPart(kind="text", text="请解释"),
    )


def test_event_parsing_exposes_standalone_image_key() -> None:
    parsed = _parse_feishu_event(
        _sdk_event(
            content='{"image_key":"img_standalone_1"}',
            message_type="image",
        )
    )

    assert parsed.text == ""
    assert parsed.image_keys == ("img_standalone_1",)
    assert parsed.content_parts == (
        FeishuContentPart(kind="image", image_key="img_standalone_1"),
    )


def test_send_message_uploads_data_url_images_before_creating_post() -> None:
    client, rest = _client_with_response(_response())
    upload_response = _response()
    upload_response.data.image_key = "img_uploaded_1"
    rest.im.v1.image.create.return_value = upload_response
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nimage-bytes").decode("ascii")

    client.send_message(
        receive_id="oc_group",
        text=f"结果如下：\n\n![结果图](data:image/png;base64,{png})",
    )

    upload_request = rest.im.v1.image.create.call_args.args[0]
    assert upload_request.request_body.image_type == "message"
    request = rest.im.v1.message.create.call_args.args[0]
    content = json.loads(request.request_body.content)
    assert content["zh_cn"]["content"][0][0]["text"] == (
        "结果如下：\n\n![结果图](img_uploaded_1)"
    )


def test_send_message_skips_markdown_image_examples_and_reuses_upload() -> None:
    client, rest = _client_with_response(_response())
    upload_response = _response()
    upload_response.data.image_key = "img_uploaded_1"
    rest.im.v1.image.create.return_value = upload_response
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nimage-bytes").decode("ascii")
    source = f"data:image/png;base64,{png}"
    text = (
        f"`![inline]({source})`\n"
        f"```md\n![fenced]({source})\n```\n"
        f"\\![escaped]({source})\n"
        f"![first]({source}) ![second]({source})"
    )

    client.send_message(receive_id="oc_group", text=text)

    rest.im.v1.image.create.assert_called_once()
    request = rest.im.v1.message.create.call_args.args[0]
    rendered = json.loads(request.request_body.content)["zh_cn"]["content"][0][0][
        "text"
    ]
    assert f"`![inline]({source})`" in rendered
    assert f"![fenced]({source})" in rendered
    assert f"\\![escaped]({source})" in rendered
    assert "![first](img_uploaded_1) ![second](img_uploaded_1)" in rendered


def _provider_client(monkeypatch, response):
    import httpx

    client = FeishuClient(app_id="cli_a", app_secret="secret")
    client._rest_client = MagicMock()

    def authorize(config, request, option):
        option.tenant_access_token = "provider-token"

    monkeypatch.setattr("personal_assistant.channels.feishu.client.verify", authorize)
    requests = []

    def handle(request):
        requests.append(request)
        return response

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handle)),
    )
    return client, requests


def test_download_message_image_reads_only_provider_resource(monkeypatch):
    import httpx

    data = b"\x89PNG\r\n\x1a\nimage"
    client, requests = _provider_client(
        monkeypatch,
        httpx.Response(200, content=data, headers={"Content-Type": "image/png"}),
    )
    image = client.download_message_image(message_id="message-1", image_key="img_1")
    assert image.data == data
    assert image.content_type == "image/png"
    assert (
        str(requests[0].url)
        == "https://open.feishu.cn/open-apis/im/v1/messages/message-1/resources/img_1?type=image"
    )
    assert requests[0].headers["Authorization"] == "Bearer provider-token"


@pytest.mark.parametrize(
    "headers,content",
    [
        (
            {"Content-Type": "image/png", "Content-Length": str(5 * 1024 * 1024 + 1)},
            b"",
        ),
        ({"Content-Type": "image/png"}, b"x" * (5 * 1024 * 1024 + 1)),
    ],
)
def test_download_message_image_rejects_oversize_before_projection(
    monkeypatch, headers, content
):
    import httpx

    client, _ = _provider_client(
        monkeypatch, httpx.Response(200, headers=headers, content=content)
    )
    with pytest.raises(FeishuImageTooLargeError):
        client.download_message_image(message_id="message-1", image_key="img_1")


@pytest.mark.parametrize(
    "source",
    [
        "https://images.example/a.png",
        "http://127.0.0.1/secret",
        "http://user:pass@localhost/secret",
    ],
)
def test_remote_markdown_images_are_text_links_without_fetch(source):
    client, rest = _client_with_response(_response())
    client.send_message(receive_id="oc_group", text=f"![diagram]({source})")
    rest.im.v1.image.create.assert_not_called()
    request = rest.im.v1.message.create.call_args.args[0]
    rendered = json.loads(request.request_body.content)["zh_cn"]["content"][0][0][
        "text"
    ]
    assert rendered == f"[diagram]({source})"
