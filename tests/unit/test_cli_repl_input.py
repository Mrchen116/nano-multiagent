"""REPL 输入引擎行为测试。

覆盖终端按键处理、光标移动、历史回调、命令菜单、
CJK 显示宽度、粘贴分组和外部输出回显等输入层行为。
"""

import io

from coding_cli.input import repl_commands, repl_input
from coding_cli.main import run_cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_keys(keys: list[str]):
    iterator = iter(keys)

    def _reader() -> str | None:
        try:
            return next(iterator)
        except StopIteration:
            return None

    return _reader


class _ScriptedReplInputReader:
    def __init__(self, scripted_lines: list[list[str]]) -> None:
        self._line_iterator = iter(scripted_lines)
        self.render = io.StringIO()

    def read_line(self, prompt: str, history: tuple[str, ...] | list[str]) -> str:
        keys = next(self._line_iterator)
        key_iterator = iter(keys)

        def _read_key() -> str | None:
            try:
                return next(key_iterator)
            except StopIteration:
                return None

        return repl_input.read_interactive_line(
            prompt=prompt,
            history=tuple(history),
            key_reader=_read_key,
            out=self.render,
            command_suggestions=repl_commands.REPL_COMMANDS,
        )


class _TTYStringIO(io.StringIO):
    def isatty(self) -> bool:  # pragma: no cover - simple test seam
        return True


def _simulate_terminal_rows(text: str) -> list[str]:
    """Render enough terminal behavior to catch bare-LF indentation bugs."""
    rows: list[dict[int, str]] = [{}]
    row = 0
    col = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\x1b":
            index += 1
            if index < len(text) and text[index] == "[":
                index += 1
                while index < len(text) and not text[index].isalpha():
                    index += 1
                if index < len(text):
                    index += 1
            continue
        if char == "\r":
            col = 0
            index += 1
            continue
        if char == "\n":
            row += 1
            while len(rows) <= row:
                rows.append({})
            index += 1
            continue
        rows[row][col] = char
        col += 1
        index += 1

    rendered: list[str] = []
    for cells in rows:
        if not cells:
            rendered.append("")
            continue
        max_col = max(cells)
        rendered.append("".join(cells.get(i, " ") for i in range(max_col + 1)).rstrip())
    return rendered


# Minimal stub — only the context-manager protocol is needed for REPL lifecycle.
class _StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def __enter__(self) -> "_StubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def health(self) -> dict[str, object]:
        self.calls.append(("health", None))
        return {"healthy": True}

    def create_session(self, *, title: str | None = None, **kwargs: object) -> dict[str, str]:
        self.calls.append(("create_session", {"title": title or ""}))
        return {"session_id": "sess_cli"}

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        self._last_text = text
        return {"run_id": "run-1", "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        text = getattr(self, "_last_text", "hello repl")
        yield {"event": "assistant_message", "run_id": "run-1", "content": f"echo:{text}"}
        yield {"event": "run_status", "run_id": "run-1", "status": "completed", "stop_reason": "stop", "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        return {"session_id": session_id, "tools": [{"name": "read", "description": "Read", "input_schema": {}}]}

    def compact_session(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("compact_session", {"session_id": session_id}))
        return {"session_id": session_id, "compacted": False, "result": None}

    def get_session_messages(self, *, session_id: str, limit: int = 20) -> dict[str, object]:
        self.calls.append(("get_session_messages", {"session_id": session_id, "limit": limit}))
        return {"session_id": session_id, "messages": []}

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        return {"session_id": session_id, "used_tokens": 64, "max_tokens": 200, "remaining_tokens": 136, "usage_ratio": 0.32}

    def get_llm_config(self) -> dict[str, object]:
        self.calls.append(("get_llm_config", None))
        return {"provider": "openai_compat", "model": "codex_oauth:gpt-5.5", "base_url": "http://127.0.0.1:4000", "api_key_configured": False, "timeout_seconds": 30.0}

    def set_llm_config(self, *, provider=None, model=None, base_url=None, api_key=None, timeout_seconds=None, clear_api_key=False) -> dict[str, object]:
        self.calls.append(("set_llm_config", {"provider": provider, "model": model, "base_url": base_url, "api_key": api_key, "timeout_seconds": timeout_seconds, "clear_api_key": clear_api_key}))
        return {"provider": provider or "openai_compat", "model": model or "codex_oauth:gpt-5.5", "base_url": base_url or "http://127.0.0.1:4000", "api_key_configured": bool(api_key), "timeout_seconds": timeout_seconds or 30.0}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_repl_input_engine_supports_inline_insert_at_cursor() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "helXlo"


def test_repl_input_engine_supports_left_right_with_backspace_editing() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["a", "b", "c", "\x1b[D", "\x7f", "\x1b[C", "!", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "ac!"


def test_repl_input_engine_arrow_up_recalls_and_allows_editing() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("first", "second"),
        key_reader=_iter_keys(["\x1b[A", "\x1b[D", "\x1b[D", "X", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "secoXnd"


def test_repl_input_engine_history_navigation_moves_up_and_down() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("first", "second"),
        key_reader=_iter_keys(["\x1b[A", "\x1b[A", "\x1b[B", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "second"


def test_repl_input_engine_slash_menu_down_enter_fills_selected_command() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[B", "\n", "\n"]),
        out=io.StringIO(),
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/new"


def test_repl_input_engine_slash_menu_up_wraps_without_history_recall() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[A", "\n", "\n"]),
        out=io.StringIO(),
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/exit"


def test_repl_input_engine_slash_menu_does_not_render_multiline_panel() -> None:
    output = io.StringIO()
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[B", "\n", "\n"]),
        out=output,
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/new"
    assert "Commands ↓ " not in output.getvalue()


def test_read_interactive_line_groups_multiline_paste_into_single_submission() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["f", "i", "r", "s", "t", "\nsecond\n"]),
        out=io.StringIO(),
    )

    assert typed == "first\nsecond"


def test_repl_input_external_output_replays_prompt_without_layout_break() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("ping"),
        cursor=4,
    )
    repl_input.emit_external_text(out=output, text="[tool echo] output=ok")

    text = output.getvalue()
    assert "[tool echo] output=ok" in text
    assert "\r[tool echo] output=ok\r\n" in text
    assert text.count("nano> ping") >= 2


def test_repl_input_external_multiline_output_uses_terminal_safe_line_endings() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("ping"),
        cursor=4,
    )
    repl_input.emit_external_text(out=output, text="line-1\nline-2")

    text = output.getvalue()
    assert "line-1\r\nline-2\r\n" in text
    assert text.count("nano> ping") >= 2


def test_repl_input_raw_mode_reenables_output_postprocessing(monkeypatch) -> None:
    class _FakeTermios:
        ONLCR = 0b01
        OPOST = 0b10
        TCSADRAIN = 0

        def __init__(self) -> None:
            self.set_modes: list[list[object]] = []

        def tcgetattr(self, file_descriptor: int) -> list[object]:
            del file_descriptor
            return [0, 0, 0, 0, 0, 0, []]

        def tcsetattr(self, file_descriptor: int, when: int, mode: list[object]) -> None:
            del file_descriptor, when
            self.set_modes.append(list(mode))

    class _FakeTty:
        def setraw(self, file_descriptor: int) -> None:
            del file_descriptor

    class _FakeStdin:
        def fileno(self) -> int:
            return 0

    fake_termios = _FakeTermios()
    monkeypatch.setattr(repl_input, "termios", fake_termios)
    monkeypatch.setattr(repl_input, "tty", _FakeTty())

    with repl_input._stdin_raw_mode(_FakeStdin()):  # noqa: SLF001 - focused terminal-mode regression
        pass

    raw_mode = fake_termios.set_modes[0]
    assert raw_mode[1] == fake_termios.OPOST | fake_termios.ONLCR


def test_repl_input_persistent_output_does_not_clear_prior_completed_blocks(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr(repl_input, "_count_terminal_lines", lambda text: 2 if text else 0)

    repl_input.emit_persistent_text(out=output, text="Assistant:\nfirst turn")
    repl_input.emit_persistent_text(out=output, text="Assistant:\nsecond turn")

    text = output.getvalue()
    assert "Assistant:\r\nfirst turn\r\n" in text
    assert "Assistant:\r\nsecond turn\r\n" in text
    assert "\x1b[A\x1b[2K" not in text


def test_repl_input_engine_supports_cjk_cursor_movement_for_visible_characters() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["你", "好", "世", "界", "\x1b[D", "\x1b[D", "A", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "你好A世界"


def test_repl_input_render_uses_display_width_for_mixed_text_cursor_position() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("你a好"),
        cursor=1,
    )

    text = output.getvalue()
    assert "\x1b[2D" not in text
    assert "\x1b[3D" in text


def test_repl_input_render_uses_display_width_for_cjk_inline_hint_cursor_position() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("你/"),
        cursor=1,
        command_items=repl_commands.REPL_COMMANDS,
        selected_command_index=0,
    )

    text = output.getvalue()
    expected_tail_columns = 1 + len("  (/help)")
    assert f"\x1b[{expected_tail_columns}D" in text


def test_repl_input_engine_supports_crlf_line_break_for_terminal_mode() -> None:
    output = io.StringIO()
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["h", "i", "\n"]),
        out=output,
        line_break="\r\n",
    )

    assert typed == "hi"
    assert output.getvalue().endswith("\r\n")


def test_repl_input_state_machine_reports_needs_redraw_for_noop_and_mutating_keys() -> None:
    from coding_cli.input import repl_input as layered_repl_input

    state = layered_repl_input._initial_input_state(history=(), command_items=repl_commands.REPL_COMMANDS)

    noop = layered_repl_input._apply_input_key(state=state, key="\x1b[D")
    assert noop.needs_redraw is False
    assert noop.state.cursor == 0
    assert noop.state.chars == ()

    inserted = layered_repl_input._apply_input_key(state=noop.state, key="a")
    assert inserted.needs_redraw is True
    assert inserted.state.cursor == 1
    assert inserted.state.chars == ("a",)
    assert inserted.final_line is None


def test_repl_input_engine_skips_redundant_redraw_for_noop_keys(monkeypatch) -> None:
    from coding_cli.input import repl_input as layered_repl_input

    output = io.StringIO()
    render_calls: list[tuple[str, str, int]] = []
    original_render = layered_repl_input.render_interactive_line

    def _counting_render(*, out, prompt, chars, cursor, command_items=(), selected_command_index=None):
        render_calls.append(("render", "".join(chars), cursor))
        return original_render(
            out=out,
            prompt=prompt,
            chars=chars,
            cursor=cursor,
            command_items=command_items,
            selected_command_index=selected_command_index,
        )

    monkeypatch.setattr(layered_repl_input, "render_interactive_line", _counting_render)

    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["\x1b[D", "\x1b[D", "a", "\n"]),
        out=output,
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "a"
    # Initial render + one mutating render.
    assert len(render_calls) == 2


def test_repl_input_state_machine_skips_redraw_when_history_up_hits_top_boundary() -> None:
    from coding_cli.input import repl_input as layered_repl_input

    state = layered_repl_input._initial_input_state(history=("first",), command_items=repl_commands.REPL_COMMANDS)

    first_up = layered_repl_input._apply_input_key(state=state, key="\x1b[A")
    assert first_up.needs_redraw is True
    assert first_up.state.chars == ("f", "i", "r", "s", "t")

    second_up = layered_repl_input._apply_input_key(state=first_up.state, key="\x1b[A")
    assert second_up.needs_redraw is False
    assert second_up.state == first_up.state


def test_run_cli_repl_up_recalls_previous_command_line(tmp_path) -> None:
    from tests.unit._cli_kernel_stubs import _BaseKernelStub, _make_kernel_factory
    stub = _BaseKernelStub()
    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["/", "h", "e", "l", "p", "\n"],
            ["\x1b[A", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        repl_input_reader_factory=lambda: scripted_reader,
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    assert output.getvalue().count("Commands: /help /new /use <session_id>") == 2
