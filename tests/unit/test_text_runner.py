"""Tests for coding_cli.text_runner."""

import io
import json
from typing import Any

from coding_cli.text_runner import run_text


class _FakeClient:
    def __init__(self, *, events: list[dict[str, Any]], submit_response: dict[str, Any] | None = None) -> None:
        self._events = list(events)
        self._submit_response = submit_response or {
            "run_id": "run_1",
            "anchor_sequence": 5,
            "injected": False,
            "status": "queued",
        }
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def submit_message(self, *, session_id: str, text: str, priority: str | None = None) -> dict[str, Any]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return dict(self._submit_response)

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        self.calls.append(("stream_session", {"session_id": session_id, "last_event_id": last_event_id}))
        for event in self._events:
            yield event


async def _run_text(client: _FakeClient, out: io.StringIO, session_id: str = "s1", text: str = "hi") -> int:
    return await run_text(client=client, session_id=session_id, text=text, out=out)


def test_run_text_outputs_ndjson_and_returns_0_on_completed() -> None:
    client = _FakeClient(
        events=[
            {"event": "assistant_message", "run_id": "run_1", "content": "ok"},
            {"event": "run_status", "run_id": "run_1", "status": "completed"},
        ]
    )
    out = io.StringIO()
    import asyncio

    exit_code = asyncio.run(_run_text(client, out))

    assert exit_code == 0
    lines = out.getvalue().strip().split("\n")
    assert len(lines) == 3
    submit = json.loads(lines[0])
    assert submit["event"] == "submit_response"
    assert submit["run_id"] == "run_1"
    assert json.loads(lines[1])["event"] == "assistant_message"
    assert json.loads(lines[2])["status"] == "completed"


def test_run_text_returns_1_on_failed_run() -> None:
    client = _FakeClient(
        events=[
            {"event": "run_status", "run_id": "run_1", "status": "failed"},
        ]
    )
    out = io.StringIO()
    import asyncio

    exit_code = asyncio.run(_run_text(client, out))

    assert exit_code == 1


def test_run_text_returns_2_on_stream_error() -> None:
    client = _FakeClient(
        events=[
            {"event": "error", "run_id": "run_1", "code": "stream_broken"},
        ]
    )
    out = io.StringIO()
    import asyncio

    exit_code = asyncio.run(_run_text(client, out))

    assert exit_code == 2


def test_run_text_returns_1_on_cancelled_run() -> None:
    client = _FakeClient(
        events=[
            {"event": "run_status", "run_id": "run_1", "status": "cancelled"},
        ]
    )
    out = io.StringIO()
    import asyncio

    exit_code = asyncio.run(_run_text(client, out))

    assert exit_code == 1


def test_run_text_ignores_events_for_other_runs() -> None:
    client = _FakeClient(
        events=[
            {"event": "assistant_message", "run_id": "run_other", "content": "other"},
            {"event": "assistant_message", "run_id": "run_1", "content": "target"},
            {"event": "run_status", "run_id": "run_1", "status": "completed"},
        ]
    )
    out = io.StringIO()
    import asyncio

    asyncio.run(_run_text(client, out))
    text = out.getvalue()
    assert "other" not in text
    assert "target" in text
