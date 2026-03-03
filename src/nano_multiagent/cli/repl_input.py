import sys
from contextlib import contextmanager
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


class ReplInputReader(Protocol):
    def read_line(self, prompt: str, history: Sequence[str]) -> str:
        ...


def build_repl_input_reader(
    *,
    out: TextIO,
    input_fn: Callable[[str], str] | None,
    repl_input_reader_factory: Callable[[], ReplInputReader] | None,
    command_suggestions: Sequence[str] = (),
) -> Callable[[str, Sequence[str]], str]:
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
    with _stdin_raw_mode(sys.stdin):
        return read_interactive_line(
            prompt=prompt,
            history=history,
            key_reader=lambda: _read_terminal_key(sys.stdin),
            out=out,
            command_suggestions=command_suggestions,
        )


def read_interactive_line(
    *,
    prompt: str,
    history: Sequence[str],
    key_reader: Callable[[], str | None],
    out: TextIO,
    command_suggestions: Sequence[str] = (),
) -> str:
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
            print("", file=out)
            return "".join(chars)
        if key == "\x03":
            raise KeyboardInterrupt()
        if key == "\x04":
            if chars:
                continue
            print("", file=out)
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


def render_interactive_line(
    *,
    out: TextIO,
    prompt: str,
    chars: Sequence[str],
    cursor: int,
    command_items: Sequence[str] = (),
    selected_command_index: int | None = None,
) -> None:
    line = "".join(chars)
    out.write(f"\r{prompt}{line}\x1b[K")
    out.write("\x1b[J")
    if selected_command_index is not None and command_items:
        out.write(f"\n{_format_command_menu(command_items=command_items, selected_index=selected_command_index)}\x1b[K")
        out.write("\x1b[1A\r")
        out.write(f"{prompt}{line}")
    tail_size = len(line) - cursor
    if tail_size > 0:
        out.write(f"\x1b[{tail_size}D")
    flush = getattr(out, "flush", None)
    if callable(flush):
        flush()


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
