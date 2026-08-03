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


def test_repl_input_persistent_output_does_not_clear_prior_completed_blocks() -> None:
    output = io.StringIO()

    repl_input.emit_persistent_text(out=output, text="Assistant:\nfirst turn")
    repl_input.emit_persistent_text(out=output, text="Assistant:\nsecond turn")

    text = output.getvalue()
    assert "Assistant:\r\nfirst turn\r\n" in text
    assert "Assistant:\r\nsecond turn\r\n" in text
    assert "\x1b[A\x1b[2K" not in text


def test_repl_input_engine_supports_cjk_cursor_movement_for_visible_characters() -> (
    None
):
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


def test_repl_input_render_uses_display_width_for_cjk_inline_hint_cursor_position() -> (
    None
):
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
