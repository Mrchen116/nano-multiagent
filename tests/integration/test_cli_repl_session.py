"""Integration: CLI REPL session management, commands, and managed/remote modes.

Covers /tools, /compact, /history, queueing during async runs, managed-server
lifecycle (start/stop), and llm-config get/set commands in both remote and
managed modes.
"""

import io
import json
import time

import httpx
import pytest
from fastapi import FastAPI

from coding_cli import commands as cli_commands
from coding_cli.main import run_cli
from agent.core.types import Message, TurnResult
from agent.core.agent.compaction.types import CompactionReason, CompactionResult
from agent.platform.http_api.app import create_app
from integration.conftest import ASGIClient

# REPL tests require a single asyncio event-loop shared between the REPL loop
# and the SSE background reader. ASGI TestClient uses isolated event-loops per
# client instance, so submit_message and stream_session cannot share server-side
# queues. Skip until a test-server-based fixture is available. (#47)
_REPL_HANG_SKIP = pytest.mark.skip(
    reason="REPL+ASGI hang: 跨 event-loop SSE 不可达 — tracked in #47"
)


class _RuntimeStub:
    async def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None, controller=None, parent_session_id=None, origin=None):
        del stream
        text = ""
        for item in parts:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                break
        return TurnResult(
            session_id=session_id,
            turn_id="turn_cli",
            messages=(Message(message_id="msg_cli", role="assistant", content=f"cli:{text}"),),
            completed=True,
            stop_reason="stop",
        )

    async def compact(self, session_id: str) -> CompactionResult:
        return CompactionResult(
            reason=CompactionReason.MANUAL,
            entry_id="entry_cli_compact",
            first_kept_event_id="evt_cli_kept",
            summary="cli compacted",
            dropped_event_ids=("evt_cli_drop",),
            kept_event_ids=("evt_cli_kept",),
        )


class _SlowFirstTurnRuntime(_RuntimeStub):
    def __init__(self) -> None:
        self._turn_count = 0

    async def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None, controller=None, parent_session_id=None, origin=None):
        self._turn_count += 1
        if self._turn_count == 1:
            time.sleep(0.2)
        return await super().run(session_id=session_id, parts=parts, stream=stream, run_id=run_id)


class _ManagedServerRecorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")


@_REPL_HANG_SKIP
def test_cli_repl_flow_supports_tools_and_compact_commands() -> None:
    app = create_app(runtime=_RuntimeStub())

    def client_factory(_config):
        return ASGIClient(app)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/tools", "/compact", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:ping" in text
    assert "Tools for session" in text
    assert "Compaction for session" in text


@_REPL_HANG_SKIP
def test_cli_repl_compact_refreshes_context_budget_snapshot() -> None:
    app = create_app(runtime=_RuntimeStub())

    def client_factory(_config):
        return ASGIClient(app)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/compact", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Context budget: " in text
    assert "Context budget (after /compact): " in text


@_REPL_HANG_SKIP
def test_cli_repl_allows_queueing_next_input_while_previous_async_run_is_running() -> None:
    app = create_app(runtime=_SlowFirstTurnRuntime())

    def client_factory(_config):
        return ASGIClient(app)

    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Queued message #1" in text
    assert text.count("run=") == 1
    assert "cli:second" not in text


@_REPL_HANG_SKIP
def test_cli_repl_history_wait_barrier_ignores_false_timeout_after_drain(monkeypatch) -> None:
    from coding_cli import commands as app_commands

    class _FalseTimeoutAfterDrainQueue:
        def __init__(self, *, process_message, on_worker_error=None) -> None:  # noqa: ANN001
            del on_worker_error
            self._process_message = process_message
            self._pending: list[object] = []

        def enqueue(self, *, session_id: str, text: str) -> int:
            backlog_before = len(self._pending)
            self._pending.append(app_commands.QueuedReplMessage(session_id=session_id, text=text))
            return backlog_before

        def backlog_size(self) -> int:
            return len(self._pending)

        def wait_for_drain(self, *, timeout_seconds: float | None = None) -> bool:
            del timeout_seconds
            while self._pending:
                item = self._pending.pop(0)
                self._process_message(item)
            return False

        def close(self, *, wait_for_drain: bool, drain_timeout_seconds: float | None = None) -> bool:
            del wait_for_drain, drain_timeout_seconds
            return True

    app = create_app(runtime=_RuntimeStub())

    def client_factory(_config):
        return ASGIClient(app)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/history", "/exit"])
    monkeypatch.setattr(app_commands, "ReplRunQueue", _FalseTimeoutAfterDrainQueue)
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "History for session" in text
    assert "user: ping" in text
    assert "assistant: cli:ping" in text
    assert "Timed out waiting for in-flight messages; skipping /history for now." not in text


@_REPL_HANG_SKIP
def test_cli_repl_flow_supports_history_listing() -> None:
    app = create_app(runtime=_RuntimeStub())

    def client_factory(_config):
        return ASGIClient(app)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/history", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "History for session" in text
    assert "user: ping" in text
    assert "assistant: cli:ping" in text


@pytest.mark.parametrize("mode", ["managed", "remote"])
@_REPL_HANG_SKIP
def test_cli_repl_flow_supports_key_commands_in_both_modes(mode: str) -> None:
    app = create_app(runtime=_RuntimeStub())
    managed_server = _ManagedServerRecorder()

    def client_factory(_config):
        return ASGIClient(app)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/tools", "/compact", "/history", "/exit"])
    exit_code = run_cli(
        ["--mode", mode, "--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        managed_server_factory=lambda _: managed_server,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:ping" in text
    assert "Tools for session" in text
    assert "Compaction for session" in text
    assert "History for session" in text
    if mode == "managed":
        assert managed_server.events == ["start", "stop"]
    else:
        assert managed_server.events == []


@_REPL_HANG_SKIP
def test_cli_repl_managed_exit_discards_queued_messages_and_stops_server() -> None:
    app = create_app(runtime=_SlowFirstTurnRuntime())
    managed_server = _ManagedServerRecorder()

    def client_factory(_config):
        return ASGIClient(app)

    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/exit"])
    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        managed_server_factory=lambda _: managed_server,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert managed_server.events == ["start", "stop"]
    assert "Waiting for 2 in-flight message(s) before exit." not in text
    assert "cli:second" not in text
    assert text.count("Queued message #1") == 1


@pytest.mark.parametrize("mode", ["managed", "remote"])
def test_cli_llm_config_get_set_flow_supports_remote_and_managed_modes(mode: str) -> None:
    app = FastAPI()
    state: dict[str, object] = {
        "provider": "openai_compat",
        "model": "codex_oauth:gpt-5.5",
        "base_url": "http://127.0.0.1:4000",
        "timeout_seconds": 30.0,
        "api_key": None,
    }

    @app.get("/v1/llm-config")
    def get_llm_config() -> dict[str, object]:
        return {
            "provider": state["provider"],
            "model": state["model"],
            "base_url": state["base_url"],
            "timeout_seconds": state["timeout_seconds"],
            "api_key_configured": bool(state["api_key"]),
        }

    @app.patch("/v1/llm-config")
    def patch_llm_config(payload: dict[str, object]) -> dict[str, object]:
        for key in ("provider", "model", "base_url", "timeout_seconds", "api_key"):
            if key in payload:
                state[key] = payload[key]
        return {
            "provider": state["provider"],
            "model": state["model"],
            "base_url": state["base_url"],
            "timeout_seconds": state["timeout_seconds"],
            "api_key_configured": bool(state["api_key"]),
        }

    transport = httpx.ASGITransport(app=app)
    managed_server = _ManagedServerRecorder()

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    set_out = io.StringIO()
    set_exit = run_cli(
        [
            "--mode",
            mode,
            "--base-url",
            "http://testserver",
            "llm-config",
            "set",
            "--provider",
            "anthropic",
            "--model",
            "kimiCoding:K2.6",
            "--base-url",
            "http://127.0.0.1:4100",
            "--timeout-seconds",
            "66",
        ],
        stdout=set_out,
        client_factory=client_factory,
        managed_server_factory=lambda _: managed_server,
    )
    assert set_exit == 0
    set_payload = json.loads(set_out.getvalue())
    assert set_payload["provider"] == "anthropic"
    assert set_payload["model"] == "kimiCoding:K2.6"
    assert set_payload["base_url"] == "http://127.0.0.1:4100"
    assert set_payload["timeout_seconds"] == 66.0

    get_out = io.StringIO()
    get_exit = run_cli(
        ["--mode", mode, "--base-url", "http://testserver", "llm-config", "get"],
        stdout=get_out,
        client_factory=client_factory,
        managed_server_factory=lambda _: managed_server,
    )
    assert get_exit == 0
    get_payload = json.loads(get_out.getvalue())
    assert get_payload["provider"] == "anthropic"
    assert get_payload["model"] == "kimiCoding:K2.6"
    assert get_payload["base_url"] == "http://127.0.0.1:4100"
    assert get_payload["timeout_seconds"] == 66.0

    if mode == "managed":
        assert managed_server.events == ["start", "stop", "start", "stop"]
    else:
        assert managed_server.events == []
