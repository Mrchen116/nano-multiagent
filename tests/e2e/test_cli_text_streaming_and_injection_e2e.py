"""E2E tests for CLI text streaming and priority='next' injection."""

import io
from typing import Any

from coding_cli.client import ServerClient
from coding_cli.events.repl_events import consume_async_run_events, send_message_with_async_events
from coding_cli.render.repl_render import print_repl_turn_summary


class _FakeClient:
    """Minimal fake for send_message_with_async_events tests."""

    def __init__(self, *, events_batches: list[list[dict[str, Any]]], terminal_run: dict[str, Any]) -> None:
        self._events_batches = list(events_batches)
        self._terminal_run = terminal_run
        self.calls: list[dict[str, Any]] = []

    def send_message_async(self, *, session_id: str, text: str, priority: str | None = None) -> dict[str, Any]:
        self.calls.append({"method": "send_message_async", "session_id": session_id, "text": text, "priority": priority})
        return {"run_id": "run_stream_e2e", "session_id": session_id, "status": "queued"}

    def stream_session_events(self, *, session_id: str, after_sequence: int = 0, max_events: int, timeout_seconds: float) -> list[dict[str, Any]]:
        del after_sequence
        if self._events_batches:
            return self._events_batches.pop(0)
        return []

    def get_run(self, *, run_id: str) -> dict[str, Any]:
        return dict(self._terminal_run)


def test_consume_async_run_events_streams_text_delta_directly() -> None:
    out = io.StringIO()
    events = [
        {"event_id": "e1", "event": "text_delta", "data": {"run_id": "r1", "delta": "Hello "}},
        {"event_id": "e2", "event": "text_delta", "data": {"run_id": "r1", "delta": "world"}},
        {"event_id": "e3", "event": "tool_start", "data": {"run_id": "r1", "name": "bash"}},
    ]
    text, consumed, text_streamed = consume_async_run_events(
        out=out,
        events=events,
        run_id="r1",
        assistant_text="",
    )
    assert text == "Hello world"
    assert consumed == 3
    assert text_streamed is True
    written = out.getvalue()
    assert "Hello world" in written
    assert "Tool:" in written


def test_consume_async_run_events_no_text_delta_returns_false() -> None:
    out = io.StringIO()
    events = [
        {"event_id": "e1", "event": "tool_start", "data": {"run_id": "r1", "name": "bash"}},
    ]
    text, consumed, text_streamed = consume_async_run_events(
        out=out,
        events=events,
        run_id="r1",
        assistant_text="",
    )
    assert text == ""
    assert consumed == 1
    assert text_streamed is False


def test_send_message_with_async_events_appends_newline_after_streaming() -> None:
    out = io.StringIO()
    client = _FakeClient(
        events_batches=[
            [
                {"event_id": "e1", "event": "text_delta", "data": {"run_id": "run_stream_e2e", "delta": "ok"}},
                {"event_id": "e2", "event": "run_status", "data": {"run_id": "run_stream_e2e", "status": "completed"}},
            ],
        ],
        terminal_run={"status": "completed", "turn_id": "t1"},
    )
    result = send_message_with_async_events(
        out=out,
        client=client,  # type: ignore[arg-type]
        session_id="s1",
        text="hi",
    )
    assert result.get("message", {}).get("content") == "ok"
    assert result.get("_text_streamed") is True
    written = out.getvalue()
    # Should contain streamed text plus trailing newline before summary
    assert "ok\n" in written or written.endswith("ok\n")


def test_print_repl_turn_summary_skips_text_when_streamed() -> None:
    out = io.StringIO()
    payload = {
        "session_id": "s1",
        "run_id": "r1",
        "status": "completed",
        "completed": True,
        "stop_reason": "stop",
        "message": {"role": "assistant", "content": "already streamed"},
        "_text_streamed": True,
        "_repl_view": {"status_updates": [], "tool_updates": []},
    }
    print_repl_turn_summary(out=out, payload=payload)
    text = out.getvalue()
    assert "already streamed" not in text
    assert "State: completed" in text


def test_print_repl_turn_summary_prints_text_when_not_streamed() -> None:
    out = io.StringIO()
    payload = {
        "session_id": "s1",
        "run_id": "r1",
        "status": "completed",
        "completed": True,
        "stop_reason": "stop",
        "message": {"role": "assistant", "content": "not streamed"},
        "_text_streamed": False,
        "_repl_view": {"status_updates": [], "tool_updates": []},
    }
    print_repl_turn_summary(out=out, payload=payload)
    text = out.getvalue()
    assert "not streamed" in text
    assert "Assistant:" in text
