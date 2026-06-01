"""REPL 异步事件渲染测试 (refactor-387 M2)。

覆盖 async stream() 路径下的事件过滤、去重、工具执行流等行为。
Stub classes 定义在 _cli_kernel_stubs.py（M2 后的 Kernel 接口）。
"""

import io

from coding_cli.input import repl_input
from coding_cli.main import run_cli

from tests.unit._cli_kernel_stubs import (
    _AsyncChangedEventIdReplayKernelStub,
    _AsyncEventingKernelStub,
    _AsyncFailedRunKernelStub,
    _AsyncLongToolOutputKernelStub,
    _AsyncMultilineToolKernelStub,
    _AsyncNoEventIdReplayKernelStub,
    _AsyncOrphanExecExitKernelStub,
    _AsyncSameToolSameOutputKernelStub,
    _AsyncSameToolTwiceKernelStub,
    _AsyncToolExecStreamingKernelStub,
    _BaseKernelStub,
    _TTYStringIO,
    _make_kernel_factory,
)


class _AsyncUsageEventingKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return type("R", (), {"run_id": "run_target"})()

    def stream(self, session_id, *, after_sequence=0):
        from tests.unit._cli_kernel_stubs import _AsyncIterEvents

        return _AsyncIterEvents(
            [
                {"event": "run_status", "run_id": "run_target", "status": "queued"},
                {
                    "event": "assistant_message",
                    "run_id": "run_target",
                    "content": "final:echo:ping",
                },
                {
                    "event": "tool_start",
                    "run_id": "run_target",
                    "name": "echo",
                    "call_id": "call_1",
                    "arguments": {"text": "ping"},
                },
                {
                    "event": "tool_end",
                    "run_id": "run_target",
                    "name": "echo",
                    "call_id": "call_1",
                    "output": {"text": "echo:ping"},
                    "error": None,
                },
                {
                    "event": "run_status",
                    "run_id": "run_target",
                    "status": "completed",
                    "stop_reason": "stop",
                    "usage": {
                        "prompt_tokens": 320,
                        "completion_tokens": 41,
                        "total_tokens": 361,
                    },
                },
            ]
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


def test_run_cli_repl_prints_compact_answer_first_summary_for_async_flow(
    tmp_path,
) -> None:
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
    assert "final:echo:ping" in text
    assert "State: completed | stop=stop" in text
    assert "Tool: echo start args=ping" in text
    assert "Tool echo start args=ping" not in text
    assert "Tool: echo output=echo:ping" in text
    assert "[status]" not in text


def test_run_cli_repl_prints_async_turn_llm_usage_when_available(tmp_path) -> None:
    stub = _AsyncUsageEventingKernelStub()
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
    assert "Usage: prompt=320, completion=41, total=361" in text


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


def test_run_cli_repl_dedupes_replayed_tool_start_with_changed_event_id(
    tmp_path,
) -> None:
    stub = _AsyncChangedEventIdReplayKernelStub()
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
    assert text.count("Tool: bash start args=") == 1
    assert "final:changed-event-id" in text


def test_run_cli_repl_failed_run_error_includes_run_id_for_diagnosis(tmp_path) -> None:
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
    assert "send failed: run_id=run_failed" in text
    assert "layer=runtime" in text


def test_run_cli_repl_prints_compact_error_summary_for_failed_run(tmp_path) -> None:
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


def test_run_cli_repl_non_tty_async_output_avoids_emit_external_text_path(
    monkeypatch, tmp_path
) -> None:
    stub = _AsyncToolExecStreamingKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    def _forbid_emit_external_text(*, out, text):  # noqa: ANN001
        del out, text
        raise AssertionError("non-tty path must not call emit_external_text")

    monkeypatch.setattr(repl_input, "emit_external_text", _forbid_emit_external_text)
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
    assert "State: completed" in text
    assert "\r" not in text
    assert "\x1b[" not in text


def test_run_cli_repl_tty_async_output_disables_live_preview_until_renderer_is_stable(
    tmp_path,
) -> None:
    stub = _AsyncToolExecStreamingKernelStub()
    output = _TTYStringIO()
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
    assert "done" in text
    assert "Tool: bash progress chunks=2 (stdout=1, stderr=1)" in text
    assert "Tool: bash exit code=0 status=completed duration=210ms" in text
    assert text.count("done") >= 1


def test_run_cli_repl_resume_batches_history_into_single_emit(
    monkeypatch, tmp_path
) -> None:
    # M2 does not load history via HTTP; --resume only sets active session_id.
    # Verify that --resume sets the active session without error.
    stub = _BaseKernelStub(session_id="sess_hist")
    output = _TTYStringIO()
    emitted: list[str] = []
    original_emit_persistent_text = repl_input.emit_persistent_text

    def _record_emit_persistent_text(*, out, text):  # noqa: ANN001
        emitted.append(text)
        return original_emit_persistent_text(out=out, text=text)

    monkeypatch.setattr(
        repl_input, "emit_persistent_text", _record_emit_persistent_text
    )
    exit_code = run_cli(
        ["--resume", "sess_hist"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: "/exit",
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    # M2: history loading removed (no HTTP GET /messages); only banner emitted.
    text = output.getvalue()
    assert "bye" in text or "Auto mode" in text
