import pytest

from nano_multiagent.agent.state import parse_input_parts, render_user_text


def test_parse_input_parts_supports_text_and_image() -> None:
    parts = parse_input_parts(
        [
            {"type": "text", "text": "hello"},
            {"type": "image", "image_url": "https://example.com/demo.png"},
        ]
    )

    assert len(parts) == 2
    assert parts[0].type == "text"
    assert parts[0].text == "hello"
    assert parts[1].type == "image"
    assert parts[1].image_url == "https://example.com/demo.png"


def test_render_user_text_uses_image_placeholder() -> None:
    parts = parse_input_parts(
        [
            {"type": "text", "text": "describe this"},
            {"type": "image", "image_url": "https://example.com/pic.png"},
        ]
    )

    rendered = render_user_text(parts)

    assert rendered == "describe this\n[image:placeholder]"


def test_parse_input_parts_rejects_non_text_non_image() -> None:
    with pytest.raises(ValueError, match="unsupported part type"):
        parse_input_parts([{"type": "audio", "audio_url": "x"}])
