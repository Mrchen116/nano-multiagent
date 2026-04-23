"""Simplified tool-call progress line formatters for live REPL preview."""


def format_tool_running(name: str) -> str:
    """Return the in-progress glyph for a tool."""
    return f"▸ Tool: {name}"


def format_tool_done(name: str, duration_ms: int | float | None) -> str:
    """Return the completion glyph for a tool, optionally with elapsed time."""
    if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
        return f"✓ Tool: {name} (elapsed={int(duration_ms)}ms)"
    return f"✓ Tool: {name}"
