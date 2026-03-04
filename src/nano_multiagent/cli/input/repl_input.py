"""Interactive terminal input helpers used by CLI REPL."""

import sys
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Callable, Protocol, Sequence, TextIO

try:
    import termios
    import tty
except ImportError:  # pragma: no cover
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

_KEY_ARROW_UP = "\x1b[A"
_KEY_ARROW_DOWN = "\x1b[B"
_KEY_ARROW_RIGHT = "\x1b[C"
_KEY_ARROW_LEFT = "\x1b[D"
_KEY_ENTER = {"\n", "\r"}
_KEY_BACKSPACE = {"\x7f", "\b"}
_MENU_MARKER_SELECTED = "▶"
_MENU_MARKER_IDLE = " "


@dataclass(slots=True)
class _ActiveRenderState:
    out: TextIO
    prompt: str
    chars: tuple[str, ...]
    cursor: int
    command_items: tuple[str, ...]
    selected_command_index: int | None


_RENDER_LOCK = RLock()
_ACTIVE_RENDER_STATE: _ActiveRenderState | None = None


class ReplInputReader(Protocol):
    """Protocol for pluggable REPL line readers."""

    def read_line(self, prompt: str, history: Sequence[str]) -> str:
        """Read one logical input line for current prompt/history context."""
        ...


def build_repl_input_reader(
    *,
    out: TextIO,
    input_fn: Callable[[str], str] | None,
    repl_input_reader_factory: Callable[[], ReplInputReader] | None,
    command_suggestions: Sequence[str] = (),
) -> Callable[[str, Sequence[str]], str]:
    """Build line-reader adapter for tests, plain input, or editable terminal."""
    if repl_input_reader_factory is not None:
        reader = repl_input_reader_factory()
        return reader.read_line

    if input_fn is not None:
        return lambda prompt, history: input_fn(prompt)

    if supports_editable_terminal_input(sys.stdin):
        return lambda prompt, history: read_interactive_line_from_terminal(
            prompt=prompt,
            history=history,
            out=out,
            command_suggestions=command_suggestions,
        )

    return lambda prompt, history: input(prompt)


def supports_editable_terminal_input(stdin: TextIO) -> bool:
    """Check whether terminal supports raw-mode interactive editing."""
    if termios is None or tty is None:
        return False
    is_tty = getattr(stdin, "isatty", None)
    fileno = getattr(stdin, "fileno", None)
    if not callable(is_tty) or not callable(fileno):
        return False
    try:
        return bool(is_tty())
    except Exception:
        return False


@contextmanager
def _stdin_raw_mode(stdin: TextIO):
    if termios is None or tty is None:
        yield
        return
    file_descriptor = stdin.fileno()
    original_mode = termios.tcgetattr(file_descriptor)
    try:
        tty.setraw(file_descriptor)
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, original_mode)


def _read_terminal_key(stdin: TextIO) -> str | None:
    first = stdin.read(1)
    if first == "":
        return None
    if first != "\x1b":
        return first
    second = stdin.read(1)
    if second == "":
        return first
    if second != "[":
        return f"{first}{second}"
    third = stdin.read(1)
    if third == "":
        return f"{first}{second}"
    return f"{first}{second}{third}"


def read_interactive_line_from_terminal(
    *,
    prompt: str,
    history: Sequence[str],
    out: TextIO,
    command_suggestions: Sequence[str] = (),
) -> str:
    """Read one line from real terminal with raw-key handling."""
    with _stdin_raw_mode(sys.stdin):
        return read_interactive_line(
            prompt=prompt,
            history=history,
            key_reader=lambda: _read_terminal_key(sys.stdin),
            out=out,
            command_suggestions=command_suggestions,
            line_break="\r\n",
        )


def read_interactive_line(
    *,
    prompt: str,
    history: Sequence[str],
    key_reader: Callable[[], str | None],
    out: TextIO,
    command_suggestions: Sequence[str] = (),
    line_break: str = "\n",
) -> str:
    """Read/edit one line with history and slash-command menu support."""
    chars: list[str] = []
    cursor = 0
    history_items = [item for item in history if isinstance(item, str)]
    history_index: int | None = None
    draft_before_history: list[str] = []
    command_items = tuple(item for item in command_suggestions if isinstance(item, str) and item.startswith("/"))
    command_menu_index: int | None = None
    command_menu_index = _sync_command_menu_selection(
        chars=chars,
        cursor=cursor,
        command_items=command_items,
        selected_index=command_menu_index,
    )
    try:
        render_interactive_line(
            out=out,
            prompt=prompt,
            chars=chars,
            cursor=cursor,
            command_items=command_items,
            selected_command_index=command_menu_index,
        )
        while True:
            key = key_reader()
            if key is None:
                raise EOFError()
            if key in _KEY_ENTER:
                if command_menu_index is not None and command_items:
                    selected_command = command_items[command_menu_index]
                    chars = list(selected_command)
                    cursor = len(chars)
                    command_menu_index = _sync_command_menu_selection(
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_index=None,
                    )
                    render_interactive_line(
                        out=out,
                        prompt=prompt,
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_command_index=command_menu_index,
                    )
                    continue
                out.write(line_break)
                return "".join(chars)
            if key == "\x03":
                raise KeyboardInterrupt()
            if key == "\x04":
                if chars:
                    continue
                out.write(line_break)
                raise EOFError()
            if key in _KEY_BACKSPACE:
                if cursor > 0:
                    if history_index is not None:
                        history_index = None
                    del chars[cursor - 1]
                    cursor -= 1
                    command_menu_index = _sync_command_menu_selection(
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_index=command_menu_index,
                    )
                    render_interactive_line(
                        out=out,
                        prompt=prompt,
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_command_index=command_menu_index,
                    )
                continue
            if key == _KEY_ARROW_LEFT:
                if cursor > 0:
                    cursor -= 1
                    command_menu_index = _sync_command_menu_selection(
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_index=command_menu_index,
                    )
                    render_interactive_line(
                        out=out,
                        prompt=prompt,
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_command_index=command_menu_index,
                    )
                continue
            if key == _KEY_ARROW_RIGHT:
                if cursor < len(chars):
                    cursor += 1
                    command_menu_index = _sync_command_menu_selection(
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_index=command_menu_index,
                    )
                    render_interactive_line(
                        out=out,
                        prompt=prompt,
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_command_index=command_menu_index,
                    )
                continue
            if key == _KEY_ARROW_UP:
                if command_menu_index is not None and command_items:
                    command_menu_index = (command_menu_index - 1) % len(command_items)
                    render_interactive_line(
                        out=out,
                        prompt=prompt,
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_command_index=command_menu_index,
                    )
                    continue
                if not history_items:
                    continue
                if history_index is None:
                    draft_before_history = chars.copy()
                    history_index = len(history_items) - 1
                elif history_index > 0:
                    history_index -= 1
                chars = list(history_items[history_index])
                cursor = len(chars)
                command_menu_index = _sync_command_menu_selection(
                    chars=chars,
                    cursor=cursor,
                    command_items=command_items,
                    selected_index=None,
                )
                render_interactive_line(
                    out=out,
                    prompt=prompt,
                    chars=chars,
                    cursor=cursor,
                    command_items=command_items,
                    selected_command_index=command_menu_index,
                )
                continue
            if key == _KEY_ARROW_DOWN:
                if command_menu_index is not None and command_items:
                    command_menu_index = (command_menu_index + 1) % len(command_items)
                    render_interactive_line(
                        out=out,
                        prompt=prompt,
                        chars=chars,
                        cursor=cursor,
                        command_items=command_items,
                        selected_command_index=command_menu_index,
                    )
                    continue
                if history_index is None:
                    continue
                if history_index < len(history_items) - 1:
                    history_index += 1
                    chars = list(history_items[history_index])
                else:
                    history_index = None
                    chars = draft_before_history.copy()
                cursor = len(chars)
                command_menu_index = _sync_command_menu_selection(
                    chars=chars,
                    cursor=cursor,
                    command_items=command_items,
                    selected_index=None,
                )
                render_interactive_line(
                    out=out,
                    prompt=prompt,
                    chars=chars,
                    cursor=cursor,
                    command_items=command_items,
                    selected_command_index=command_menu_index,
                )
                continue
            if len(key) == 1 and key.isprintable():
                if history_index is not None:
                    history_index = None
                chars.insert(cursor, key)
                cursor += 1
                command_menu_index = _sync_command_menu_selection(
                    chars=chars,
                    cursor=cursor,
                    command_items=command_items,
                    selected_index=command_menu_index,
                )
                render_interactive_line(
                    out=out,
                    prompt=prompt,
                    chars=chars,
                    cursor=cursor,
                    command_items=command_items,
                    selected_command_index=command_menu_index,
                )
    finally:
        _clear_active_render_state(out=out)


def render_interactive_line(
    *,
    out: TextIO,
    prompt: str,
    chars: Sequence[str],
    cursor: int,
    command_items: Sequence[str] = (),
    selected_command_index: int | None = None,
) -> None:
    """Render editable line and optional slash-command menu in terminal."""
    with _RENDER_LOCK:
        _set_active_render_state(
            out=out,
            prompt=prompt,
            chars=chars,
            cursor=cursor,
            command_items=command_items,
            selected_command_index=selected_command_index,
        )
        _render_interactive_line_locked(
            out=out,
            prompt=prompt,
            chars=chars,
            cursor=cursor,
            command_items=command_items,
            selected_command_index=selected_command_index,
        )


def emit_external_text(*, out: TextIO, text: str) -> None:
    """Emit one external message block without corrupting interactive prompt layout."""
    with _RENDER_LOCK:
        active = _ACTIVE_RENDER_STATE
        should_restore_prompt = active is not None and active.out is out
        if should_restore_prompt:
            _clear_interactive_line_locked(out=out)

        normalized_text = _normalize_terminal_multiline_text(text)
        if normalized_text:
            # Always force external block to start at column 0. This avoids
            # progressive right-shift when terminal output happens in raw mode.
            out.write("\r")
            out.write(normalized_text)
            if not normalized_text.endswith("\r\n"):
                out.write("\r\n")

        if should_restore_prompt and active is not None:
            _render_interactive_line_locked(
                out=out,
                prompt=active.prompt,
                chars=active.chars,
                cursor=active.cursor,
                command_items=active.command_items,
                selected_command_index=active.selected_command_index,
            )

        flush = getattr(out, "flush", None)
        if callable(flush):
            flush()


def _render_interactive_line_locked(
    *,
    out: TextIO,
    prompt: str,
    chars: Sequence[str],
    cursor: int,
    command_items: Sequence[str] = (),
    selected_command_index: int | None = None,
) -> None:
    line = "".join(chars)
    inline_hint = ""
    if selected_command_index is not None and command_items:
        inline_hint = f"  ({command_items[selected_command_index]})"
    out.write(f"\r{prompt}{line}{inline_hint}\x1b[K")
    out.write("\x1b[J")
    tail_size = len(line) - cursor + len(inline_hint)
    if tail_size > 0:
        out.write(f"\x1b[{tail_size}D")
    flush = getattr(out, "flush", None)
    if callable(flush):
        flush()


def _set_active_render_state(
    *,
    out: TextIO,
    prompt: str,
    chars: Sequence[str],
    cursor: int,
    command_items: Sequence[str],
    selected_command_index: int | None,
) -> None:
    global _ACTIVE_RENDER_STATE
    _ACTIVE_RENDER_STATE = _ActiveRenderState(
        out=out,
        prompt=prompt,
        chars=tuple(chars),
        cursor=cursor,
        command_items=tuple(command_items),
        selected_command_index=selected_command_index,
    )


def _clear_active_render_state(*, out: TextIO) -> None:
    global _ACTIVE_RENDER_STATE
    with _RENDER_LOCK:
        if _ACTIVE_RENDER_STATE is not None and _ACTIVE_RENDER_STATE.out is out:
            _ACTIVE_RENDER_STATE = None


def _clear_interactive_line_locked(*, out: TextIO) -> None:
    out.write("\r\x1b[K")
    out.write("\x1b[J")


def _normalize_terminal_multiline_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n")


def _sync_command_menu_selection(
    *,
    chars: Sequence[str],
    cursor: int,
    command_items: Sequence[str],
    selected_index: int | None,
) -> int | None:
    if not command_items:
        return None
    if cursor != 1 or len(chars) != 1 or chars[0] != "/":
        return None
    if selected_index is None:
        return 0
    if selected_index < 0 or selected_index >= len(command_items):
        return 0
    return selected_index


def _format_command_menu(*, command_items: Sequence[str], selected_index: int) -> str:
    rendered_items: list[str] = []
    for index, command in enumerate(command_items):
        marker = _MENU_MARKER_SELECTED if index == selected_index else _MENU_MARKER_IDLE
        rendered_items.append(f"{marker} {command}")
    return "Commands ↓ " + "  ".join(rendered_items)
