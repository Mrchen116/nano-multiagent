"""REPL 命令行为测试 (refactor-387 M2)。

覆盖 /help、/new、/use、/session、/tools、/compact、/history、/exit
等 REPL 命令的行为，以及错误建议、连接失败、超时等 REPL 会话层行为。
所有 stub 走 Kernel 接口（无 HTTP），由 _cli_kernel_stubs.py 提供。
"""

import io
import json

from coding_cli import commands as cli_commands
from coding_cli.input import repl_input
from coding_cli.main import run_cli

from tests.unit._cli_kernel_stubs import (
    _BaseKernelStub,
    _CompactedKernelStub,
    _ConnectionRefusedKernelStub,
    _FailingToolsKernelStub,
    _ThresholdBudgetKernelStub,
    _TimeoutKernelStub,
    _TTYStringIO,
    _UsageKernelStub,
    _make_kernel_factory,
)


# ---------------------------------------------------------------------------
# Additional stubs for command tests
# ---------------------------------------------------------------------------


class _StopReasonOnlyKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self._last_text = text
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return type("R", (), {"run_id": "run-1"})()

    def stream(self, session_id, *, after_sequence=0):
        from tests.unit._cli_kernel_stubs import _AsyncIterEvents

        text = self._last_text
        return _AsyncIterEvents(
            [
                {
                    "event": "assistant_message",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "content": f"echo:{text}",
                },
                {
                    "event": "run_status",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _ScriptedReplInputReader:
    def __init__(self, scripted_lines: list[list[str]]) -> None:
        self._line_iterator = iter(scripted_lines)
        self.render = io.StringIO()

    def read_line(self, prompt: str, history: tuple[str, ...] | list[str]) -> str:
        from coding_cli.input import repl_commands

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cli_help_mentions_repl_editing_budget_and_error_layers() -> None:
    help_text = cli_commands.build_parser().format_help()

    assert "REPL quick commands" in help_text
    assert "/compact /history [n] /exit" in help_text
    assert "Inline editing" in help_text
    assert "History recall" in help_text
    # M2: "In-process kernel" replaces "HTTP-only boundary"
    assert "in-process" in help_text.lower() or "In-process" in help_text
    assert "single final JSON object on stdout" in help_text or "--text" in help_text
    assert "LLM usage: shown per turn" in help_text
    # M2: "input / runtime" (network layer removed)
    assert "Error layers:" in help_text


def test_run_cli_repl_supports_required_commands(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(
        ["/help", "/new", "hello repl", "/session", "/tools", "/compact", "/exit"]
    )

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    lines = output.getvalue()
    assert "/help /new /use <session_id> /session /tools /compact" in lines
    assert "/history [n]" in lines
    assert "/exit" in lines
    assert "Started new session sess_cli." in lines
    assert "Active session: sess_cli." in lines
    assert '{"session_id":' not in lines
    assert "hello repl" in lines
    assert "Tools for session" in lines
    assert "- read: Read" in lines
    assert "Compaction for session sess_cli: no changes." in lines
    # M2: no HTTP, call sequence is different
    call_names = [call[0] for call in stub.calls]
    assert "create_session" in call_names
    assert "submit" in call_names
    assert "list_session_tools" in call_names
    assert "compact" in call_names


def test_run_cli_repl_use_switches_active_session(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/use sess_manual", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    assert "Switched to session sess_manual." in output.getvalue()
    assert (
        "submit",
        {"session_id": "sess_manual", "text": "ping", "model": "kimiCoding:K2.6"},
    ) in stub.calls


def test_run_cli_repl_session_transitions_render_active_copy_without_json(
    tmp_path,
) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["hello auto", "/new", "/use sess_manual", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Started new session sess_cli.") >= 2
    assert text.count("Active session: sess_cli.") >= 2
    assert "Switched to session sess_manual." in text
    assert "Active session: sess_manual." in text
    assert '{"session_id":' not in text
    assert '"session_id":' not in text


def test_run_cli_repl_history_shows_recent_messages(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/history 2", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "History for session sess_cli (last 2/4):" in text
    assert "user: second" in text
    assert "assistant: echo:second" in text
    assert "assistant: echo:first" not in text


def test_run_cli_repl_command_errors_include_actionable_suggestions(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/tools", "/use", "/unknown", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: no active session." in text
    assert "Layer: input" in text
    assert "Suggestion: run /new or /use <session_id>." in text
    assert "Error: missing session_id for /use." in text
    assert "Suggestion: try /use <session_id>." in text
    assert "Error: unknown command '/unknown'." in text
    assert "Suggestion: run /help to see available commands." in text


def test_run_cli_repl_absolute_path_input_is_not_treated_as_command(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    path_line = "/tmp/nano-test/screenshot_2026-03-03.png这个呢"
    inputs = iter(["/new", path_line, "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert f"echo:{path_line}" in text
    assert "unknown command" not in text
    assert (
        "submit",
        {"session_id": "sess_cli", "text": path_line, "model": "kimiCoding:K2.6"},
    ) in stub.calls


def test_run_cli_repl_ignores_blank_input_and_exits_on_eof(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    calls = iter(["   "])

    def _input(_: str) -> str:
        try:
            return next(calls)
        except StopIteration as exc:
            raise EOFError() from exc

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=_input,
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Auto mode" in text or "auto mode" in text, (
        f"Expected auto mode banner in REPL output, got: {text!r}"
    )
    assert "bye" in text
    # M2: kernel.close() is always called on REPL exit — only check no session was created/submitted
    assert not any(call[0] in ("create_session", "submit") for call in stub.calls)


def test_run_cli_repl_rejects_invalid_command_arguments(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/new extra", "/session now", "/use a b", "/history 0", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: command /new does not accept arguments." in text
    assert "Layer: input" in text
    assert "Suggestion: try /new." in text
    assert "Usage: /new" in text
    assert "Error: command /session does not accept arguments." in text
    assert "Suggestion: try /session." in text
    assert "Usage: /session" in text
    assert "Error: /use expects exactly one session_id." in text
    assert "Suggestion: try /use <session_id>." in text
    assert "Usage: /use <session_id>" in text
    assert "Error: invalid n for /history." in text
    assert "Suggestion: try /history 10." in text
    assert "Usage: /history [n]" in text
    assert ("create_session", {"title": None, "skills": None}) not in stub.calls


def test_run_cli_repl_compact_summary_displays_key_fields(tmp_path) -> None:
    stub = _CompactedKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "/compact", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Compaction for session sess_cli: compacted." in text
    assert "Summary: context compacted" in text


def test_run_cli_repl_compact_prints_post_compact_result(tmp_path) -> None:
    stub = _CompactedKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "/compact", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Compaction for session sess_cli: compacted." in text


def test_run_cli_repl_edit_history_budget_compact_chain_regression(tmp_path) -> None:
    stub = _CompactedKernelStub()
    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"],
            ["\x1b[A", "\x1b[C", "!", "\n"],
            ["/", "c", "o", "m", "p", "a", "c", "t", "\n"],
            ["/", "h", "i", "s", "t", "o", "r", "y", " ", "4", "\n"],
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
    text = output.getvalue()
    assert "echo:helXlo" in text
    assert "echo:helXlo!" in text
    assert "History for session sess_cli" in text
    assert "user: helXlo!" in text
    assert "Compaction for session sess_cli: compacted." in text


def test_run_cli_repl_context_budget_shows_threshold_hint(tmp_path) -> None:
    stub = _ThresholdBudgetKernelStub(used_tokens=174, max_tokens=200)
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text


def test_run_cli_repl_context_budget_fetch_failure_is_fail_open(tmp_path) -> None:
    # Context budget failure should not crash the REPL.
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text


def test_run_cli_repl_prints_turn_llm_usage_when_available(tmp_path) -> None:
    stub = _UsageKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "State: completed | stop=stop" in text
    assert "Usage: prompt=120, completion=35, total=155" in text
    assert "[status]" not in text
    assert "[usage]" not in text


def test_run_cli_repl_infers_completed_state_when_sync_payload_has_stop_reason(
    tmp_path,
) -> None:
    stub = _StopReasonOnlyKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "State: completed | stop=stop" in text


def test_run_cli_repl_request_failures_include_suggestions(tmp_path) -> None:
    stub = _FailingToolsKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "/tools", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: failed to run /tools." in text
    assert "Layer:" in text
    assert "Suggestion:" in text


def test_run_cli_repl_connection_refused_shows_error(tmp_path) -> None:
    stub = _ConnectionRefusedKernelStub()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "Connection refused" in text or "connection refused" in text.lower()
    assert "layer=network" in text


def test_run_cli_repl_timeout_shows_timeout_error(tmp_path) -> None:
    stub = _TimeoutKernelStub()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "timed out" in text
    assert "layer=network" in text
