"""Terminal-safe line output helpers for the interactive REPL."""

from __future__ import annotations

from typing import Sequence, TextIO


def write_tty_line(out: TextIO, text: str = "") -> None:
    """Write one terminal line with an explicit carriage return."""
    out.write(f"\r{text}\r\n")
    flush = getattr(out, "flush", None)
    if callable(flush):
        flush()


def emit_lines(out: TextIO, lines: Sequence[str], *, is_tty: bool) -> None:
    """Emit display lines with terminal-safe endings when writing to a TTY."""
    if is_tty:
        for line in lines:
            write_tty_line(out, line)
        return
    for line in lines:
        print(line, file=out)
    flush = getattr(out, "flush", None)
    if callable(flush):
        flush()
