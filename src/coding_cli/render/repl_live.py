"""Renderers for interactive REPL tool/text streaming."""

import threading
from typing import Callable
from typing import TextIO

from coding_cli.render.repl_tool_lines import format_tool_done
from coding_cli.render.repl_tool_lines import format_tool_running


def _rich_available() -> bool:
    try:
        import rich.live  # noqa: F401
        import rich.spinner  # noqa: F401
        import rich.text  # noqa: F401
        import rich.console  # noqa: F401
    except Exception:
        return False
    return True


class ReplLiveRenderer:
    """Renders one assistant turn with a spinner, streaming text, and tool lines.

    Uses ``rich.live.Live`` to update the terminal in-place. Created per turn
    and used as a context manager.
    """

    def __init__(self, out: TextIO) -> None:
        self._out = out
        self._live: object | None = None
        self._console: object | None = None
        self._assistant_text = ""
        self._tool_lines: dict[str, str] = {}
        self._spinner_active = True
        self._lock = threading.Lock()
        self._last_renderable_str: str | None = None

    def __enter__(self) -> "ReplLiveRenderer":
        if not _rich_available():
            return self
        from rich.console import Console
        from rich.live import Live
        from rich.spinner import Spinner

        self._console = Console(file=self._out, force_terminal=True)
        self._live = Live(
            Spinner("dots", text="Thinking..."),
            console=self._console,
            refresh_per_second=8,
            vertical_overflow="visible",
            auto_refresh=False,
            redirect_stdout=False,
            redirect_stderr=False,
            transient=False,
        )
        self._live.start(refresh=True)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        with self._lock:
            if self._live is not None:
                self._live.stop()
                self._live = None
            self._console = None
        flush = getattr(self._out, "flush", None)
        if callable(flush):
            flush()

    def on_text_delta(self, delta: str) -> None:
        """Merge a text delta and refresh the live view."""
        if not delta:
            return
        from coding_cli.events.repl_events import merge_text_delta

        with self._lock:
            merged = merge_text_delta(self._assistant_text, delta)
            if merged == self._assistant_text:
                return
            self._assistant_text = merged
            self._spinner_active = False
        self._refresh()

    def on_tool_event(self, event_name: str, data: dict[str, object]) -> None:
        """Handle tool lifecycle events and refresh the live view."""
        from coding_cli.render.repl_tool_lines import (
            format_tool_done,
            format_tool_running,
        )

        name = data.get("name")
        call_id = data.get("call_id")
        if not isinstance(call_id, str):
            call_id = data.get("tool_call_id")
        if not isinstance(name, str):
            return
        key = f"{name}::{call_id}" if isinstance(call_id, str) else name
        if event_name == "tool_start":
            new_line = format_tool_running(name)
        elif event_name == "tool_exec_exit":
            duration_ms = data.get("duration_ms")
            new_line = format_tool_done(name, duration_ms)
        else:
            # tool_exec_started / tool_exec_running / tool_exec_chunk are intentionally
            # hidden in the live view to reduce flicker and noise.
            return
        with self._lock:
            if self._tool_lines.get(key) == new_line:
                return
            self._tool_lines[key] = new_line
            self._spinner_active = False
        self._refresh()

    def _refresh(self) -> None:
        with self._lock:
            if self._live is None:
                return
            from rich.spinner import Spinner
            from rich.text import Text

            lines: list[Text] = []

            if self._assistant_text:
                # Split on explicit newlines only; let the Console handle
                # terminal-width wrapping naturally.  Pre-wrapping with
                # Text.wrap() risks a width mismatch between what Rich thinks
                # the terminal is and what it actually is, causing cursor
                # misalignment.
                for raw_line in self._assistant_text.split("\n"):
                    lines.append(Text(f"> {raw_line}"))
            for tool_line in self._tool_lines.values():
                lines.append(Text(tool_line))

            if not lines and self._spinner_active:
                renderable = Spinner("dots", text="Thinking...")
            elif lines:
                renderable = Text("\n").join(lines)
            else:
                renderable = Text("")

            renderable_str = str(renderable)
            if self._last_renderable_str == renderable_str:
                return
            self._last_renderable_str = renderable_str
            self._live.update(renderable, refresh=True)


class ReplBlockRenderer:
    """Compose assistant text and tool state into one TTY block.

    This renderer is intentionally simple and deterministic: each state change
    rebuilds the full visible block and sends it through a caller-provided emit
    callback such as ``repl_input.emit_external_text``. Keeping text and tool
    progress in the same block avoids the text/tool overwrite race that happens
    when each event tries to redraw independently.
    """

    def __init__(self, *, emit: Callable[[str], None]) -> None:
        self._emit = emit
        self._assistant_text = ""
        self._tool_lines: dict[str, str] = {}
        self._last_block: str | None = None
        self._lock = threading.Lock()

    def on_text_delta(self, delta: str) -> None:
        """Merge one possibly cumulative text update and redraw once."""
        if not delta:
            return
        from coding_cli.events.repl_events import merge_text_delta

        with self._lock:
            merged = merge_text_delta(self._assistant_text, delta)
            if merged == self._assistant_text:
                return
            self._assistant_text = merged
        self._refresh()

    def on_tool_event(self, event_name: str, data: dict[str, object]) -> None:
        """Track concise tool lifecycle rows in the shared block."""
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return
        call_id = data.get("call_id")
        if not isinstance(call_id, str):
            call_id = data.get("tool_call_id")
        key = f"{name}::{call_id}" if isinstance(call_id, str) and call_id else name
        if event_name == "tool_start":
            new_line = format_tool_running(name)
        elif event_name == "tool_exec_exit":
            new_line = format_tool_done(name, data.get("duration_ms"))
        else:
            return
        with self._lock:
            if self._tool_lines.get(key) == new_line:
                return
            self._tool_lines[key] = new_line
        self._refresh()

    def _refresh(self) -> None:
        with self._lock:
            lines: list[str] = []
            if self._assistant_text:
                lines.extend(f"> {line}" for line in self._assistant_text.split("\n"))
            lines.extend(self._tool_lines.values())
            block = "\n".join(lines)
            if block == self._last_block:
                return
            self._last_block = block
        self._emit(block)
