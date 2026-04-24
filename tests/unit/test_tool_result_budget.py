"""Unit tests for ToolResultCompressor."""

import tempfile
from pathlib import Path

import pytest

from agent.core.tools.result_budget import (
    DEFAULT_MAX_RESULT_SIZE_CHARS,
    PERSISTED_OUTPUT_CLOSING_TAG,
    PERSISTED_OUTPUT_TAG,
    PREVIEW_SIZE_CHARS,
    ToolResultCompressor,
    _generate_preview,
)


class TestMaybeCompress:
    def test_under_limit_returns_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            content = "x" * 40_000
            result = comp.maybe_compress(
                content,
                tool_name="bash",
                tool_call_id="call_1",
                session_id="sess_1",
                max_size_chars=50_000,
            )
            assert result is content
            assert not (Path(tmpdir) / "sess_1").exists()

    def test_none_limit_returns_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            content = "x" * 200_000
            result = comp.maybe_compress(
                content,
                tool_name="read",
                tool_call_id="call_1",
                session_id="sess_1",
                max_size_chars=None,
            )
            assert result is content
            assert not (Path(tmpdir) / "sess_1").exists()

    def test_over_limit_persists_and_returns_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            content = "line\n" * 30_000  # ~180K chars
            result = comp.maybe_compress(
                content,
                tool_name="bash",
                tool_call_id="call_2",
                session_id="sess_2",
                max_size_chars=50_000,
            )
            assert isinstance(result, str)
            assert result.startswith(PERSISTED_OUTPUT_TAG)
            assert result.endswith(PERSISTED_OUTPUT_CLOSING_TAG)
            assert "Output too large" in result
            assert "Full output saved to" in result
            assert "Preview" in result

            filepath = Path(tmpdir) / "sess_2" / "call_2.txt"
            assert filepath.exists()
            assert filepath.read_text(encoding="utf-8") == content

    def test_over_limit_with_short_content_no_ellipsis(self) -> None:
        # content 60K > limit 50K, but 60K > preview 2K so ellipsis IS present.
        # To test no-ellipsis, use content that exceeds limit but fits in preview.
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            content = "x" * 2_000  # > 50K? No. Use limit smaller than preview.
            result = comp.maybe_compress(
                content,
                tool_name="bash",
                tool_call_id="call_3",
                session_id="sess_3",
                max_size_chars=1_000,  # 2K > 1K limit, but 2K == preview size
            )
            assert isinstance(result, str)
            assert "..." not in result.split("Preview")[-1]

    def test_over_limit_with_long_content_has_ellipsis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            content = "x" * 200_000
            result = comp.maybe_compress(
                content,
                tool_name="bash",
                tool_call_id="call_4",
                session_id="sess_4",
                max_size_chars=50_000,
            )
            assert isinstance(result, str)
            preview_section = result.split("Preview")[-1]
            assert "..." in preview_section

    def test_list_with_image_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            content = [
                {"type": "text", "text": "hello"},
                {"type": "image", "data": "abc", "mimeType": "image/png"},
            ]
            result = comp.maybe_compress(
                content,
                tool_name="read",
                tool_call_id="call_5",
                session_id="sess_5",
                max_size_chars=1,
            )
            assert result is content

    def test_list_text_only_compressed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            content = [
                {"type": "text", "text": "a" * 30_000},
                {"type": "text", "text": "b" * 30_000},
            ]
            result = comp.maybe_compress(
                content,
                tool_name="web_fetch",
                tool_call_id="call_6",
                session_id="sess_6",
                max_size_chars=50_000,
            )
            assert isinstance(result, str)
            assert result.startswith(PERSISTED_OUTPUT_TAG)
            filepath = Path(tmpdir) / "sess_6" / "call_6.txt"
            assert filepath.exists()
            assert filepath.read_text(encoding="utf-8") == "a" * 30_000 + "\n" + "b" * 30_000

    def test_empty_string_no_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            result = comp.maybe_compress(
                "",
                tool_name="bash",
                tool_call_id="call_7",
                session_id="sess_7",
                max_size_chars=50_000,
            )
            assert result == ""

    def test_session_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            comp = ToolResultCompressor(base_dir=Path(tmpdir))
            comp.maybe_compress(
                "a" * 60_000,
                tool_name="bash",
                tool_call_id="call_a",
                session_id="sess_a",
                max_size_chars=50_000,
            )
            comp.maybe_compress(
                "b" * 60_000,
                tool_name="bash",
                tool_call_id="call_b",
                session_id="sess_b",
                max_size_chars=50_000,
            )
            assert (Path(tmpdir) / "sess_a" / "call_a.txt").read_text() == "a" * 60_000
            assert (Path(tmpdir) / "sess_b" / "call_b.txt").read_text() == "b" * 60_000


class TestGeneratePreview:
    def test_short_text_returns_full(self) -> None:
        assert _generate_preview("hello world", 100) == "hello world"

    def test_long_text_hard_cut(self) -> None:
        text = "a" * 3_000
        preview = _generate_preview(text, 2_000)
        assert preview == "a" * 2_000

    def test_long_text_cut_at_newline(self) -> None:
        # 500 * 5 = 2500 chars, newlines at indices 4, 9, 14, ...
        # truncated[:2000] ends at index 1999 which is a newline.
        # last_newline = 1999 > 1000 (0.5 * 2000), so cut = 1999.
        text = "line\n" * 500
        preview = _generate_preview(text, 2_000)
        # Cut at newline means preview ends just before the newline at index 1999
        assert len(preview) == 1_999
        assert not preview.endswith("\n")
        assert preview.endswith("line")

    def test_newline_too_early_uses_hard_limit(self) -> None:
        # newline only at position 100 (< 0.5 * 2000 = 1000), should hard cut
        text = "early" + "\n" + "x" * 5_000
        preview = _generate_preview(text, 2_000)
        assert preview == text[:2_000]

    def test_no_newline_hard_cut(self) -> None:
        text = "x" * 5_000
        assert _generate_preview(text, 2_000) == "x" * 2_000


class TestConstants:
    def test_default_limit(self) -> None:
        assert DEFAULT_MAX_RESULT_SIZE_CHARS == 50_000

    def test_preview_size(self) -> None:
        assert PREVIEW_SIZE_CHARS == 2_000
