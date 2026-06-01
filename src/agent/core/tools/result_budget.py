"""Tool result budget enforcement: persist oversized results and return preview."""

from pathlib import Path
from typing import Any

DEFAULT_MAX_RESULT_SIZE_CHARS = 50_000
PREVIEW_SIZE_CHARS = 2_000
PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"


class ToolResultCompressor:
    """Compress oversized tool results by persisting to disk and returning a preview.

    - Stateless: each call is independent. No cross-turn state needed.
    - Session-scoped: files saved under ``{base_dir}/{session_id}/{tool_call_id}.txt``.
    - Idempotent: same ``(session_id, tool_call_id)`` writes the same path;
      content is deterministic for a given tool_call_id, so overwrite is safe.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir.expanduser().resolve()

    def maybe_compress(
        self,
        content: str | list[dict[str, Any]],
        *,
        tool_name: str,
        tool_call_id: str,
        session_id: str,
        max_size_chars: int | None,
    ) -> str | list[dict[str, Any]]:
        """Return ``content`` unchanged if under limit, otherwise persist + preview."""
        # None = Infinity (Read tool, or explicit opt-out)
        if max_size_chars is None:
            return content

        # Skip non-text content (images, etc.)
        if isinstance(content, list):
            if any(
                not (isinstance(b, dict) and b.get("type") == "text") for b in content
            ):
                return content
            text_content = "\n".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            text_content = content

        if len(text_content) <= max_size_chars:
            return content

        # Persist atomically
        session_dir = self._base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        filepath = session_dir / f"{tool_call_id}.txt"
        tmp_path = filepath.with_suffix(".tmp")
        tmp_path.write_text(text_content, encoding="utf-8")
        tmp_path.replace(filepath)

        # Build preview message
        preview = _generate_preview(text_content, PREVIEW_SIZE_CHARS)
        has_more = len(text_content) > PREVIEW_SIZE_CHARS
        preview_msg = (
            f"{PERSISTED_OUTPUT_TAG}\n"
            f"Output too large ({len(text_content)} chars > {max_size_chars} limit). "
            f"Full output saved to: {filepath}\n\n"
            f"Preview (first {PREVIEW_SIZE_CHARS} chars):\n"
            f"{preview}\n"
            f"{'...' if has_more else ''}\n"
            f"{PERSISTED_OUTPUT_CLOSING_TAG}"
        )
        return preview_msg


def _generate_preview(text: str, max_chars: int) -> str:
    """Return first ``max_chars`` of text, cutting at newline when possible."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    cut = last_newline if last_newline > max_chars * 0.5 else max_chars
    return text[:cut]
