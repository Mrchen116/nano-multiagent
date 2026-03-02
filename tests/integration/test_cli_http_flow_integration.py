import io
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.agent.compaction.types import CompactionReason, CompactionResult
from nano_multiagent.cli.main import run_cli
from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from nano_multiagent.server.app import create_app
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.base import LoadedSession, SessionStore
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.registry import ToolRegistry


class _ScriptedReplInputReader:
    def __init__(self, scripted_lines: list[list[str]]) -> None:
        self._line_iterator = iter(scripted_lines)
        self.render = io.StringIO()

    def read_line(self, prompt: str, history: tuple[str, ...] | list[str]) -> str:
        del history
        keys = next(self._line_iterator)
        key_iterator = iter(keys)

        def _read_key() -> str | None:
            try:
                return next(key_iterator)
            except StopIteration:
                return None

        return cli_commands._read_interactive_line(
            prompt=prompt,
            history=(),
            key_reader=_read_key,
            out=self.render,
        )


class _RuntimeStub:
    def run(self, session_id: str, parts, *, stream: bool = False):
        del stream
        text = ""
        for item in parts:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                break
        return TurnResult(
            session_id=session_id,
            turn_id="turn_cli",
            messages=(
                Message(
                    message_id="msg_cli",
                    role="assistant",
                    content=f"cli:{text}",
                ),
            ),
            completed=True,
            stop_reason="stop",
        )

    def compact(self, session_id: str) -> CompactionResult:
        return CompactionResult(
            reason=CompactionReason.MANUAL,
            entry_id="entry_cli_compact",
            first_kept_event_id="evt_cli_kept",
            summary="cli compacted",
            dropped_event_ids=("evt_cli_drop",),
            kept_event_ids=("evt_cli_kept",),
        )


class _InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.snapshots: dict[str, dict[str, object]] = {}

    def append_event(self, session_id: str, entry: object) -> None:
        self.events.append((session_id, entry))

    def load_session(self, session_id: str) -> LoadedSession | None:
        session_events = tuple(entry for sid, entry in self.events if sid == session_id)
        if not session_events and session_id not in self.snapshots:
            return None
        return LoadedSession(
            session_id=session_id,
            events=session_events,
            snapshot=self.snapshots.get(session_id),
        )

    def save_snapshot(self, session_id: str, snapshot: dict[str, object]) -> None:
        self.snapshots[session_id] = snapshot


class _ToolCallingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_cli_echo_1",
                            name="echo",
                            arguments={"text": request.messages[-1].content},
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            )

        tool_text = ""
        if request.messages:
            tail = request.messages[-1]
            if tail.role == "tool":
                payload = json.loads(tail.content)
                if isinstance(payload, dict):
                    output = payload.get("output")
                    if isinstance(output, dict):
                        raw_text = output.get("text")
                        if isinstance(raw_text, str):
                            tool_text = raw_text

        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"final:{tool_text}"),
            finish_reason="stop",
        )


class _EchoTool:
    name = "echo"
    description = "Echo user text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def run(self, args, ctx):  # noqa: ANN001
        del ctx
        text = str(args["text"])
        self.calls.append({"text": text})
        return {"text": f"echo:{text}"}


class _ModelTimeoutRuntime:
    def run(self, session_id: str, parts, *, stream: bool = False) -> TurnResult:  # noqa: ANN001
        del session_id
        del parts
        del stream
        raise ModelError("timed out waiting for upstream; root_cause=connect ETIMEDOUT", retryable=True)


def test_cli_runs_http_flow_against_asgi_app() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    create_out = io.StringIO()
    create_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
            "create-session",
            "--title",
            "cli-session",
        ],
        stdout=create_out,
        client_factory=client_factory,
    )

    assert create_code == 0
    created = json.loads(create_out.getvalue())
    session_id = created["session_id"]

    send_out = io.StringIO()
    send_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
            "send-message",
            "--session-id",
            session_id,
            "--text",
            "ping",
        ],
        stdout=send_out,
        client_factory=client_factory,
    )

    assert send_code == 0
    payload = json.loads(send_out.getvalue())
    assert payload["session_id"] == session_id
    assert payload["message"]["content"] == "cli:ping"


def test_cli_http_flow_executes_tool_call_loop_before_returning_final_answer() -> None:
    store = _InMemorySessionStore()
    llm = _ToolCallingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=Path.cwd(),
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    echo_tool = _EchoTool()
    tool_registry.register(echo_tool)

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
        auth_token="test-token",
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    create_out = io.StringIO()
    create_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
            "create-session",
        ],
        stdout=create_out,
        client_factory=client_factory,
    )
    assert create_code == 0
    session_id = json.loads(create_out.getvalue())["session_id"]

    send_out = io.StringIO()
    send_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
            "send-message",
            "--session-id",
            session_id,
            "--text",
            "ping",
        ],
        stdout=send_out,
        client_factory=client_factory,
    )

    assert send_code == 0
    payload = json.loads(send_out.getvalue())
    assert payload["stop_reason"] != "tool_registry_unavailable"
    assert payload["message"]["content"] == "final:echo:ping"
    assert len(llm.requests) == 2
    assert [spec.name for spec in llm.requests[0].tools] == ["echo"]
    assert echo_tool.calls == [{"text": "ping"}]


def test_cli_timeout_error_surfaces_root_cause_and_trace_id_evidence() -> None:
    app = create_app(runtime=_ModelTimeoutRuntime(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["hi", "/exit"])
    exit_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
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
    assert "run failed: {'code': 'run_execution_failed'" in text
    assert "root_cause=connect ETIMEDOUT" in text
    assert "NANO_MULTIAGENT_API_TIMEOUT_SECONDS" in text


def test_cli_repl_flow_supports_tools_and_compact_commands() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/tools", "/compact", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:ping" in text
    assert "Tools for session" in text
    assert "Compaction for session" in text


def test_cli_repl_inline_editing_keys_submit_edited_text() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )
    output = io.StringIO()
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:helXlo" in text


def test_cli_repl_streams_async_run_tool_and_text_events() -> None:
    store = _InMemorySessionStore()
    llm = _ToolCallingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=Path.cwd(),
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    echo_tool = _EchoTool()
    tool_registry.register(echo_tool)

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
        auth_token="test-token",
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "[run " in text
    assert "status=completed" in text
    assert "[tool echo] start" in text
    assert "[tool echo] output=echo:ping" in text
    assert "[text] final:echo:ping" in text


def test_cli_repl_flow_supports_history_listing() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/history", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "History for session" in text
    assert "user: ping" in text
    assert "assistant: cli:ping" in text


def test_cli_repl_rejects_invalid_command_arguments() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new extra", "/tools now", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: command /new does not accept arguments." in text
    assert "Suggestion: try /new." in text
    assert "Usage: /new" in text
    assert "Error: command /tools does not accept arguments." in text
    assert "Suggestion: try /tools." in text
    assert "Usage: /tools" in text


class _ManagedServerRecorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")


@pytest.mark.parametrize("mode", ["managed", "remote"])
def test_cli_repl_flow_supports_key_commands_in_both_modes(mode: str) -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)
    managed_server = _ManagedServerRecorder()

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/tools", "/compact", "/history", "/exit"])
    exit_code = run_cli(
        ["--mode", mode, "--base-url", "http://testserver", "--token", "test-token"],
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


@pytest.mark.parametrize("mode", ["managed", "remote"])
def test_cli_llm_config_get_set_flow_supports_remote_and_managed_modes(mode: str) -> None:
    app = FastAPI()
    state: dict[str, object] = {
        "provider": "openai_compat",
        "model": "codexOAuth:gpt-5.2-codex",
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
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    set_out = io.StringIO()
    set_exit = run_cli(
        [
            "--mode",
            mode,
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
            "llm-config",
            "set",
            "--provider",
            "anthropic",
            "--model",
            "claude-3-5-sonnet-20241022",
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
    assert set_payload["model"] == "claude-3-5-sonnet-20241022"
    assert set_payload["base_url"] == "http://127.0.0.1:4100"
    assert set_payload["timeout_seconds"] == 66.0

    get_out = io.StringIO()
    get_exit = run_cli(
        ["--mode", mode, "--base-url", "http://testserver", "--token", "test-token", "llm-config", "get"],
        stdout=get_out,
        client_factory=client_factory,
        managed_server_factory=lambda _: managed_server,
    )
    assert get_exit == 0
    get_payload = json.loads(get_out.getvalue())
    assert get_payload["provider"] == "anthropic"
    assert get_payload["model"] == "claude-3-5-sonnet-20241022"
    assert get_payload["base_url"] == "http://127.0.0.1:4100"
    assert get_payload["timeout_seconds"] == 66.0

    if mode == "managed":
        assert managed_server.events == ["start", "stop", "start", "stop"]
    else:
        assert managed_server.events == []
