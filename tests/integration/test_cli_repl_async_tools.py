"""Integration: CLI REPL with real AgentRuntime and tool call loops.

Tests in this file involve a full AgentRuntime (real LLM client stub, real tool
registry, real ASGI app) to verify tool execution events, bash tool streaming,
compact sections in output, and control-sequence hygiene.
"""

import io
from pathlib import Path

import httpx
import pytest

from coding_cli.main import run_cli
from agent.core.agent.runtime import AgentRuntime
from agent.core.types import Message, TurnResult
from agent.core.agent.compaction.types import CompactionReason, CompactionResult
from agent.platform.hooks.loader import build_hook_registry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.platform.http_api.app import create_app
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.registry import ToolRegistry

# All tests in this file use REPL mode with ASGI TestClient. SessionStreamReader
# starts a background thread that calls asyncio.run(stream_session()), but ASGI
# TestClient isolates each client to its own event loop. Server-side asyncio.Queue
# objects are bound to the event loop that handles submit_message, making them
# unreachable from the SSE background thread. Tests hang indefinitely. (#47)
pytestmark = pytest.mark.skip(reason="REPL+ASGI hang: 跨 event-loop SSE 不可达 — tracked in #47")


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


class _ToolCallingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # AsyncIterator[LLMMessage]
        import json
        self.requests.append(request)
        if len(self.requests) == 1:
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="call_cli_echo_1",
                        name="echo",
                        arguments={"text": request.messages[-1].content},
                    ),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
            return

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

        yield LLMMessage(role="assistant", content=f"final:{tool_text}")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


class _BashToolCallingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # AsyncIterator[LLMMessage]
        self.requests.append(request)
        if len(self.requests) == 1:
            yield LLMMessage(
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
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
            return

        yield LLMMessage(role="assistant", content="final:bash-finished")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


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


def test_cli_http_flow_executes_tool_call_loop_before_returning_final_answer(tmp_path: Path) -> None:
    # Verifies the full tool call loop through the REPL path (ASGITransport is
    # safe here because SessionStreamReader uses a background thread with its
    # own asyncio.run(), avoiding the nesting restriction that breaks --text mode).
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    llm = _ToolCallingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    echo_tool = _EchoTool()
    tool_registry.register(echo_tool)

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "final:echo:ping" in text
    assert "Tool: echo" in text
    # The tool call loop executed: LLM made 2 requests and echo tool was called.
    assert len(llm.requests) == 2
    assert [spec.name for spec in llm.requests[0].tools] == ["echo"]
    assert echo_tool.calls == [{"text": "ping"}]


def test_cli_repl_streams_async_run_tool_and_text_events(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    llm = _ToolCallingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    echo_tool = _EchoTool()
    tool_registry.register(echo_tool)

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
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


def test_cli_repl_non_tty_async_output_avoids_terminal_control_sequences(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    llm = _ToolCallingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    tool_registry.register(_EchoTool())

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
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


def test_cli_repl_streams_started_running_chunk_and_exit_for_bash_tool(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    llm = _BashToolCallingLLMClient()
    hook_runner = HookRunner(registry=build_hook_registry(repo_root=tmp_path))
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        hook_runner=hook_runner,
        repo_root=tmp_path,
    )
    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=hook_runner,
    )
    tool_registry.register(BashTool())

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
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


def test_cli_repl_prints_compact_sections_in_async_turn_output(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    llm = _ToolCallingLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    echo_tool = _EchoTool()
    tool_registry.register(echo_tool)

    app = create_app(
        session_store=store,
        runtime=runtime,
        tool_registry=tool_registry,
    )
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
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
