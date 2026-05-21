"""REPL 异步事件渲染测试。

覆盖 async stream_session 路径下的事件过滤、去重、工具执行流、
SSE tail 批处理等行为。Stub classes 定义在 _cli_async_stubs.py。
"""

import io

from coding_cli.input import repl_input
from coding_cli.main import run_cli

from tests.unit._cli_async_stubs import (
    _AsyncChangedEventIdReplayStubClient,
    _AsyncEventingStubClient,
    _AsyncFailedRunStubClient,
    _AsyncLongToolOutputStubClient,
    _AsyncMultilineToolOutputStubClient,
    _AsyncNoEventIdReplayStubClient,
    _AsyncOrphanExecExitStubClient,
    _AsyncSameToolSameOutputStubClient,
    _AsyncSameToolTwiceStubClient,
    _AsyncToolExecStreamingStubClient,
    _AsyncUsageEventingStubClient,
    _ResumeHistoryStubClient,
    _TTYStringIO,
)


def test_run_cli_repl_uses_async_events_with_run_filter_and_dedup() -> None:
    stub = _AsyncEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "status=queued" not in text
    assert "Tool: echo start args=ping" in text
    assert "Tool echo start args=ping" not in text
    assert "Tool: echo output=echo:ping" in text
    assert "final:echo:ping" in text
    assert "ignore-me" not in text
    assert ("submit_message", {"session_id": "sess_cli", "text": "ping"}) in stub.calls


def test_repl_sanitizes_multiline_tool_preview() -> None:
    stub = _AsyncMultilineToolOutputStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: echo output=line1\\nline2" in text
    assert "Tool: echo output=line1\nline2" not in text


def test_repl_truncates_long_tool_output_with_head_and_tail() -> None:
    stub = _AsyncLongToolOutputStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: echo output=HEAD-" in text
    assert "..." in text
    assert "-TAIL" in text
    assert "x" * 150 not in text


def test_run_cli_repl_groups_same_tool_name_events_by_call_id() -> None:
    stub = _AsyncSameToolTwiceStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: echo start args=") == 2
    assert "Tool echo start args=" not in text
    assert "Tool: echo output=echo:first" in text
    assert "Tool: echo output=echo:second" in text


def test_run_cli_repl_keeps_same_tool_output_lines_for_distinct_call_id() -> None:
    stub = _AsyncSameToolSameOutputStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: echo output=echo:same") == 2
    assert "final:echo:same" in text


def test_run_cli_repl_prints_compact_answer_first_summary_for_async_flow() -> None:
    stub = _AsyncEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "final:echo:ping" in text
    assert "State: completed | stop=stop" in text
    assert "Tool: echo start args=ping" in text
    assert "Tool echo start args=ping" not in text
    assert "Tool: echo output=echo:ping" in text
    assert "Usage: unavailable" in text
    assert '"run_id": "run_target"' not in text
    assert "[status]" not in text


def test_run_cli_repl_prints_async_turn_llm_usage_when_available() -> None:
    stub = _AsyncUsageEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Usage: prompt=320, completion=41, total=361" in text


def test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution() -> None:
    stub = _AsyncToolExecStreamingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
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
    assert text.index("Tool: bash started status=started elapsed=0ms") < text.index("State:")


def test_run_cli_repl_renders_orphan_tool_exit_as_isolated_timeline() -> None:
    stub = _AsyncOrphanExecExitStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: orphan bash exit code=137 status=failed duration=31ms" in text
    assert "Tool: bash exit code=0 status=completed duration=19ms" in text
    assert "Progress: orphan_events=1" in text
    assert "final:orphan-isolated" in text


def test_run_cli_repl_dedupes_replayed_tool_start_without_event_id() -> None:
    stub = _AsyncNoEventIdReplayStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("bash start args=") == 1
    assert text.count("Tool: bash exit code=0 status=completed duration=12ms") == 1
    assert "final:no-event-id" in text


def test_run_cli_repl_dedupes_replayed_tool_start_with_changed_event_id() -> None:
    stub = _AsyncChangedEventIdReplayStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: bash start args=") == 1
    assert "final:changed-event-id" in text


def test_run_cli_repl_failed_run_error_includes_run_id_for_diagnosis() -> None:
    stub = _AsyncFailedRunStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "send failed: run_id=run_failed" in text
    assert "layer=runtime" in text


def test_run_cli_repl_prints_compact_error_summary_for_failed_run() -> None:
    stub = _AsyncFailedRunStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "State: failed | layer=runtime" in text
    assert "Error: send failed: run_id=run_failed" in text
    assert "Usage: unavailable" in text
    assert "[status]" not in text


def test_run_cli_repl_non_tty_async_output_avoids_emit_external_text_path(monkeypatch) -> None:
    stub = _AsyncToolExecStreamingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    def _forbid_emit_external_text(*, out, text):  # noqa: ANN001
        del out, text
        raise AssertionError("non-tty path must not call emit_external_text")

    monkeypatch.setattr(repl_input, "emit_external_text", _forbid_emit_external_text)
    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: bash start args=" in text
    assert "State: completed" in text
    assert "\r" not in text
    assert "\x1b[" not in text


def test_run_cli_repl_tty_async_output_disables_live_preview_until_renderer_is_stable() -> None:
    stub = _AsyncToolExecStreamingStubClient()
    output = _TTYStringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "done" in text
    assert "Tool: bash progress chunks=2 (stdout=1, stderr=1)" in text
    assert "Tool: bash exit code=0 status=completed duration=210ms" in text
    assert text.count("done") >= 1


def test_run_cli_repl_resume_batches_history_into_single_emit(monkeypatch) -> None:
    output = _TTYStringIO()
    emitted: list[str] = []
    original_emit_persistent_text = repl_input.emit_persistent_text

    def _record_emit_persistent_text(*, out, text):  # noqa: ANN001
        emitted.append(text)
        return original_emit_persistent_text(out=out, text=text)

    monkeypatch.setattr(repl_input, "emit_persistent_text", _record_emit_persistent_text)
    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--resume", "sess_hist"],
        stdout=output,
        client_factory=lambda _: _ResumeHistoryStubClient(),
        input_fn=lambda _: "/exit",
    )

    assert exit_code == 0
    history_emits = [text for text in emitted if "first question" in text]
    assert history_emits == [
        "> first question\nAssistant:\nfirst answer\nAssistant:\nsecond line 1\nsecond line 2"
    ]
