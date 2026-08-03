"""User-visible REPL command and error behavior."""

import io

from coding_cli.main import run_cli

from tests.unit._cli_kernel_stubs import (
    _BaseKernelStub,
    _CompactedKernelStub,
    _ConnectionRefusedKernelStub,
    _FailingToolsKernelStub,
    _TimeoutKernelStub,
    _UsageKernelStub,
    _make_kernel_factory,
)


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
    assert "bye" in text
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


def test_run_cli_repl_without_budget_metrics_still_completes_turn(tmp_path) -> None:
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
