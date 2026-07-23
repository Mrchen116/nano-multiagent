"""黑盒 IM client 的 HTTP timeline adapter 回归测试。"""

from __future__ import annotations

import pytest

from ._im_client import IMClient


class _Response:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._body


class _TimelineHTTP:
    def get(self, *_args: object, **_kwargs: object) -> _Response:
        return _Response(
            {
                "items": [
                    {
                        "type": "message",
                        "message": {
                            "id": "user-message",
                            "sender_type": "user",
                            "content": "question",
                        },
                    },
                    {
                        "type": "agent_config_boundary",
                        "id": "boundary-1",
                        "config": {"profile_version": 2},
                    },
                    {
                        "type": "message",
                        "message": {
                            "id": "agent-message",
                            "sender_type": "agent",
                            "content": "SENTINEL",
                        },
                    },
                ]
            }
        )


@pytest.mark.e2e
def test_list_messages_unwraps_message_timeline_items_for_reply_consumers() -> None:
    """普通消息 consumer 不接收 timeline wrapper 或 config boundary。"""
    client = IMClient("http://im.test")
    client.token = "test-token"
    client._http = _TimelineHTTP()  # type: ignore[assignment]

    assert client.list_messages("conversation-1") == [
        {"id": "user-message", "sender_type": "user", "content": "question"},
        {"id": "agent-message", "sender_type": "agent", "content": "SENTINEL"},
    ]
