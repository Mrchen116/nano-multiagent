"""bugfix-433: build_chat_messages must carry image blocks for current + history turns.

Covers decisions 2 & 4: when the current user turn or a history Message carries an
image part, build_chat_messages emits an LLMMessage whose content is a list of blocks
(text + image). Pure-text turns stay on the content:str path (no drift, 不变量1).
"""

from agent.core.types import Message
from agent.core.agent.prompting import build_chat_messages, build_prompt_messages
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


def test_render_user_content_parts_image_without_url_does_not_enter_list_path() -> None:
    """bugfix-433-fix1 #3: an image part with image_url=None must NOT force the list path.

    Before the fix the guard keyed on ``type=="image"`` while block construction required
    ``image_url is not None`` — so a url-less image returned ``[]`` (or a text-only list),
    contradicting the "no usable image → None" contract and silently dropping content.
    """
    parts = (
        InputPart(type="text", text="hi"),
        InputPart(type="image", image_url=None),
    )
    # No usable image → return None so the caller keeps the content:str path.
    assert render_user_content_parts(parts) is None


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


def test_build_prompt_messages_threads_user_parts() -> None:
    """bugfix-433-fix1 #5: the public build_prompt_messages must forward user_parts.

    The loop calls build_chat_messages directly, but build_prompt_messages is the public
    API; without threading user_parts, any caller sending an image through it would
    silently drop the image (content falls back to user_text).
    """
    user_parts = [
        {"type": "text", "text": "describe"},
        {"type": "image", "image_url": _DATA_URL},
    ]
    msgs = build_prompt_messages(
        history_messages=(),
        user_text="describe\n[image:placeholder]",
        user_parts=user_parts,
    )
    last = msgs[-1]
    assert last.role == "user"
    assert isinstance(last.content, list)
    assert {"type": "image", "image_url": _DATA_URL} in last.content


# ---------------------------------------------------------------------------
# bugfix-433-fix2: an image turn that triggered a provider error must not re-send
# its image block on later turns (CC normalizeMessagesForAPI errorToBlockTypes).
# Pure-text turns and pure-text provider errors are untouched.
# ---------------------------------------------------------------------------


def _provider_error(parent_id: str, *, message_id: str = "err-1") -> Message:
    return Message(
        message_id=message_id,
        parent_message_id=parent_id,
        role="assistant",
        content="⚠️ 模型调用失败:anthropic: stream ended without terminal event",
        metadata={"is_provider_error": True},
    )


def test_image_turn_after_provider_error_strips_image_keeps_text() -> None:
    """An image user turn followed by a provider-error → next build strips the image
    block but keeps the text (model sees text-only, not the poison image)."""
    history = (
        Message(
            message_id="u-img",
            role="user",
            content="这是什么图？\n[image:placeholder]",
            parts=(
                {"type": "text", "text": "这是什么图？"},
                {"type": "image", "image_url": _DATA_URL},
            ),
        ),
        _provider_error("u-img"),
    )
    msgs = build_chat_messages(history_messages=history, user_text="只问文字：1+1?")
    user_msgs = [m for m in msgs if m.role == "user"]
    history_user = user_msgs[0]
    # Image block must be gone; text must survive.
    if isinstance(history_user.content, list):
        assert all(
            b.get("type") != "image"
            for b in history_user.content
            if isinstance(b, dict)
        ), "poison image block must be stripped after provider error"
        texts = [b.get("text") for b in history_user.content if isinstance(b, dict)]
        assert "这是什么图？" in texts
    else:
        # str content path is acceptable as long as no data URL leaks
        assert _DATA_URL not in (history_user.content or "")
        assert "这是什么图？" in history_user.content


def test_image_turn_without_error_keeps_image() -> None:
    """No provider error → the image is still replayed (no over-stripping)."""
    history = (
        Message(
            message_id="u-img",
            role="user",
            content="这是什么图？\n[image:placeholder]",
            parts=(
                {"type": "text", "text": "这是什么图？"},
                {"type": "image", "image_url": _DATA_URL},
            ),
        ),
        Message(message_id="a-1", role="assistant", content="这是红色。"),
    )
    msgs = build_chat_messages(history_messages=history, user_text="还有呢？")
    history_user = [m for m in msgs if m.role == "user"][0]
    assert isinstance(history_user.content, list)
    assert {"type": "image", "image_url": _DATA_URL} in history_user.content


def test_pure_text_turn_with_provider_error_unchanged() -> None:
    """A pure-text user turn that errored keeps its text (no image to strip, no change)."""
    history = (
        Message(message_id="u-txt", role="user", content="算个大数"),
        _provider_error("u-txt"),
    )
    msgs = build_chat_messages(history_messages=history, user_text="继续")
    history_user = [m for m in msgs if m.role == "user"][0]
    assert history_user.content == "算个大数"


# ---------------------------------------------------------------------------
# bugfix-433-fix4: defensive guards for the image-strip-on-error walk (cr3-B).
# The image→provider-error path cannot be reproduced live (the local proxy passes
# image blocks to every model without error), so these unit tests are B's primary
# verification — they pin the walk's scoping so it never over-strips a healthy image.
# ---------------------------------------------------------------------------


def _image_user(message_id: str, *, text: str | None = "看图") -> Message:
    parts: list[dict] = []
    content = ""
    if text is not None:
        parts.append({"type": "text", "text": text})
        content = f"{text}\n[image:placeholder]"
    else:
        content = "[image:placeholder]"
    parts.append({"type": "image", "image_url": _DATA_URL})
    return Message(
        message_id=message_id, role="user", content=content, parts=tuple(parts)
    )


def test_successful_image_turn_not_stripped_when_later_turn_errors() -> None:
    """A *successful* image turn must keep its image even if a LATER turn errors.

    Sequence: image_user(success) → assistant → text_user → provider_error.
    The walk back from the error stops at the text_user (a non-image user turn), so the
    earlier successful image turn is NOT marked. Guards core vision from over-stripping.
    """
    history = (
        _image_user("u-img-ok"),
        Message(message_id="a-1", role="assistant", content="这是红色。"),
        Message(message_id="u-txt", role="user", content="再算个大数"),
        _provider_error("u-txt"),
    )
    msgs = build_chat_messages(history_messages=history, user_text="继续")
    img_user = [m for m in msgs if m.role == "user" and isinstance(m.content, list)]
    assert img_user, "successful image turn must still replay as a block list"
    assert {"type": "image", "image_url": _DATA_URL} in img_user[0].content


def test_text_user_turn_between_image_and_error_blocks_the_walk() -> None:
    """A plain-text user turn between the image turn and the error stops the walk.

    Sequence: image_user → text_user → provider_error. The error belongs to the
    text_user turn; the walk must NOT reach back past it to strip the earlier image.
    """
    history = (
        _image_user("u-img"),
        Message(message_id="u-txt", role="user", content="顺便算一下"),
        _provider_error("u-txt"),
    )
    msgs = build_chat_messages(history_messages=history, user_text="继续")
    img_user = [m for m in msgs if m.role == "user" and isinstance(m.content, list)]
    assert img_user, "image turn before an unrelated text-error must keep its image"
    assert {"type": "image", "image_url": _DATA_URL} in img_user[0].content


def test_image_only_turn_strip_fallback_is_nonempty_placeholder() -> None:
    """An image-ONLY turn (no text block) that errored falls back to a non-empty content.

    When the image block is stripped and no text block survives, _history_content must
    fall back to the message's content projection — the non-empty "[image:placeholder]"
    string — never an empty string (which would itself break the API call). Pins the
    cr3-A false-positive ("empty-string poison") as a regression guard.
    """
    history = (
        _image_user(
            "u-img-only", text=None
        ),  # parts = [image] only, content="[image:placeholder]"
        _provider_error("u-img-only"),
    )
    msgs = build_chat_messages(history_messages=history, user_text="继续")
    history_user = [m for m in msgs if m.role == "user"][0]
    # No image block leaks, and the replayed content is non-empty.
    if isinstance(history_user.content, list):
        assert all(
            b.get("type") != "image"
            for b in history_user.content
            if isinstance(b, dict)
        )
        assert history_user.content, (
            "stripped image-only turn must not become empty list"
        )
    else:
        assert history_user.content == "[image:placeholder]"
        assert _DATA_URL not in history_user.content
