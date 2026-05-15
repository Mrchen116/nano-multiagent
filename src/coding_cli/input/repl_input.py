"""Interactive terminal input helpers used by CLI REPL."""

import codecs
import os
import select
import sys
import unicodedata
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
_KEEP_STATE = object()
_KEY_IDLE = object()


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
_LAST_EXTERNAL_TEXT_LINES: int = 0


@dataclass(frozen=True, slots=True)
class _InputState:
    chars: tuple[str, ...]
    cursor: int
    history_items: tuple[str, ...]
    history_index: int | None
    draft_before_history: tuple[str, ...]
    command_items: tuple[str, ...]
    command_menu_index: int | None


@dataclass(frozen=True, slots=True)
class _InputStep:
    state: _InputState
    needs_redraw: bool
    final_line: str | None = None
    write_line_break: bool = False
    raises_eof: bool = False
    raises_keyboard_interrupt: bool = False


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
    on_idle: Callable[[], None] | None = None,
    idle_interval_seconds: float = 0.5,
) -> Callable[..., str]:
    """Build line-reader adapter for tests, plain input, or editable terminal."""
    if repl_input_reader_factory is not None:
        reader = repl_input_reader_factory()
        return reader.read_line

    if input_fn is not None:
        return lambda prompt, history, **kwargs: input_fn(prompt)

    if supports_editable_terminal_input(sys.stdin):
        return lambda prompt, history, **kwargs: read_interactive_line_from_terminal(
            prompt=prompt,
            history=history,
            out=out,
            command_suggestions=command_suggestions,
            on_idle=on_idle,
            idle_interval_seconds=idle_interval_seconds,
        )

    return lambda prompt, history, **kwargs: input(prompt)


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
        # Re-enable OPOST+ONLCR so that \n written by print() / Console.line()
        # still maps to \r\n on output.  Without this, raw-mode disables
        # OPOST and every \n becomes a bare LF, leaving the cursor in the
        # middle of the next line and producing progressive indentation.
        mode = termios.tcgetattr(file_descriptor)
        # termios attr list: [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
        mode[1] = mode[1] | termios.OPOST | termios.ONLCR
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, mode)
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, original_mode)


def _read_terminal_key(stdin: TextIO) -> str | None:
    first = stdin.read(1)
    if first == "":
        return None
    if first in {"\n", "\r"}:
        return first
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


def _build_key_reader(
    stdin: TextIO,
    *,
    on_idle: Callable[[], None] | None,
    idle_interval_seconds: float,
) -> Callable[[], str | None]:
    """Build a key reader that returns _KEY_IDLE when no input arrives within the interval."""
    if on_idle is not None:
        return _IdleFdKeyReader(stdin=stdin, idle_interval_seconds=idle_interval_seconds).read_key

    def _read_key() -> str | None:
        return _read_terminal_key(stdin)

    return _read_key


class _IdleFdKeyReader:
    """Read raw terminal bytes without losing IME text buffered above the fd."""

    def __init__(self, *, stdin: TextIO, idle_interval_seconds: float) -> None:
        self._stdin = stdin
        self._idle_interval_seconds = idle_interval_seconds
        encoding = getattr(stdin, "encoding", None) or sys.getdefaultencoding() or "utf-8"
        self._decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        self._tokens: list[str] = []
        self._pending_escape = ""

    def read_key(self) -> str | None:
        """Return one decoded key token, or _KEY_IDLE when the fd is quiet."""
        if self._tokens:
            return self._tokens.pop(0)

        fd = self._stdin.fileno()
        ready, _, _ = select.select([fd], [], [], self._idle_interval_seconds)
        if not ready:
            return _KEY_IDLE  # type: ignore[return-value]

        data = os.read(fd, 4096)
        if data == b"":
            return None
        self._extend_tokens(self._decoder.decode(data, final=False))
        if self._tokens:
            return self._tokens.pop(0)
        return _KEY_IDLE  # type: ignore[return-value]

    def _extend_tokens(self, text: str) -> None:
        pending = f"{self._pending_escape}{text}"
        self._pending_escape = ""
        index = 0
        while index < len(pending):
            char = pending[index]
            if char != "\x1b":
                self._tokens.append(char)
                index += 1
                continue

            remaining = pending[index:]
            if len(remaining) < 2:
                self._pending_escape = remaining
                break
            if remaining[1] != "[":
                self._tokens.append(remaining[:2])
                index += 2
                continue
            if len(remaining) < 3:
                self._pending_escape = remaining
                break
            self._tokens.append(remaining[:3])
            index += 3


def _split_pasted_key(key: str) -> tuple[str, ...]:
    if len(key) <= 1:
        return (key,)
    if "\n" not in key and "\r" not in key:
        return (key,)
    normalized = key.replace("\r\n", "\n").replace("\r", "\n")
    return tuple(normalized)


def _is_pasted_newline_token(key: str) -> bool:
    return len(key) > 1 and ("\n" in key or "\r" in key)


def _apply_pasted_text(*, state: _InputState, key: str) -> _InputStep:
    next_chars = list(state.chars)
    insert_at = state.cursor
    for token in _split_pasted_key(key):
        next_chars.insert(insert_at, token)
        insert_at += 1
    return _InputStep(
        state=_next_input_state(
            state,
            chars=tuple(next_chars),
            cursor=insert_at,
            history_index=None if state.history_index is not None else _KEEP_STATE,
            command_menu_index_seed=None,
        ),
        needs_redraw=True,
    )


def _normalize_submitted_text(chars: Sequence[str]) -> str:
    return "".join(chars).rstrip("\n")


def read_interactive_line_from_terminal(
    *,
    prompt: str,
    history: Sequence[str],
    out: TextIO,
    command_suggestions: Sequence[str] = (),
    on_idle: Callable[[], None] | None = None,
    idle_interval_seconds: float = 0.5,
) -> str:
    """Read one line from real terminal with raw-key handling."""
    with _stdin_raw_mode(sys.stdin):
        key_reader = _build_key_reader(sys.stdin, on_idle=on_idle, idle_interval_seconds=idle_interval_seconds)
        return read_interactive_line(
            prompt=prompt,
            history=history,
            key_reader=key_reader,
            out=out,
            command_suggestions=command_suggestions,
            line_break="\r\n",
            on_idle=on_idle,
        )


def read_interactive_line(
    *,
    prompt: str,
    history: Sequence[str],
    key_reader: Callable[[], str | None],
    out: TextIO,
    command_suggestions: Sequence[str] = (),
    line_break: str = "\n",
    on_idle: Callable[[], None] | None = None,
) -> str:
    """Read/edit one logical input, keeping multiline paste as one submission.

    Args:
        prompt: Prompt prefix rendered for the active REPL session.
        history: Per-session history candidates available to arrow navigation.
        key_reader: Raw key supplier that returns one decoded terminal token at a time.
            When *on_idle* is active, the key_reader may return _KEY_IDLE to signal
            no key was pressed within the idle interval.
        out: Terminal-like stream used for redraws.
        command_suggestions: Slash commands shown in the inline suggestion menu.
        line_break: Physical line break written when the logical input is submitted.
        on_idle: Optional callback invoked when no key arrives within the idle interval.

    Returns:
        One logical user submission. When terminal paste injects embedded newlines,
        they are preserved inside the returned string instead of being split into
        multiple submissions.
    """
    state = _initial_input_state(history=history, command_items=command_suggestions)
    pending_paste_submit = False
    try:
        render_interactive_line(
            out=out,
            prompt=prompt,
            chars=state.chars,
            cursor=state.cursor,
            command_items=state.command_items,
            selected_command_index=state.command_menu_index,
        )
        while True:
            key = key_reader()
            if key is _KEY_IDLE:
                if on_idle is not None:
                    on_idle()
                continue
            if key is None:
                if pending_paste_submit:
                    out.write(line_break)
                    return _normalize_submitted_text(state.chars)
                raise EOFError()
            if pending_paste_submit and key in _KEY_ENTER:
                out.write(line_break)
                return _normalize_submitted_text(state.chars)
            pending_paste_submit = False
            if _is_pasted_newline_token(key):
                step = _apply_pasted_text(state=state, key=key)
                pending_paste_submit = True
            else:
                step = _apply_input_key(state=state, key=key)
            state = step.state
            if step.raises_keyboard_interrupt:
                raise KeyboardInterrupt()
            if step.raises_eof:
                if step.write_line_break:
                    out.write(line_break)
                raise EOFError()
            if step.final_line is not None:
                out.write(line_break)
                return step.final_line
            if step.needs_redraw:
                render_interactive_line(
                    out=out,
                    prompt=prompt,
                    chars=state.chars,
                    cursor=state.cursor,
                    command_items=state.command_items,
                    selected_command_index=state.command_menu_index,
                )

    finally:
        _clear_active_render_state(out=out)


def _initial_input_state(*, history: Sequence[str], command_items: Sequence[str]) -> _InputState:
    state = _InputState(
        chars=(),
        cursor=0,
        history_items=tuple(item for item in history if isinstance(item, str)),
        history_index=None,
        draft_before_history=(),
        command_items=tuple(item for item in command_items if isinstance(item, str) and item.startswith("/")),
        command_menu_index=None,
    )
    return _next_input_state(state)


def _apply_input_key(*, state: _InputState, key: str) -> _InputStep:
    if key in _KEY_ENTER:
        if state.command_menu_index is not None and state.command_items:
            selected = state.command_items[state.command_menu_index]
            return _InputStep(
                state=_next_input_state(
                    state,
                    chars=tuple(selected),
                    cursor=len(selected),
                    command_menu_index_seed=None,
                ),
                needs_redraw=True,
            )
        if state.chars:
            next_chars = list(state.chars)
            next_chars.insert(state.cursor, "\n")
            return _InputStep(
                state=_next_input_state(
                    state,
                    chars=tuple(next_chars),
                    cursor=state.cursor + 1,
                    history_index=None if state.history_index is not None else _KEEP_STATE,
                    command_menu_index_seed=None,
                ),
                needs_redraw=True,
                final_line="".join(state.chars),
            )
        return _InputStep(state=state, needs_redraw=False, final_line="")
    if key == "\x03":
        return _InputStep(state=state, needs_redraw=False, raises_keyboard_interrupt=True)
    if key == "\x04":
        if state.chars:
            return _InputStep(state=state, needs_redraw=False)
        return _InputStep(
            state=state,
            needs_redraw=False,
            write_line_break=True,
            raises_eof=True,
        )
    if key in _KEY_BACKSPACE:
        if state.cursor == 0:
            return _InputStep(state=state, needs_redraw=False)
        next_chars = list(state.chars)
        del next_chars[state.cursor - 1]
        return _InputStep(
            state=_next_input_state(
                state,
                chars=tuple(next_chars),
                cursor=state.cursor - 1,
                history_index=None if state.history_index is not None else _KEEP_STATE,
            ),
            needs_redraw=True,
        )
    if key == _KEY_ARROW_LEFT:
        if state.cursor == 0:
            return _InputStep(state=state, needs_redraw=False)
        return _InputStep(
            state=_next_input_state(state, cursor=state.cursor - 1),
            needs_redraw=True,
        )
    if key == _KEY_ARROW_RIGHT:
        if state.cursor >= len(state.chars):
            return _InputStep(state=state, needs_redraw=False)
        return _InputStep(
            state=_next_input_state(state, cursor=state.cursor + 1),
            needs_redraw=True,
        )
    if key == _KEY_ARROW_UP:
        if state.command_menu_index is not None and state.command_items:
            next_state = _next_input_state(
                state,
                command_menu_index_seed=(state.command_menu_index - 1) % len(state.command_items),
            )
            return _InputStep(
                state=next_state,
                needs_redraw=next_state != state,
            )
        if not state.history_items:
            return _InputStep(state=state, needs_redraw=False)
        next_history_index = state.history_index
        next_draft = state.draft_before_history
        if state.history_index is None:
            next_draft = state.chars
            next_history_index = len(state.history_items) - 1
        elif state.history_index > 0:
            next_history_index = state.history_index - 1
        assert next_history_index is not None
        history_chars = tuple(state.history_items[next_history_index])
        next_state = _next_input_state(
            state,
            chars=history_chars,
            cursor=len(history_chars),
            history_index=next_history_index,
            draft_before_history=next_draft,
            command_menu_index_seed=None,
        )
        return _InputStep(state=next_state, needs_redraw=next_state != state)
    if key == _KEY_ARROW_DOWN:
        if state.command_menu_index is not None and state.command_items:
            next_state = _next_input_state(
                state,
                command_menu_index_seed=(state.command_menu_index + 1) % len(state.command_items),
            )
            return _InputStep(
                state=next_state,
                needs_redraw=next_state != state,
            )
        if state.history_index is None:
            return _InputStep(state=state, needs_redraw=False)
        if state.history_index < len(state.history_items) - 1:
            next_history_index = state.history_index + 1
            next_chars = tuple(state.history_items[next_history_index])
            next_state = _next_input_state(
                state,
                chars=next_chars,
                cursor=len(next_chars),
                history_index=next_history_index,
                command_menu_index_seed=None,
            )
            return _InputStep(state=next_state, needs_redraw=next_state != state)
        next_state = _next_input_state(
            state,
            chars=state.draft_before_history,
            cursor=len(state.draft_before_history),
            history_index=None,
            command_menu_index_seed=None,
        )
        return _InputStep(state=next_state, needs_redraw=next_state != state)
    if len(key) == 1 and key.isprintable():
        next_chars = list(state.chars)
        next_chars.insert(state.cursor, key)
        return _InputStep(
            state=_next_input_state(
                state,
                chars=tuple(next_chars),
                cursor=state.cursor + 1,
                history_index=None if state.history_index is not None else _KEEP_STATE,
            ),
            needs_redraw=True,
        )
    return _InputStep(state=state, needs_redraw=False)


def _next_input_state(
    state: _InputState,
    *,
    chars: tuple[str, ...] | object = _KEEP_STATE,
    cursor: int | object = _KEEP_STATE,
    history_index: int | None | object = _KEEP_STATE,
    draft_before_history: tuple[str, ...] | object = _KEEP_STATE,
    command_menu_index_seed: int | None | object = _KEEP_STATE,
) -> _InputState:
    next_chars = state.chars if chars is _KEEP_STATE else chars
    next_cursor = state.cursor if cursor is _KEEP_STATE else cursor
    next_history_index = state.history_index if history_index is _KEEP_STATE else history_index
    next_draft = state.draft_before_history if draft_before_history is _KEEP_STATE else draft_before_history
    next_command_seed = state.command_menu_index if command_menu_index_seed is _KEEP_STATE else command_menu_index_seed
    return _InputState(
        chars=next_chars,
        cursor=next_cursor,
        history_items=state.history_items,
        history_index=next_history_index,
        draft_before_history=next_draft,
        command_items=state.command_items,
        command_menu_index=_sync_command_menu_selection(
            chars=next_chars,
            cursor=next_cursor,
            command_items=state.command_items,
            selected_index=next_command_seed,
        ),
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


def _emit_terminal_text_block(*, out: TextIO, text: str, replace_previous: bool) -> None:
    """Emit one terminal message block without corrupting interactive prompt layout."""
    global _LAST_EXTERNAL_TEXT_LINES
    with _RENDER_LOCK:
        active = _ACTIVE_RENDER_STATE
        should_restore_prompt = active is not None and active.out is out
        if should_restore_prompt:
            _clear_interactive_line_locked(out=out)

        # Clear prior multi-line assistant output above the prompt when the
        # caller is updating the current live block rather than appending
        # completed output to terminal history.
        if replace_previous and _LAST_EXTERNAL_TEXT_LINES > 0:
            for _ in range(_LAST_EXTERNAL_TEXT_LINES):
                out.write("\x1b[A\x1b[2K")
            out.write("\r")

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

        _LAST_EXTERNAL_TEXT_LINES = _count_terminal_lines(normalized_text) if replace_previous else 0


def emit_external_text(*, out: TextIO, text: str) -> None:
    """Emit one replaceable external message block."""
    _emit_terminal_text_block(out=out, text=text, replace_previous=True)


def emit_persistent_text(*, out: TextIO, text: str) -> None:
    """Emit one append-only external message block."""
    _emit_terminal_text_block(out=out, text=text, replace_previous=False)


def _count_terminal_lines(text: str) -> int:
    """Return number of terminal rows occupied by text, or 0 if unavailable."""
    if not text:
        return 0
    try:
        width = os.get_terminal_size().columns
    except OSError:
        return 0
    if width <= 0:
        return 0
    lines = text.split("\r\n")
    total = 0
    for line in lines:
        line_width = sum(
            2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
            for ch in line
            if not unicodedata.combining(ch)
        )
        total += max(1, (line_width + width - 1) // width)
    return total


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
    tail_size = _display_width(line[cursor:]) + _display_width(inline_hint)
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


def _display_width(text: str) -> int:
    """Return terminal column width for mixed-width printable text."""
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        if unicodedata.east_asian_width(char) in {"F", "W"}:
            width += 2
            continue
        width += 1
    return width


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


@dataclass(frozen=True)
class PermissionOption:
    """One selectable option in a permission picker."""

    id: str
    label: str
    description: str = ""


def read_permission_choice(
    *,
    header: str,
    options: Sequence[PermissionOption],
    out: TextIO | None = None,
) -> str:
    """Render an arrow-key permission picker and return the chosen option id.

    Pauses the live REPL render temporarily (grabs _RENDER_LOCK so in-progress
    redraws complete first), presents the picker, then releases.  Designed to
    be called from the SSE drain loop when a ``permission_request`` event
    arrives — at that point the agent run is already parked, so no new streaming
    output will arrive during the picker interaction.

    Args:
        header: Displayed above the options (tool name + projected input + reason).
        options: Selectable options; must be non-empty.
        out: Output stream; defaults to sys.stdout.

    Returns:
        The ``id`` of the chosen option.

    Raises:
        ValueError: When options is empty.
        KeyboardInterrupt: When the user presses Ctrl+C (propagated to the caller).
    """
    if not options:
        raise ValueError("read_permission_choice: options must be non-empty")

    _out = out or sys.stdout
    selected = 0

    def _render() -> None:
        _out.write(f"\n{header}\n")
        for i, opt in enumerate(options):
            marker = _MENU_MARKER_SELECTED if i == selected else _MENU_MARKER_IDLE
            desc = f"  {opt.description}" if opt.description else ""
            _out.write(f"  {marker} {opt.label}{desc}\n")
        _out.write("  (↑/↓ to move, Enter to select, Ctrl-C to cancel)\n")
        _out.flush()

    def _erase(n_lines: int) -> None:
        """Move cursor up n_lines and erase each line."""
        for _ in range(n_lines):
            _out.write("\x1b[A\x1b[2K")
        _out.flush()

    n_render_lines = len(options) + 3  # header + options + instruction

    if termios is None or not hasattr(_out, "fileno"):
        # Non-TTY fallback: print header + numbered options, read a digit.
        _out.write(f"\n{header}\n")
        for i, opt in enumerate(options, start=1):
            _out.write(f"  {i}. {opt.label}\n")
        _out.write("Enter number: ")
        _out.flush()
        try:
            choice = input().strip()
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx].id
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        return options[0].id

    with _RENDER_LOCK:
        with _stdin_raw_mode(sys.stdin):
            key_reader = _build_key_reader(sys.stdin)
            _render()

            while True:
                key = key_reader()
                if key is None or key is _KEY_IDLE:
                    continue
                if key == _KEY_ARROW_UP:
                    _erase(n_render_lines)
                    selected = max(0, selected - 1)
                    _render()
                elif key == _KEY_ARROW_DOWN:
                    _erase(n_render_lines)
                    selected = min(len(options) - 1, selected + 1)
                    _render()
                elif key in _KEY_ENTER:
                    _erase(n_render_lines)
                    chosen = options[selected]
                    _out.write(f"  Selected: {chosen.label}\n")
                    _out.flush()
                    return chosen.id
                elif key == "\x03":  # Ctrl-C
                    _erase(n_render_lines)
                    raise KeyboardInterrupt
