"""Input parsing and immutable state objects for one agent turn."""

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from agent.core.types import Message


@dataclass(frozen=True, slots=True)
class InputPart:
    """Represent one normalized user input part (text or image)."""

    type: str
    text: str | None = None
    image_url: str | None = None
    mime_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentState:
    """Represent immutable state consumed by the loop for one turn."""

    session_id: str
    turn_id: str
    turn_count: int
    history_messages: tuple[Message, ...]
    input_parts: tuple[InputPart, ...]
    user_text: str
    user_message_id: str | None = None


def parse_input_parts(parts: Sequence[Mapping[str, Any]]) -> tuple[InputPart, ...]:
    """Validate and normalize raw input parts.

    Args:
        parts: User-provided parts with `type=text|image`.

    Returns:
        Parsed immutable input parts.

    Raises:
        ValueError: If part type or required fields are invalid.
    """

    parsed: list[InputPart] = []
    for raw_part in parts:
        part_type = str(raw_part.get("type", "")).strip()
        if part_type == "text":
            text = raw_part.get("text")
            if not isinstance(text, str):
                raise ValueError("text part requires string field: text")
            parsed.append(
                InputPart(
                    type="text",
                    text=text,
                    metadata=_extract_metadata(raw_part),
                )
            )
            continue

        if part_type == "image":
            image_url = raw_part.get("image_url")
            if image_url is not None and not isinstance(image_url, str):
                raise ValueError(
                    "image part field image_url must be string when provided"
                )
            mime_type = raw_part.get("mime_type")
            if mime_type is not None and not isinstance(mime_type, str):
                raise ValueError(
                    "image part field mime_type must be string when provided"
                )
            parsed.append(
                InputPart(
                    type="image",
                    image_url=image_url,
                    mime_type=mime_type,
                    metadata=_extract_metadata(raw_part),
                )
            )
            continue

        raise ValueError(f"unsupported part type: {part_type or '<empty>'}")
    return tuple(parsed)


def render_user_text(parts: Sequence[InputPart]) -> str:
    """Render input parts into text fallback consumed by prompt builders.

    Args:
        parts: Parsed input parts.

    Returns:
        Joined text representation with image placeholders.
    """

    lines: list[str] = []
    for part in parts:
        if part.type == "text" and part.text is not None:
            lines.append(part.text)
        elif part.type == "image":
            lines.append("[image:placeholder]")
    return "\n".join(lines)


def render_user_content_parts(
    parts: Sequence[InputPart],
) -> list[dict[str, Any]] | None:
    """Render input parts into structured content blocks, or None when no image.

    bugfix-433 决策2: the text-only ``render_user_text`` projection cannot carry an
    image (it produces ``str``).  When any part is an image, the turn must be sent as
    a list of canonical blocks so the image survives to the provider mapper.  Returning
    None for the no-image case keeps pure-text turns on the ``content:str`` path so
    persisted/replayed text sessions stay byte-identical (不变量1).

    The canonical image block is ``{"type":"image","image_url":"data:<mime>;base64,..."}``
    (mapper 据此映射); the data URL is produced upstream at the gateway inbound
    boundary (决策1), so core never holds an unreachable IM HTTP URL.

    Args:
        parts: Parsed input parts for one user turn.

    Returns:
        A list of text/image blocks when at least one image with a usable URL is present;
        otherwise None.
    """

    # bugfix-433-fix1 #3: the trigger condition must match block construction — an image
    # part with no usable image_url contributes no block, so it must NOT force the list
    # path (which would otherwise return a text-only/empty list, violating the
    # "no usable image → None" contract and silently dropping the image).
    if not any(part.type == "image" and part.image_url is not None for part in parts):
        return None
    blocks: list[dict[str, Any]] = []
    for part in parts:
        if part.type == "text" and part.text is not None:
            blocks.append({"type": "text", "text": part.text})
        elif part.type == "image" and part.image_url is not None:
            blocks.append({"type": "image", "image_url": part.image_url})
    return blocks


def _extract_metadata(raw_part: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        key: value
        for key, value in raw_part.items()
        if key not in {"type", "text", "image_url", "mime_type"}
    }
