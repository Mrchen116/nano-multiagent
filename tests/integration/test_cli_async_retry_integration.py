"""Integration: CLI REPL chain completes successfully end-to-end.

After M6, transient retry is handled inside AgentLoop; the old retry-progress
SSE fields (_wait_with_cancel) were removed. This test verifies that the CLI
REPL chain handles the current SSE event shape (run_status:completed) and
exits cleanly after receiving a turn result.

Uses a full stub client so the test does not depend on ASGI transport
threading behaviour (stream_session() crosses thread boundaries in
SessionStreamReader, making cross-event-loop ASGI transport unsafe here).
"""

import io

from coding_cli.main import run_cli


_RUN_ID = "run_cli_retry_integration"
_SESSION_ID = "sess_cli_retry_integration"


class _StubClient:
    """Minimal stub for coding_cli that models a successful one-turn REPL session."""

    def __init__(self) -> None:
        self.create_session_calls: int = 0
        self.submit_calls: list[dict] = []

    # ---- context manager (run_cli uses `with factory(config) as client:`) ----

    def __enter__(self) -> "_StubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        pass

    # ---- session management ----

    def create_session(self, **kwargs) -> dict:  # noqa: ANN003
        self.create_session_calls += 1
        return {"session_id": _SESSION_ID, "status": "idle", "metadata": {}}

    def get_session(self, *, session_id: str) -> dict:
        return {"session_id": session_id, "status": "active", "metadata": {}}

    def get_session_messages(self, *, session_id: str, limit: int = 100) -> dict:
        return {"messages": []}

    def health(self) -> dict:
        return {"status": "ok"}

    # ---- message submission ----

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", **kwargs) -> dict:  # noqa: ANN003
        self.submit_calls.append({"session_id": session_id, "text": text})
        return {"run_id": _RUN_ID, "anchor_sequence": 1, "injected": False, "status": "queued"}

    # ---- SSE stream: simulate one completed run ----

    async def stream_session(self, *, session_id: str, last_event_id=None):
        # Yield one complete turn's worth of events so drain_run() exits promptly.
        yield {"event": "run_status", "run_id": _RUN_ID, "status": "running", "_id": 1, "session_id": session_id}
        yield {"event": "assistant_message", "run_id": _RUN_ID, "content": "ok", "_id": 2, "session_id": session_id}
        yield {
            "event": "turn_end",
            "run_id": _RUN_ID,
            "completed": True,
            "stop_reason": "completed",
            "_id": 3,
            "session_id": session_id,
        }
        yield {
            "event": "run_status",
            "run_id": _RUN_ID,
            "status": "completed",
            "stop_reason": "completed",
            "_id": 4,
            "session_id": session_id,
        }

    # ---- context budget (optional, not required) ----

    def get_context_budget(self, *, session_id: str) -> dict:
        return {"used": 100, "limit": 8000}


def test_cli_repl_http_chain_recovers_after_retryable_error() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    def _input_fn(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    exit_code = run_cli(
        ["--base-url", "http://testserver", "--mode", "remote"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=_input_fn,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "State: completed" in text
    assert "ok" in text
