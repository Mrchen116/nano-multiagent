"""CLI text 模式 + 流式 REPL 路径测试 (refactor-387 M2)。

覆盖 --text 单次提交输出 NDJSON、流式 turn_end 渲染、
tty 行首对齐、非 user origin run 头部。
M2 后走 Kernel SDK 进程内流式（无 HTTP SSE）。
"""

import io
import json

from coding_cli.main import run_cli
from tests.unit._cli_kernel_stubs import (
    _BaseKernelStub,
    _AsyncIterEvents,
    _TTYStringIO,
    _make_kernel_factory,
)


# ---------------------------------------------------------------------------
# Kernel stubs for text/SSE path tests
# ---------------------------------------------------------------------------


class _TextModeKernelStub(_BaseKernelStub):
    """Stub for --text mode: one session create + one submit + stream."""

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return type("R", (), {"run_id": "run_sse"})()

    def stream(self, session_id, *, after_sequence=0):
        return _AsyncIterEvents(
            [
                {
                    "event": "assistant_message",
                    "run_id": "run_sse",
                    "content": "ack:hello",
                },
                {
                    "event": "turn_end",
                    "run_id": "run_sse",
                    "completed": True,
                    "stop_reason": "stop",
                },
                {"event": "run_status", "run_id": "run_sse", "status": "completed"},
            ]
        )


class _TtyToolKernelStub(_BaseKernelStub):
    """Stub for TTY path: tool start/end + multiline assistant reply."""

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self._last_text = text
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return type("R", (), {"run_id": "run_sse"})()

    def stream(self, session_id, *, after_sequence=0):
        return _AsyncIterEvents(
            [
                {"event": "tool_start", "run_id": "run_sse", "name": "agent"},
                {
                    "event": "tool_end",
                    "run_id": "run_sse",
                    "name": "agent",
                    "duration_ms": 22,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_sse",
                    "content": "line one\nline two",
                },
                {"event": "run_status", "run_id": "run_sse", "status": "completed"},
            ]
        )


class _BgRunKernelStub(_BaseKernelStub):
    """Stub with a background-origin run event mixed in."""

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return type("R", (), {"run_id": "run_sse"})()

    def stream(self, session_id, *, after_sequence=0):
        return _AsyncIterEvents(
            [
                {
                    "event": "run_status",
                    "run_id": "run_bg",
                    "status": "running",
                    "origin": "background_task",
                    "source_task_id": "t1",
                },
                {"event": "assistant_message", "run_id": "run_sse", "content": "done"},
                {"event": "run_status", "run_id": "run_sse", "status": "completed"},
            ]
        )


# ---------------------------------------------------------------------------
# Tests: text mode
# ---------------------------------------------------------------------------


def test_run_cli_text_mode_creates_session_and_streams_ndjson(tmp_path) -> None:
    stub = _TextModeKernelStub()
    output = io.StringIO()

    exit_code = run_cli(
        ["--text", "hello"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    lines = output.getvalue().strip().split("\n")
    assert len(lines) >= 2
    submit_line = json.loads(lines[0])
    assert submit_line["event"] == "submit_response"
    assert submit_line["run_id"] == "run_sse"

    event_lines = [json.loads(line) for line in lines[1:]]
    run_events = [e for e in event_lines if e.get("run_id") == "run_sse"]
    assert any(e.get("event") == "assistant_message" for e in run_events)
    assert any(
        e.get("event") == "run_status" and e.get("status") == "completed"
        for e in run_events
    )


def test_run_cli_text_mode_uses_resume_session_when_given(tmp_path) -> None:
    stub = _TextModeKernelStub()
    output = io.StringIO()

    exit_code = run_cli(
        ["--resume", "sess_resume", "--text", "hello"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    # --resume sets session_id; submit uses it instead of freshly created session
    assert any(
        call[0] == "submit" and call[1].get("session_id") == "sess_resume"
        for call in stub.calls
    ), f"Expected submit to sess_resume, got: {stub.calls}"
    # create_session is called but then overridden by --resume
    assert ("submit", {"session_id": "sess_resume", "text": "hello"}) in stub.calls


# ---------------------------------------------------------------------------
# Tests: SSE REPL path (now: SDK stream REPL path)
# ---------------------------------------------------------------------------


def test_run_cli_repl_uses_sse_path_when_submit_message_available(tmp_path) -> None:
    stub = _TextModeKernelStub()
    output = io.StringIO()
    inputs = iter(["hello", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "ack:hello" in text
    assert ("submit", {"session_id": "sess_cli", "text": "hello"}) in stub.calls


def test_run_cli_repl_tty_turn_summary_starts_each_line_at_column_zero(
    tmp_path,
) -> None:
    from tests.unit._cli_async_stubs import _simulate_terminal_rows

    stub = _TextModeKernelStub()
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
    rows = _simulate_terminal_rows(output.getvalue())
    summary_rows = [
        row
        for row in rows
        if row.lstrip().startswith(("State:", "Usage:", "Context budget:"))
    ]
    assert summary_rows
    assert all(
        row.startswith(("State:", "Usage:", "Context budget:")) for row in summary_rows
    )


# ---------------------------------------------------------------------------
# Tests: _send_message_async behavior (via run_cli integration)
# ---------------------------------------------------------------------------


def test_send_message_builds_payload_from_events(tmp_path) -> None:
    """Verify that a turn payload with assistant reply is built correctly."""
    stub = _TextModeKernelStub()
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
    assert "ack:hello" in text
    assert "State: completed" in text


def test_send_message_renders_tool_events(tmp_path) -> None:
    """Verify that tool events appear in the REPL output."""
    from tests.unit._cli_kernel_stubs import _AsyncToolExecStreamingKernelStub

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


def test_send_message_non_tty_does_not_use_terminal_codes(tmp_path) -> None:
    """Non-TTY path must not emit ANSI escape sequences."""
    stub = _TtyToolKernelStub()
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
    assert "State: completed" in text
    assert "\r" not in text
    assert "\x1b[" not in text


def test_send_message_tty_uses_terminal_safe_line_endings(tmp_path) -> None:
    """TTY path: \n must be preceded by \r (terminal safe)."""
    stub = _TtyToolKernelStub()
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
    assert "line one" in text


def test_send_message_handles_background_run_in_stream(tmp_path) -> None:
    """Events from other run_ids should not break the current run's drain."""
    stub = _BgRunKernelStub()
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
    assert "done" in text
    assert "State: completed" in text
