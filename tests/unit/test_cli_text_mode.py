"""CLI ``--text`` automation and terminal-output entry tests."""

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
# Kernel stubs for automation and terminal-output entry tests
# ---------------------------------------------------------------------------


class _TextModeKernelStub(_BaseKernelStub):
    """Stub for --text mode: one session create + one submit + stream."""

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.submitted_model = kwargs.get("model")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return type("R", (), {"run_id": "run_text"})()

    def stream(self, session_id, *, after_sequence=0):
        return _AsyncIterEvents(
            [
                {
                    "event": "assistant_message",
                    "run_id": "run_text",
                    "content": "ack:hello",
                },
                {
                    "event": "turn_end",
                    "run_id": "run_text",
                    "completed": True,
                    "stop_reason": "stop",
                },
                {"event": "run_status", "run_id": "run_text", "status": "completed"},
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
        return type("R", (), {"run_id": "run_tty"})()

    def stream(self, session_id, *, after_sequence=0):
        return _AsyncIterEvents(
            [
                {"event": "tool_start", "run_id": "run_tty", "name": "agent"},
                {
                    "event": "tool_end",
                    "run_id": "run_tty",
                    "name": "agent",
                    "duration_ms": 22,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_tty",
                    "content": "line one\nline two",
                },
                {"event": "run_status", "run_id": "run_tty", "status": "completed"},
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
        return type("R", (), {"run_id": "run_current"})()

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
                {
                    "event": "assistant_message",
                    "run_id": "run_current",
                    "content": "done",
                },
                {
                    "event": "run_status",
                    "run_id": "run_current",
                    "status": "completed",
                },
            ]
        )


def _simulate_terminal_rows(text: str) -> list[str]:
    """Apply cursor control needed to verify visible terminal line alignment."""
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
        elif char == "\n":
            row += 1
            while len(rows) <= row:
                rows.append({})
        else:
            rows[row][col] = char
            col += 1
        index += 1

    rendered: list[str] = []
    for cells in rows:
        if not cells:
            rendered.append("")
            continue
        rendered.append(
            "".join(cells.get(i, " ") for i in range(max(cells) + 1)).rstrip()
        )
    return rendered


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
    assert submit_line["run_id"] == "run_text"

    event_lines = [json.loads(line) for line in lines[1:]]
    run_events = [e for e in event_lines if e.get("run_id") == "run_text"]
    assert any(e.get("event") == "assistant_message" for e in run_events)
    assert any(
        e.get("event") == "run_status" and e.get("status") == "completed"
        for e in run_events
    )


def test_run_cli_text_mode_submits_current_model(tmp_path) -> None:
    stub = _TextModeKernelStub()
    expected_model = stub.get_llm_config().model
    output = io.StringIO()

    run_cli(
        ["--text", "hello"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert stub.submitted_model == expected_model


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
    assert any(
        call[0] == "submit" and call[1].get("session_id") == "sess_resume"
        for call in stub.calls
    ), f"Expected submit to sess_resume, got: {stub.calls}"
    assert ("submit", {"session_id": "sess_resume", "text": "hello"}) in stub.calls


def test_run_cli_repl_tty_turn_summary_starts_each_line_at_column_zero(
    tmp_path,
) -> None:
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


def test_run_cli_repl_non_tty_does_not_use_terminal_codes(tmp_path) -> None:
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


def test_run_cli_repl_handles_background_run_in_stream(tmp_path) -> None:
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
    assert "background wake (task_id=t1)" in text
    assert "done" in text
    assert "State: completed" in text
