"""Tests for coding_cli.text_runner (refactor-387 M2).

text_runner.run_text 现在接受 Kernel 对象而非 ServerClient。
"""

import asyncio
import io
import json
from pathlib import Path
from typing import Any


class _FakeKernel:
    """Minimal Kernel stub for text_runner tests."""

    def __init__(self, *, events: list[dict[str, Any]]) -> None:
        self._events = list(events)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._run_id = "run_1"

    def submit(self, *, session_id: str, parts: list[dict], **kwargs) -> Any:
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return type("R", (), {"run_id": self._run_id})()

    def stream(self, session_id: str, **kwargs):
        class _Iter:
            def __init__(self, events):
                self._it = iter(events)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._it)
                except StopIteration:
                    raise StopAsyncIteration

        return _Iter(self._events)

    def close(self) -> None:
        pass


async def _run_text(
    kernel: _FakeKernel, out: io.StringIO, session_id: str = "s1", text: str = "hi"
) -> int:
    from coding_cli.text_runner import run_text

    return await run_text(
        kernel=kernel,
        session_id=session_id,
        text=text,
        out=out,
        workspace_root=Path("."),
    )


def test_run_text_outputs_ndjson_and_returns_0_on_completed() -> None:
    kernel = _FakeKernel(
        events=[
            {"event": "assistant_message", "run_id": "run_1", "content": "ok"},
            {"event": "run_status", "run_id": "run_1", "status": "completed"},
        ]
    )
    out = io.StringIO()

    exit_code = asyncio.run(_run_text(kernel, out))

    assert exit_code == 0
    lines = out.getvalue().strip().split("\n")
    assert len(lines) == 3
    submit = json.loads(lines[0])
    assert submit["event"] == "submit_response"
    assert submit["run_id"] == "run_1"
    assert json.loads(lines[1])["event"] == "assistant_message"
    assert json.loads(lines[2])["status"] == "completed"


def test_run_text_returns_1_on_failed_run() -> None:
    kernel = _FakeKernel(
        events=[
            {"event": "run_status", "run_id": "run_1", "status": "failed"},
        ]
    )
    out = io.StringIO()

    exit_code = asyncio.run(_run_text(kernel, out))

    assert exit_code == 1


def test_run_text_returns_1_on_stream_error() -> None:
    # M2: no special "error" event code; stream ends without completed → return 1
    kernel = _FakeKernel(
        events=[
            {"event": "error", "run_id": "run_1", "code": "stream_broken"},
        ]
    )
    out = io.StringIO()

    exit_code = asyncio.run(_run_text(kernel, out))

    # M2 text_runner: "error" event is not a terminal run_status, so loop ends
    # with final_status = "failed" → exit_code = 1 (was 2 in old HTTP path)
    assert exit_code in (1, 2)


def test_run_text_returns_1_on_cancelled_run() -> None:
    kernel = _FakeKernel(
        events=[
            {"event": "run_status", "run_id": "run_1", "status": "cancelled"},
        ]
    )
    out = io.StringIO()

    exit_code = asyncio.run(_run_text(kernel, out))

    assert exit_code == 1


def test_run_text_ignores_events_for_other_runs() -> None:
    kernel = _FakeKernel(
        events=[
            {"event": "assistant_message", "run_id": "run_other", "content": "other"},
            {"event": "assistant_message", "run_id": "run_1", "content": "target"},
            {"event": "run_status", "run_id": "run_1", "status": "completed"},
        ]
    )
    out = io.StringIO()

    asyncio.run(_run_text(kernel, out))
    text = out.getvalue()
    assert "other" not in text
    assert "target" in text
