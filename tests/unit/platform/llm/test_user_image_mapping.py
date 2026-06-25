"""bugfix-433: provider mapper user branch must emit image blocks for content:list.

Decision 3: when a user LLMMessage carries content as a list of canonical blocks
([{type:text}, {type:image, image_url: data-url}]), each mapper's user branch maps
the image block into its provider-native form. Pure str content keeps current shape.
"""

from agent.core.llm.interfaces import LLMMessage
from agent.platform.llm.providers.anthropic.mapper import AnthropicMapper
from agent.platform.llm.providers.openai_compat.mapper import OpenAICompatMapper


_DATA_URL = "data:image/png;base64,aGVsbG8="


def _user_with_image() -> LLMMessage:
    return LLMMessage(
        role="user",
        content=[
            {"type": "text", "text": "what is this"},
            {"type": "image", "image_url": _DATA_URL},
        ],
    )


def test_anthropic_user_branch_maps_image_block_to_base64_source() -> None:
    mapped = AnthropicMapper()._map_message(_user_with_image())
    assert mapped["role"] == "user"
    blocks = mapped["content"]
    text_blocks = [b for b in blocks if b.get("type") == "text"]
    image_blocks = [b for b in blocks if b.get("type") == "image"]
    assert text_blocks and text_blocks[0]["text"] == "what is this"
    assert len(image_blocks) == 1
    source = image_blocks[0]["source"]
    assert source["type"] == "base64"
    assert source["media_type"] == "image/png"
    assert source["data"] == "aGVsbG8="


def test_anthropic_user_branch_str_content_unchanged() -> None:
    mapped = AnthropicMapper()._map_message(LLMMessage(role="user", content="hello"))
    assert mapped["content"] == [{"type": "text", "text": "hello"}]


def test_openai_user_branch_maps_image_block_to_image_url() -> None:
    mapped = OpenAICompatMapper()._map_message(_user_with_image())
    assert mapped["role"] == "user"
    blocks = mapped["content"]
    text_blocks = [b for b in blocks if b.get("type") == "text"]
    image_blocks = [b for b in blocks if b.get("type") == "image_url"]
    assert text_blocks and text_blocks[0]["text"] == "what is this"
    assert len(image_blocks) == 1
    assert image_blocks[0]["image_url"]["url"] == _DATA_URL


def test_openai_user_branch_str_content_unchanged() -> None:
    mapped = OpenAICompatMapper()._map_message(LLMMessage(role="user", content="hi"))
    assert mapped["content"] == "hi"
