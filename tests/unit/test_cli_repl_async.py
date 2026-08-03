"""User-visible REPL rendering over the current Kernel event stream."""

import io

from coding_cli.main import run_cli

from tests.unit._cli_kernel_stubs import (
    _AsyncEventingKernelStub,
    _AsyncFailedRunKernelStub,
    _AsyncLongToolOutputKernelStub,
    _AsyncMultilineToolKernelStub,
    _AsyncNoEventIdReplayKernelStub,
    _AsyncOrphanExecExitKernelStub,
    _AsyncSameToolSameOutputKernelStub,
    _AsyncSameToolTwiceKernelStub,
    _AsyncToolExecStreamingKernelStub,
    _make_kernel_factory,
)


def test_run_cli_repl_uses_async_events_with_run_filter_and_dedup(tmp_path) -> None:
    stub = _AsyncEventingKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "status=queued" not in text
    assert "Tool: echo start args=ping" in text
    assert "Tool echo start args=ping" not in text
    assert "Tool: echo output=echo:ping" in text
    assert "final:echo:ping" in text
    assert "State: completed | stop=stop" in text
    assert "[status]" not in text
    assert "ignore-me" not in text
    assert ("submit", {"session_id": "sess_cli", "text": "ping"}) in stub.calls


def test_repl_sanitizes_multiline_tool_preview(tmp_path) -> None:
    stub = _AsyncMultilineToolKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: echo output=line1\\nline2" in text
    assert "Tool: echo output=line1\nline2" not in text


def test_repl_truncates_long_tool_output_with_head_and_tail(tmp_path) -> None:
    stub = _AsyncLongToolOutputKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: echo output=HEAD-" in text
    assert "..." in text
    assert "-TAIL" in text
    assert "x" * 150 not in text


def test_run_cli_repl_groups_same_tool_name_events_by_call_id(tmp_path) -> None:
    stub = _AsyncSameToolTwiceKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: echo start args=") == 2
    assert "Tool echo start args=" not in text
    assert "Tool: echo output=echo:first" in text
    assert "Tool: echo output=echo:second" in text


def test_run_cli_repl_keeps_same_tool_output_lines_for_distinct_call_id(
    tmp_path,
) -> None:
    stub = _AsyncSameToolSameOutputKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: echo output=echo:same") == 2
    assert "final:echo:same" in text


def test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution(
    tmp_path,
) -> None:
    stub = _AsyncToolExecStreamingKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: bash start args=" in text
    assert "Tool: bash started status=started elapsed=0ms" in text
    assert "Tool: bash running status=running elapsed=120ms" not in text
    assert "Tool: bash chunk stdout#1: out-line" not in text
    assert "Tool: bash chunk stderr#2: err-line" not in text
    assert "Tool: bash progress chunks=2 (stdout=1, stderr=1)" in text
    assert text.count("Tool: bash exit code=0 status=completed duration=210ms") == 1
    assert text.index("Tool: bash started status=started elapsed=0ms") < text.index(
        "State:"
    )


def test_run_cli_repl_renders_orphan_tool_exit_as_isolated_timeline(tmp_path) -> None:
    stub = _AsyncOrphanExecExitKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: orphan bash exit code=137 status=failed duration=31ms" in text
    assert "Tool: bash exit code=0 status=completed duration=19ms" in text
    assert "Progress: orphan_events=1" in text
    assert "final:orphan-isolated" in text


def test_run_cli_repl_dedupes_replayed_tool_start_without_event_id(tmp_path) -> None:
    stub = _AsyncNoEventIdReplayKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("bash start args=") == 1
    assert text.count("Tool: bash exit code=0 status=completed duration=12ms") == 1
    assert "final:no-event-id" in text


def test_run_cli_repl_failed_run_has_actionable_compact_summary(tmp_path) -> None:
    stub = _AsyncFailedRunKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "hi", "/exit"])

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
    assert "State: failed | layer=runtime" in text
    assert "Error: send failed: run_id=run_failed" in text
    assert "[status]" not in text
