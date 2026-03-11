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
                raise ValueError("image part field image_url must be string when provided")
            mime_type = raw_part.get("mime_type")
            if mime_type is not None and not isinstance(mime_type, str):
                raise ValueError("image part field mime_type must be string when provided")
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


def _extract_metadata(raw_part: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        key: value
        for key, value in raw_part.items()
        if key not in {"type", "text", "image_url", "mime_type"}
    }
