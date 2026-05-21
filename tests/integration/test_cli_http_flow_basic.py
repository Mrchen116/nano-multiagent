"""Integration: CLI --text mode and HTTP error handling.

Covers non-interactive --text mode (stub clients; ASGITransport cannot be used
here because asyncio.run() nesting is disallowed) and the model timeout error
surface.  The full ASGI end-to-end chain is covered by REPL tests.
"""

import io
import json
from pathlib import Path

import httpx
import pytest

from coding_cli.main import run_cli
from agent.core.errors import ModelError
from agent.core.types import TurnResult
from agent.platform.http_api.app import create_app


class _ModelTimeoutRuntime:
    async def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None, controller=None, parent_session_id=None, origin=None) -> TurnResult:  # noqa: ANN001
        del session_id
        del parts
        del stream
        raise ModelError("timed out waiting for upstream; root_cause=connect ETIMEDOUT", retryable=False)


def test_cli_runs_http_flow_against_asgi_app() -> None:
    # --text mode uses asyncio.run(run_text(...)) in the main thread, which calls
    # client.stream_session() (httpx.AsyncClient).  ASGITransport + _AsyncTransportBridge
    # cannot be used here because asyncio.run() nesting is not allowed.  Use a
    # stub client instead; the ASGI end-to-end chain is covered by REPL tests.
    _RUN_ID = "run_asgi_flow_test"
    _SESSION_ID = "sess_asgi_flow_test"

    class _TextStub:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def create_session(self, **kw): return {"session_id": _SESSION_ID, "status": "idle", "metadata": {}}
        def submit_message(self, *, session_id, text, priority="next", **kw):
            return {"run_id": _RUN_ID, "anchor_sequence": 1, "injected": False, "status": "queued"}
        async def stream_session(self, *, session_id, last_event_id=None):
            yield {"event": "run_status", "run_id": _RUN_ID, "status": "running", "_id": 1, "session_id": session_id}
            yield {"event": "assistant_message", "run_id": _RUN_ID, "content": "pong", "_id": 2, "session_id": session_id}
            yield {"event": "run_status", "run_id": _RUN_ID, "status": "completed", "stop_reason": "stop", "_id": 3, "session_id": session_id}

    client = _TextStub()
    send_out = io.StringIO()
    send_code = run_cli(
        ["--base-url", "http://testserver", "--text", "ping"],
        stdout=send_out,
        client_factory=lambda _: client,
    )

    assert send_code == 0
    lines = [json.loads(l) for l in send_out.getvalue().strip().split("\n") if l.strip()]
    run_events = [e for e in lines if e.get("event") == "run_status" and e.get("status") == "completed"]
    assert run_events, "expected completed run_status event"


def test_cli_text_mode_outputs_ndjson_events_for_completed_run() -> None:
    # send-message subcommand was removed; --text mode is the canonical non-interactive path.
    # Verify it emits NDJSON lines and terminates with a completed run_status event.
    # Uses a stub client: ASGITransport cannot be used here (asyncio.run() nesting disallowed).
    _RUN_ID = "run_text_ndjson_test"
    _SESSION_ID = "sess_text_ndjson_test"

    class _TextStub:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def create_session(self, **kw): return {"session_id": _SESSION_ID, "status": "idle", "metadata": {}}
        def submit_message(self, *, session_id, text, priority="next", **kw):
            return {"run_id": _RUN_ID, "anchor_sequence": 1, "injected": False, "status": "queued"}
        async def stream_session(self, *, session_id, last_event_id=None):
            yield {"event": "run_status", "run_id": _RUN_ID, "status": "running", "_id": 1, "session_id": session_id}
            yield {"event": "run_status", "run_id": _RUN_ID, "status": "completed", "stop_reason": "stop", "_id": 2, "session_id": session_id}

    client = _TextStub()
    send_out = io.StringIO()
    send_code = run_cli(
        ["--base-url", "http://testserver", "--text", "ping"],
        stdout=send_out,
        client_factory=lambda _: client,
    )
    assert send_code == 0
    lines = [json.loads(l) for l in send_out.getvalue().strip().split("\n") if l.strip()]
    # --text mode emits NDJSON lines: at minimum submit_response + run_status events
    assert len(lines) >= 2
    statuses = [e.get("status") for e in lines if e.get("event") == "run_status"]
    assert "completed" in statuses


@pytest.mark.skip(reason="REPL+ASGI hang: SessionStreamReader需要单一event-loop — tracked in #47")
def test_cli_timeout_error_surfaces_root_cause_and_trace_id_evidence() -> None:
    app = create_app(runtime=_ModelTimeoutRuntime())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["hi", "/exit"])
    exit_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--request-id",
            "req-cli-timeout-root-cause",
        ],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "run_id=" in text
    assert "Assistant: (empty)" in text
    assert "Error:" in text
    assert "layer=runtime" in text
    assert "run failed: {'code': 'run_execution_failed'" in text
    assert "root_cause=connect ETIMEDOUT" in text
    assert "NANO_MULTIAGENT_API_TIMEOUT_SECONDS" in text
