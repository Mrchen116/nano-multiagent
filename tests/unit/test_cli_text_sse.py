"""CLI text 模式 + SSE REPL 路径测试。

覆盖 --text 单次提交输出 NDJSON、SSE turn_end 渲染、
tty 行首对齐、非 user origin run 头部，以及
_send_message_via_sse 内部接口契约。
"""

import io
import json

from coding_cli.main import run_cli


# ---------------------------------------------------------------------------
# TTY stub
# ---------------------------------------------------------------------------

class _TTYStringIO(io.StringIO):
    """StringIO that reports isatty()=True for tty-branch coverage."""

    def isatty(self) -> bool:
        return True


def _simulate_terminal_rows(text: str) -> list[str]:
    """Replay ANSI cursor-up + carriage-return sequences to produce final terminal rows."""
    rows: list[str] = [""]
    cursor = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\r":
            cursor = 0
            i += 1
        elif ch == "\n":
            cursor = 0
            rows.append("")
            i += 1
        elif ch == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
            j = i + 2
            while j < len(text) and (text[j].isdigit() or text[j] == ";"):
                j += 1
            if j < len(text):
                cmd = text[j]
                param_str = text[i + 2:j]
                n = int(param_str) if param_str.isdigit() else 1
                if cmd == "A":
                    rows_to_move = min(n, len(rows) - 1)
                    current_row_index = len(rows) - 1
                    target_row_index = current_row_index - rows_to_move
                    while len(rows) - 1 > target_row_index:
                        rows.pop()
                    cursor = 0
                i = j + 1
            else:
                i += 1
        else:
            row = rows[-1]
            if cursor < len(row):
                rows[-1] = row[:cursor] + ch + row[cursor + 1:]
            else:
                rows[-1] = row + " " * (cursor - len(row)) + ch
            cursor += 1
            i += 1
    return rows


# ---------------------------------------------------------------------------
# SSE stub clients
# ---------------------------------------------------------------------------

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

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "used_tokens": 64,
            "max_tokens": 200,
            "remaining_tokens": 136,
            "usage_ratio": 0.32,
        }


class _SseStubClient(_StubClient):
    """Stub client that implements submit_message + stream_session for SSE REPL tests."""

    def __init__(self, *, events: list[dict[str, object]] | None = None) -> None:
        super().__init__()
        self._sse_events = list(events) if events is not None else []
        self.submit_calls: list[dict[str, object]] = []

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str | None = None,
    ) -> dict[str, object]:
        self.submit_calls.append({"session_id": session_id, "text": text, "priority": priority})
        self.calls.append(("submit_message", {"session_id": session_id, "text": text, "priority": priority}))
        return {"run_id": "run_sse", "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(
        self,
        *,
        session_id: str,
        last_event_id: int | None = None,
    ):
        del session_id, last_event_id
        for event in self._sse_events:
            yield event


class _SseStubClientWithTurnEnd(_SseStubClient):
    def __init__(self) -> None:
        super().__init__(
            events=[
                {"event": "assistant_message", "run_id": "run_sse", "content": "ack:hello"},
                {"event": "turn_end", "run_id": "run_sse", "completed": True, "stop_reason": "stop"},
                {"event": "run_status", "run_id": "run_sse", "status": "completed"},
            ]
        )


# ---------------------------------------------------------------------------
# Tests: text mode
# ---------------------------------------------------------------------------

def test_run_cli_text_mode_creates_session_and_streams_ndjson() -> None:
    stub = _SseStubClientWithTurnEnd()
    output = io.StringIO()

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--text", "hello"],
        stdout=output,
        client_factory=lambda _: stub,
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
    assert any(e.get("event") == "run_status" and e.get("status") == "completed" for e in run_events)


def test_run_cli_text_mode_uses_resume_session_when_given() -> None:
    stub = _SseStubClientWithTurnEnd()
    output = io.StringIO()

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--resume", "sess_resume", "--text", "hello"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    assert ("submit_message", {"session_id": "sess_resume", "text": "hello", "priority": None}) in stub.calls
    assert "create_session" not in [call[0] for call in stub.calls]


# ---------------------------------------------------------------------------
# Tests: SSE REPL path
# ---------------------------------------------------------------------------

def test_run_cli_repl_uses_sse_path_when_submit_message_available() -> None:
    stub = _SseStubClientWithTurnEnd()
    output = io.StringIO()
    inputs = iter(["hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "ack:hello" in text
    assert ("submit_message", {"session_id": "sess_cli", "text": "hello", "priority": None}) in stub.calls


def test_run_cli_repl_tty_turn_summary_starts_each_line_at_column_zero() -> None:
    stub = _SseStubClientWithTurnEnd()
    output = _TTYStringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    rows = _simulate_terminal_rows(output.getvalue())
    summary_rows = [
        row for row in rows
        if row.lstrip().startswith(("State:", "Usage:", "Context budget:"))
    ]
    assert summary_rows
    assert all(row.startswith(("State:", "Usage:", "Context budget:")) for row in summary_rows)


# ---------------------------------------------------------------------------
# Tests: _send_message_via_sse internal contract
# ---------------------------------------------------------------------------

def test_send_message_via_sse_builds_payload_from_events() -> None:
    from coding_cli.commands import _send_message_via_sse
    from coding_cli.session_stream import SessionStreamReader

    client = _SseStubClientWithTurnEnd()
    reader = SessionStreamReader(client)
    reader.start(session_id="sess_test")

    try:
        out = io.StringIO()
        payload = _send_message_via_sse(
            out=out,
            client=client,
            reader=reader,
            session_id="sess_test",
            text="ping",
        )
    finally:
        reader.stop()

    assert payload["session_id"] == "sess_test"
    assert payload["run_id"] == "run_sse"
    assert payload["message"]["content"] == "ack:hello"
    assert payload["status"] == "completed"
    assert payload["completed"] is True
    assert payload["stop_reason"] == "stop"


def test_send_message_via_sse_renders_tool_events() -> None:
    from coding_cli.commands import _send_message_via_sse
    from coding_cli.session_stream import SessionStreamReader

    client = _SseStubClient(
        events=[
            {"event": "tool_start", "run_id": "run_sse", "name": "bash", "call_id": "c1"},
            {"event": "assistant_message", "run_id": "run_sse", "content": "done"},
            {"event": "run_status", "run_id": "run_sse", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="sess_test")

    try:
        out = io.StringIO()
        payload = _send_message_via_sse(
            out=out,
            client=client,
            reader=reader,
            session_id="sess_test",
            text="run bash",
        )
    finally:
        reader.stop()

    assert payload["message"]["content"] == "done"
    assert payload["status"] == "completed"


def test_send_message_via_sse_non_tty_does_not_set_text_streamed() -> None:
    from coding_cli.commands import _send_message_via_sse
    from coding_cli.session_stream import SessionStreamReader

    client = _SseStubClientWithTurnEnd()
    reader = SessionStreamReader(client)
    reader.start(session_id="sess_test")

    try:
        out = io.StringIO()
        payload = _send_message_via_sse(
            out=out,
            client=client,
            reader=reader,
            session_id="sess_test",
            text="ping",
        )
    finally:
        reader.stop()

    assert payload.get("_text_streamed") is False


def test_send_message_via_sse_tty_output_uses_terminal_safe_line_endings() -> None:
    from coding_cli.commands import _send_message_via_sse
    from coding_cli.session_stream import SessionStreamReader

    client = _SseStubClient(
        events=[
            {"event": "tool_start", "run_id": "run_sse", "name": "agent"},
            {"event": "tool_end", "run_id": "run_sse", "name": "agent", "duration_ms": 22},
            {"event": "assistant_message", "run_id": "run_sse", "content": "line one\nline two"},
            {"event": "run_status", "run_id": "run_sse", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="sess_test")

    try:
        out = _TTYStringIO()
        payload = _send_message_via_sse(
            out=out,
            client=client,
            reader=reader,
            session_id="sess_test",
            text="ping",
        )
    finally:
        reader.stop()

    text = out.getvalue()
    assert payload["status"] == "completed"
    assert "> line one" in text
    for index, char in enumerate(text):
        if char == "\n":
            assert index > 0
            assert text[index - 1] == "\r"


def test_send_message_via_sse_renders_origin_header_for_non_user_run() -> None:
    from coding_cli.commands import _send_message_via_sse
    from coding_cli.session_stream import SessionStreamReader

    client = _SseStubClient(
        events=[
            {"event": "run_status", "run_id": "run_bg", "status": "running", "origin": "background_task", "source_task_id": "t1"},
            {"event": "assistant_message", "run_id": "run_sse", "content": "done"},
            {"event": "run_status", "run_id": "run_sse", "status": "completed"},
        ]
    )
    reader = SessionStreamReader(client)
    reader.start(session_id="sess_test")

    try:
        out = io.StringIO()
        payload = _send_message_via_sse(
            out=out,
            client=client,
            reader=reader,
            session_id="sess_test",
            text="ping",
        )
    finally:
        reader.stop()

    text = out.getvalue()
    assert "── background wake (task_id=t1) ──" in text
    assert payload["status"] == "completed"
