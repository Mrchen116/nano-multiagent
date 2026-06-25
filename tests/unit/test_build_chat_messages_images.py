"""bugfix-433: build_chat_messages must carry image blocks for current + history turns.

Covers decisions 2 & 4: when the current user turn or a history Message carries an
image part, build_chat_messages emits an LLMMessage whose content is a list of blocks
(text + image). Pure-text turns stay on the content:str path (no drift, 不变量1).
"""

from agent.core.types import Message
from agent.core.agent.prompting import build_chat_messages
from agent.core.agent.state import render_user_content_parts, InputPart


_DATA_URL = "data:image/png;base64,aGVsbG8="


def test_render_user_content_parts_returns_none_without_image() -> None:
    """Text-only parts → None so build_chat_messages keeps the content:str path."""
    parts = (InputPart(type="text", text="just text"),)
    assert render_user_content_parts(parts) is None


def test_render_user_content_parts_emits_blocks_when_image_present() -> None:
    """Text+image parts → canonical block list [{text},{image,image_url:data-url}]."""
    parts = (
        InputPart(type="text", text="what is this"),
        InputPart(type="image", image_url=_DATA_URL, mime_type="image/png"),
    )
    blocks = render_user_content_parts(parts)
    assert blocks == [
        {"type": "text", "text": "what is this"},
        {"type": "image", "image_url": _DATA_URL},
    ]


def test_current_user_with_image_yields_list_content() -> None:
    """Current turn carrying an image → last LLMMessage.content is a block list."""
    user_parts = [
        {"type": "text", "text": "describe"},
        {"type": "image", "image_url": _DATA_URL},
    ]
    msgs = build_chat_messages(
        history_messages=(),
        user_text="describe\n[image:placeholder]",
        user_parts=user_parts,
    )
    last = msgs[-1]
    assert last.role == "user"
    assert isinstance(last.content, list)
    assert {"type": "image", "image_url": _DATA_URL} in last.content


def test_current_user_without_image_keeps_str_content() -> None:
    """No image → content stays a plain string (no drift for pure text)."""
    msgs = build_chat_messages(
        history_messages=(),
        user_text="hello there",
        user_parts=None,
    )
    last = msgs[-1]
    assert last.content == "hello there"
    assert isinstance(last.content, str)


def test_history_message_with_parts_restores_image_block() -> None:
    """A history Message carrying image parts → its LLMMessage.content is a block list.

    This is the cross-turn path: a prior user turn whose image was persisted in
    Message.parts must reappear as an image block on the next turn.
    """
    history = (
        Message(
            message_id="m1",
            role="user",
            content="here is a pic\n[image:placeholder]",
            parts=(
                {"type": "text", "text": "here is a pic"},
                {"type": "image", "image_url": _DATA_URL},
            ),
        ),
    )
    msgs = build_chat_messages(history_messages=history, user_text="what was in it?")
    user_msgs = [m for m in msgs if m.role == "user"]
    history_user = user_msgs[0]
    assert isinstance(history_user.content, list)
    assert {"type": "image", "image_url": _DATA_URL} in history_user.content


def test_history_message_without_parts_keeps_str_content() -> None:
    """Pure-text history Message (parts=None) keeps content:str — no regression."""
    history = (Message(message_id="m1", role="user", content="plain text turn"),)
    msgs = build_chat_messages(history_messages=history, user_text="next")
    history_user = [m for m in msgs if m.role == "user"][0]
    assert history_user.content == "plain text turn"
