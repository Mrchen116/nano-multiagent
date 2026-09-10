"""Hide inline image destinations until the completed reply can be projected."""

from __future__ import annotations

import re
from collections.abc import Callable


_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(\s*(?:<([^>\n]+)>|([^\s)]+))\s*\)")
_INCOMPLETE_IMAGE = "（图片未能展示：图片引用不完整）"


class ReplyImageStream:
    """Project safe append-only Markdown deltas for a single reply bubble.

    Code examples remain literal. Inline image destinations are buffered until
    closed and replaced with a display-only ordinal, never exposed to Web IM.
    """

    def __init__(self, replace: Callable[[re.Match[str]], str] | None = None) -> None:
        """Use a supplied completed-image projection or the default pending projection."""
        self._buffer = ""
        self._delimiter = ""
        self._line_start = True
        self._ordinals: dict[str, int] = {}
        self._replace = replace or self._pending

    def _pending(self, match: re.Match[str]) -> str:
        source = match.group(2) or match.group(3)
        ordinal = self._ordinals.setdefault(source, len(self._ordinals))
        return f"![{match.group(1)}](nano-image-pending:{ordinal})"

    def feed(self, delta: str) -> str:
        """Append a model delta and return the newly safe visible text."""
        self._buffer += delta
        return self._drain(final=False)

    def finish(self) -> str:
        """Flush remaining text, replacing an unfinished image with a safe failure."""
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> str:
        output: list[str] = []
        while self._buffer:
            char = self._buffer[0]
            count = 1
            if char in "`~":
                while count < len(self._buffer) and self._buffer[count] == char:
                    count += 1
                if count == len(self._buffer) and not final:
                    break
                token = self._buffer[:count]
                if char == "`" or (count >= 3 and self._line_start):
                    if not self._delimiter:
                        self._delimiter = token
                    elif self._delimiter == token:
                        self._delimiter = ""
            elif not self._delimiter and char == "\\":
                if len(self._buffer) == 1 and not final:
                    break
                count = min(2, len(self._buffer))
            elif not self._delimiter and char == "!":
                if len(self._buffer) == 1 and not final:
                    break
                if self._buffer.startswith("!["):
                    end_label = self._buffer.find("]", 2)
                    if end_label < 0 or end_label + 1 == len(self._buffer):
                        if not final:
                            break
                        output.append(_INCOMPLETE_IMAGE)
                        self._buffer = ""
                        break
                    if self._buffer[end_label + 1] == "(":
                        match = _IMAGE.match(self._buffer)
                        if match is None:
                            end_image = self._buffer.find(")", end_label + 2)
                            if end_image >= 0:
                                output.append(_INCOMPLETE_IMAGE)
                                self._buffer = self._buffer[end_image + 1 :]
                                self._line_start = False
                                continue
                            if not final:
                                break
                            output.append(_INCOMPLETE_IMAGE)
                            self._buffer = ""
                            break
                        output.append(self._replace(match))
                        self._buffer = self._buffer[match.end() :]
                        self._line_start = False
                        continue
            token = self._buffer[:count]
            output.append(token)
            self._line_start = token.endswith("\n")
            self._buffer = self._buffer[count:]
        return "".join(output)


def mask_reply_images(markdown: str) -> str:
    """Return a full-text pending projection using the same streaming syntax rules."""
    stream = ReplyImageStream()
    return stream.feed(markdown) + stream.finish()


def transform_images(markdown: str, replace: Callable[[re.Match[str]], str]) -> str:
    """Project complete images and sanitize truncated ones using the streaming grammar.

    Args:
        markdown: A complete reply body; code and escaped examples remain literal.
        replace: Maps a valid inline image match to its final channel projection.

    Returns:
        Safe Markdown with invalid image destinations replaced by local failures.
    """
    stream = ReplyImageStream(replace)
    return stream.feed(markdown) + stream.finish()
