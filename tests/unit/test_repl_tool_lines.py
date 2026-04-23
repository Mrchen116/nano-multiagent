import pytest

from coding_cli.render.repl_tool_lines import format_tool_done, format_tool_running


def test_format_tool_running() -> None:
    assert format_tool_running("bash") == "▸ Tool: bash"
    assert format_tool_running("read") == "▸ Tool: read"


def test_format_tool_done_with_int_duration() -> None:
    assert format_tool_done("bash", 120) == "✓ Tool: bash (elapsed=120ms)"


def test_format_tool_done_with_float_duration() -> None:
    assert format_tool_done("bash", 120.7) == "✓ Tool: bash (elapsed=120ms)"


def test_format_tool_done_without_duration() -> None:
    assert format_tool_done("bash", None) == "✓ Tool: bash"
    assert format_tool_done("bash", -1) == "✓ Tool: bash"
    assert format_tool_done("bash", "invalid") == "✓ Tool: bash"
