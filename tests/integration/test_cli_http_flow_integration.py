import io
import json
from pathlib import Path
import time

import httpx
import pytest
from fastapi import FastAPI

from coding_cli.input import repl_commands, repl_input
from coding_cli import commands as cli_commands
from coding_cli.client import ServerClient
from agent.core.agent.runtime import AgentRuntime
from agent.core.agent.compaction.types import CompactionReason, CompactionResult
from coding_cli.main import run_cli
from agent.core.errors import ModelError
from agent.core.types import Message, TurnResult
from agent.platform.hooks.loader import build_hook_registry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from agent.platform.http_api.app import create_app
from agent.core.session.manager import SessionManager
from agent.core.session.store import LoadedSession, SessionStore
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.registry import ToolRegistry


class _ScriptedReplInputReader:
    def __init__(self, scripted_lines: list[list[str]]) -> None:
        self._line_iterator = iter(scripted_lines)
        self.render = io.StringIO()

    def read_line(self, prompt: str, history: tuple[str, ...] | list[str]) -> str:
        keys = next(self._line_iterator)
        key_iterator = iter(keys)

        def _read_key() -> str | None:
            try:
                return next(key_iterator)
            except StopIteration:
                return None

        return repl_input.read_interactive_line(
            prompt=prompt,
            history=tuple(history),
            key_reader=_read_key,
            out=self.render,
            command_suggestions=repl_commands.REPL_COMMANDS,
        )


class _RuntimeStub:
    def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None):
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


class _SlowFirstTurnRuntime(_RuntimeStub):
    def __init__(self) -> None:
        self._turn_count = 0

    def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None):
        self._turn_count += 1
        if self._turn_count == 1:
            time.sleep(0.2)
        return super().run(session_id=session_id, parts=parts, stream=stream, run_id=run_id)


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


class _BashToolCallingLLMClient:
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
                            call_id="call_cli_bash_1",
                            name="bash",
                            arguments={
                                "command": (
                                    "python -c \"import sys,time;"
                                    "print('out-line');sys.stdout.flush();"
                                    "time.sleep(0.2);"
                                    "print('err-line', file=sys.stderr);sys.stderr.flush()\""
                                )
                            },
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            )

        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="final:bash-finished"),
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
    def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None) -> TurnResult:  # noqa: ANN001
        del session_id
        del parts
        del stream
        raise ModelError("timed out waiting for upstream; root_cause=connect ETIMEDOUT", retryable=False)


class _AsyncMethodsMustNotBeCalledServerClient(ServerClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        del session_id, text
        raise AssertionError("send-message command must not call send_message_async")

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del session_id, max_events, timeout_seconds
        raise AssertionError("send-message command must not stream repl events")

    def get_run(self, *, run_id: str) -> dict[str, object]:
        del run_id
        raise AssertionError("send-message command must not fetch async run state")


def test_cli_runs_http_flow_against_asgi_app() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

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


def test_cli_send_message_command_keeps_single_json_stdout_contract_with_async_capable_client() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        return _AsyncMethodsMustNotBeCalledServerClient(config=config, transport=transport)

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
    raw = send_out.getvalue().strip()
    assert "\n" not in raw
    payload = json.loads(raw)
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
        from coding_cli.client import ServerClient

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
        from coding_cli.client import ServerClient

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
    assert "Assistant: (empty)" in text
    assert "Error:" in text
    assert "layer=runtime" in text
    assert "run failed: {'code': 'run_execution_failed'" in text
    assert "root_cause=connect ETIMEDOUT" in text
    assert "NANO_MULTIAGENT_API_TIMEOUT_SECONDS" in text


def test_cli_repl_flow_supports_tools_and_compact_commands() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

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


def test_cli_repl_compact_refreshes_context_budget_snapshot() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/compact", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Context budget: " in text
    assert "Context budget (after /compact): " in text


def test_cli_repl_inline_editing_keys_submit_edited_text() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

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


def test_cli_repl_history_recall_allows_second_submit_after_editing() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["p", "i", "n", "g", "\n"],
            ["\x1b[A", "\x1b[D", "\x1b[D", "X", "\n"],
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
    assert "cli:ping" in text
    assert "cli:piXng" in text


def test_cli_repl_full_chain_edit_history_and_compact_budget_state() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"],
            ["\x1b[A", "\x1b[C", "!", "\n"],
            ["/", "c", "o", "m", "p", "a", "c", "t", "\n"],
            ["/", "h", "i", "s", "t", "o", "r", "y", " ", "4", "\n"],
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
    assert "cli:helXlo!" in text
    assert "History for session" in text
    assert "user: helXlo!" in text
    assert "Compaction for session" in text
    assert "Context budget (after /compact):" in text


def test_cli_repl_up_recalls_previous_command_line() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["/", "h", "e", "l", "p", "\n"],
            ["\x1b[A", "\n"],
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
    assert output.getvalue().count("Commands: /help /new /use <session_id>") == 2


def test_cli_repl_slash_menu_selects_command_and_executes_it() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "\x1b[B", "\n", "\n"],
            ["/", "s", "e", "s", "s", "i", "o", "n", "\n"],
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
    assert "Error: unknown command '/'" not in text
    assert "Active session: sess_" in text
    assert '{"session_id":' not in text
    assert "Commands ↓ " not in text


def test_cli_repl_session_transitions_render_active_copy_without_json() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["hello http", "/new", "/use sess_manual", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Started new session sess_") == 2
    assert text.count("Active session: sess_") >= 2
    assert "Switched to session sess_manual." in text
    assert "Active session: sess_manual." in text
    assert '{"session_id":' not in text
    assert '"session_id":' not in text


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
        from coding_cli.client import ServerClient

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
    assert "Assistant:" in text
    assert "State: completed | stop=stop | run=run_" in text
    assert "Tool: echo start args=ping" in text
    assert "Tool echo start args=ping" not in text
    assert "Tool: echo output=echo:ping" in text
    assert "Usage:" in text
    assert "[status]" not in text
    assert "[tool]" not in text
    assert "[usage]" not in text
    assert "final:echo:ping" in text


def test_cli_repl_non_tty_async_output_avoids_terminal_control_sequences() -> None:
    store = _InMemorySessionStore()
    llm = _ToolCallingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=Path.cwd(),
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    tool_registry.register(_EchoTool())

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
        auth_token="test-token",
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

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
    assert "Tool: echo start args=ping" in text
    assert "State: completed" in text
    assert "\r" not in text
    assert "\x1b[" not in text


def test_cli_repl_streams_started_running_chunk_and_exit_for_bash_tool() -> None:
    store = _InMemorySessionStore()
    llm = _BashToolCallingLLMClient()
    hook_runner = HookRunner(registry=build_hook_registry(repo_root=Path.cwd()))
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        hook_runner=hook_runner,
        repo_root=Path.cwd(),
    )
    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=Path.cwd()),
        hook_runner=hook_runner,
    )
    tool_registry.register(BashTool())

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
        auth_token="test-token",
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

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
    assert "Tool: bash start args=" in text
    assert "Tool: bash started" in text
    assert "Tool: bash running" not in text
    assert "Tool: bash chunk stdout" not in text
    assert "Tool: bash chunk stderr" not in text
    assert "Tool: bash chunk stdout" not in text
    assert "Tool: bash chunk stderr" not in text
    assert text.count("Tool: bash exit code=0") == 1
    assert text.index("Tool: bash started") < text.index("State:")
    assert "final:bash-finished" in text


def test_cli_repl_prints_compact_sections_in_async_turn_output() -> None:
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
        from coding_cli.client import ServerClient

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
    assert "Assistant:" in text
    assert "State: completed" in text
    assert "Tool:" in text
    assert "Usage:" in text
    assert "[status]" not in text
    assert "[tool]" not in text
    assert "[usage]" not in text
    assert '"run_id": "run_' not in text


def test_cli_repl_allows_queueing_next_input_while_previous_async_run_is_running() -> None:
    app = create_app(runtime=_SlowFirstTurnRuntime(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Queued message #1" in text
    assert text.count("run=") >= 2


def test_cli_repl_multiline_paste_submits_single_async_message() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        [
            ["/", "\x1b[B", "\n", "\n"],
            ["f", "i", "r", "s", "t", "\nsecond\n"],
            ["/", "\x1b[A", "\n", "\n"],
        ]
    )
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:first\nsecond" in text
    assert "Queued message #1" not in text
    assert text.count("run=") == 1


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

    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/history", "/exit"])
    monkeypatch.setattr(app_commands, "ReplRunQueue", _FalseTimeoutAfterDrainQueue)
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
    assert "Timed out waiting for in-flight messages; skipping /history for now." not in text


def test_cli_repl_flow_supports_history_listing() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

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
        from coding_cli.client import ServerClient

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
    assert "Layer: input" in text
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
        from coding_cli.client import ServerClient

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


def test_cli_repl_managed_exit_discards_queued_messages_and_stops_server() -> None:
    app = create_app(runtime=_SlowFirstTurnRuntime(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)
    managed_server = _ManagedServerRecorder()

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/exit"])
    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        managed_server_factory=lambda _: managed_server,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert managed_server.events == ["start", "stop"]
    assert text.count("run=") == 1
    assert "Waiting for 2 in-flight message(s) before exit." not in text
    assert "cli:second" not in text


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
        from coding_cli.client import ServerClient

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
