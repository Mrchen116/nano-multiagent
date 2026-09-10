"""Protect streamed image destinations without rewriting code examples."""

from personal_assistant.gateway.reply_image_stream import (
    ReplyImageStream,
    mask_reply_images,
)


def test_stream_hides_split_destinations_and_keeps_normal_text_immediate() -> None:
    stream = ReplyImageStream()
    assert stream.feed("Here is the screenshot: ") == "Here is the screenshot: "
    assert stream.feed("!") == ""
    assert stream.feed("[screen](</private/exports/my ") == ""
    assert stream.feed("image.png>)\nAfter") == "![screen](nano-image-pending:0)\nAfter"
    assert stream.finish() == ""


def test_source_ordinals_are_stable_for_repeated_references() -> None:
    stream = ReplyImageStream()
    assert stream.feed("![one](a.png) ![two](<b image.png>) ") == (
        "![one](nano-image-pending:0) ![two](nano-image-pending:1) "
    )
    assert stream.feed("![again](<a.png>)") == "![again](nano-image-pending:0)"


def test_every_split_preserves_code_escaped_examples_and_reference_style() -> None:
    text = (
        "Before `![inline](secret.png)` and ``![inline2](secret.png)``\n"
        "```markdown\n![fenced](secret.png)\n```\n"
        "~~~markdown\n![tilde](secret.png)\n~~~\n"
        r"\![escaped](secret.png) [reference][img] ![reference][img]"
        "\n"
        "![real](<real image.png>) after"
    )
    expected = text.replace(
        "![real](<real image.png>)", "![real](nano-image-pending:0)"
    )
    for split in range(len(text) + 1):
        stream = ReplyImageStream()
        result = stream.feed(text[:split]) + stream.feed(text[split:]) + stream.finish()
        assert result == expected
    assert mask_reply_images(text) == expected


def test_character_deltas_never_expose_image_source_and_unclosed_image_finishes_as_failure() -> (
    None
):
    stream = ReplyImageStream()
    emitted = "".join(
        stream.feed(char) for char in "Text ![screen](/private/exports/secret.png"
    )
    assert emitted == "Text "
    final = stream.finish()
    assert "图片未能展示" in final
    assert "/private" not in final
    assert stream.finish() == ""


def test_plain_punctuation_and_incomplete_code_are_not_image_failures() -> None:
    for text in [
        "Done!",
        "backslash \\",
        "unfinished `code",
        "~~text~~",
        "```\n![example](local.png)",
    ]:
        assert mask_reply_images(text) == text


def test_invalid_closed_image_does_not_hold_back_following_prose() -> None:
    stream = ReplyImageStream()
    result = stream.feed("Before ![bad](/private/unquoted space.png) after")
    assert result.startswith("Before ")
    assert result.endswith(" after")
    assert "图片未能展示" in result
    assert "/private" not in result
    assert stream.finish() == ""
