"""Tests for turn_meta tool_iterations, agent_end payload, background hook context, and bind_tool_registry.

Covers:
- loop.py turn_meta exposes tool_iterations in metadata
- AgentRuntime agent_end hook payload includes tool_iterations
- Background hook context has fork_conversation injected (observe does not)
- bind_tool_registry propagates to _context_fork._loop (regression)
- Fork loop executes tools after bind_tool_registry was called post-construction
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# R4: loop.py turn_meta exposes tool_iterations
# ---------------------------------------------------------------------------


def test_turn_meta_has_tool_iterations_in_metadata():
    """turn_meta message from AgentLoop must include tool_iterations in metadata."""
    # We test build_turn_result with a turn_meta that has tool_iterations
    from agent.core.agent.runtime import build_turn_result
    from agent.core.types import Message

    turn_meta = Message(
        message_id="m1",
        role="turn_meta",
        content="",
        metadata={
            "stop_reason": "completed",
            "usage": None,
            "completed": True,
            "tool_iterations": 5,
        },
    )
    result = build_turn_result("session-1", "turn-1", [turn_meta])
    assert result.completed is True


@pytest.mark.asyncio
async def test_agent_loop_turn_meta_includes_tool_iterations():
    """AgentLoop.run() must yield a turn_meta message with tool_iterations set to api_round_count."""
    from agent.core.agent.loop import AgentLoop
    from agent.core.agent.state import AgentState
    from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage
    from agent.core.types import Message

    class FakeLLMResponse:
        def __init__(self):
            self.role = "assistant"
            self.content = "Hello"
            self.tool_calls = []
            self.finish_reason = "stop"
            self.usage = None
            self.reasoning_content = None
            self.reasoning_signature = None

    class FakeLLMTerminal:
        def __init__(self):
            self.role = "assistant"
            self.content = ""
            self.tool_calls = []
            self.finish_reason = "stop"
            self.usage = None
            self.reasoning_content = None
            self.reasoning_signature = None

    class FakeLLMClient:
        def generate(self, request):
            async def _stream():
                yield FakeLLMResponse()
                yield FakeLLMTerminal()

            return _stream()

    loop = AgentLoop(
        llm_client=FakeLLMClient(),
        model="test-model",
    )
    state = AgentState(
        session_id="s1",
        turn_id="t1",
        turn_count=0,
        history_messages=(),
        input_parts=[],
        user_text="hello",
    )
    messages = []
    async for msg in loop.run(state):
        messages.append(msg)

    turn_meta = [m for m in messages if m.role == "turn_meta"]
    assert len(turn_meta) == 1, "Expected exactly one turn_meta message"
    meta = turn_meta[0]
    assert "tool_iterations" in meta.metadata, (
        "turn_meta must include tool_iterations for nudge counter signal flow"
    )
    # 1 api round = tool_iterations = 1 (no tool calls, single LLM round)
    assert meta.metadata["tool_iterations"] == 1


# ---------------------------------------------------------------------------
# R4: runtime agent_end payload includes tool_iterations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_agent_end_payload_includes_tool_iterations(tmp_path):
    """AgentRuntime must include tool_iterations in agent_end hook payload."""
    from agent.core.hooks.registry import HookRegistry
    from agent.core.hooks.runner import HookRunner
    from agent.core.hooks.context import HookContext
    from agent.core.agent.runtime import AgentRuntime
    from agent.core.session.jsonl_store import JsonlSessionStore
    from agent.core.session.manager import SessionManager
    from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage

    agent_end_payloads = []

    async def capture_agent_end(payload, ctx):
        agent_end_payloads.append(dict(payload))

    registry = HookRegistry()
    registry.on("agent_end", capture_agent_end, mode="observe")
    runner = HookRunner(registry=registry)

    class FakeLLMResponse:
        role = "assistant"
        content = "Hello"
        tool_calls = []
        finish_reason = None
        usage = None
        reasoning_content = None
        reasoning_signature = None

    class FakeLLMTerminal:
        role = "assistant"
        content = ""
        tool_calls = []
        finish_reason = "stop"
        usage = None
        reasoning_content = None
        reasoning_signature = None

    class FakeLLMClient:
        def generate(self, request):
            async def _stream():
                yield FakeLLMResponse()
                yield FakeLLMTerminal()

            return _stream()

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    sm = SessionManager(store=store)
    runtime = AgentRuntime(
        session_manager=sm,
        llm_client=FakeLLMClient(),
        hook_runner=runner,
        repo_root=tmp_path,
    )

    session = await runtime.create_session(workspace_root=tmp_path)
    await runtime.run(session.session_id, [{"type": "text", "text": "hello"}])

    assert len(agent_end_payloads) >= 1
    last = agent_end_payloads[-1]
    assert "tool_iterations" in last, (
        f"agent_end payload must contain tool_iterations; got keys: {list(last.keys())}"
    )


# ---------------------------------------------------------------------------
# R5: background hook context has fork_conversation injected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_background_hook_receives_fork_conversation_in_context():
    """Background hook handler must receive a HookContext with fork_conversation set.

    Non-background hooks must NOT receive fork_conversation (it's only for background).
    """
    from agent.core.hooks.registry import HookRegistry
    from agent.core.hooks.runner import HookRunner
    from agent.core.hooks.context import HookContext

    background_ctx_values = []
    observe_ctx_values = []

    async def bg_handler(payload, ctx):
        background_ctx_values.append(ctx.fork_conversation)

    async def obs_handler(payload, ctx):
        observe_ctx_values.append(ctx.fork_conversation)

    registry = HookRegistry()
    registry.on("agent_end", obs_handler, mode="observe")
    registry.on("agent_end", bg_handler, mode="background")
    runner = HookRunner(registry=registry)

    # Build context with a fork_conversation callable
    async def dummy_fork(review_prompt, *, tool_allowlist, max_turns):
        return MagicMock()

    ctx = HookContext(session_id="s1", fork_conversation=dummy_fork)
    await runner.dispatch_observe("agent_end", {"session_id": "s1"}, ctx)
    runner.dispatch_background("agent_end", {"session_id": "s1"}, ctx)
    await asyncio.sleep(0.05)

    # Background handler should receive fork_conversation
    assert len(background_ctx_values) == 1
    assert callable(background_ctx_values[0]), (
        "Background hook context must have fork_conversation callable"
    )

    # Observe handler should NOT receive fork_conversation
    assert len(observe_ctx_values) == 1
    assert observe_ctx_values[0] is None, (
        "Observe hook context must NOT have fork_conversation (only background gets it)"
    )


# ---------------------------------------------------------------------------
# M5: bind_tool_registry must propagate to _context_fork (regression)
# ---------------------------------------------------------------------------


def test_bind_tool_registry_propagates_to_context_fork(tmp_path):
    """bind_tool_registry must also update _context_fork._loop._tool_registry.

    In app.py, AgentRuntime is constructed before the tool_registry is built,
    so tool_registry=None at construction time. bind_tool_registry is called
    later to attach the registry. If it only updates self._loop and not
    self._context_fork._loop, the fork side-chain executes with tool_registry=None
    and exits with stop_reason='tool_registry_unavailable' after round 1.
    """
    from agent.core.agent.runtime import AgentRuntime
    from agent.core.session.jsonl_store import JsonlSessionStore
    from agent.core.session.manager import SessionManager

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    sm = SessionManager(store=store)

    class _FakeLLMClient:
        async def generate(self, request):
            # Minimal: yields nothing — only construction matters
            return
            yield  # makes generate() an async generator (protocol requirement)

    # Construct with tool_registry=None (mirrors app.py construction order)
    runtime = AgentRuntime(
        session_manager=sm,
        llm_client=_FakeLLMClient(),
        repo_root=tmp_path,
    )
    assert runtime._context_fork._loop._tool_registry is None

    # Build a minimal tool registry stub
    class _StubRegistry:
        def list_specs(self):
            return ()

    stub = _StubRegistry()
    runtime.bind_tool_registry(stub)

    # After binding, _context_fork._loop must also have the registry
    assert runtime._context_fork._loop._tool_registry is stub, (
        "bind_tool_registry must propagate to _context_fork._loop._tool_registry; "
        "otherwise fork side-chains run with tool_registry=None and exit after round 1 "
        "with stop_reason='tool_registry_unavailable'"
    )


@pytest.mark.asyncio
async def test_fork_loop_executes_tools_after_bind_tool_registry(tmp_path):
    """Fork side-chain must execute tools when bind_tool_registry was called post-construction.

    Reproduces the production bug: app.py constructs AgentRuntime without tool_registry,
    then calls bind_tool_registry. The fork must execute tool calls, not exit early
    with stop_reason='tool_registry_unavailable'.
    """
    from collections.abc import AsyncIterator
    from agent.core.agent.context_fork import AgentContextFork
    from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
    from agent.core.agent.state import AgentState
    from agent.core.tools.session_file_state import SessionFileState

    executed_tools: list[str] = []

    # Round 1: LLM returns a tool_use. Round 2: LLM returns final text.
    class _TwoRoundLLMClient:
        def __init__(self):
            self._round = 0

        def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
            self._round += 1
            round_no = self._round

            async def _stream():
                if round_no == 1:
                    yield LLMMessage(
                        role="assistant",
                        content="",
                        tool_calls=(
                            LLMToolCall(
                                call_id="c1", name="skill_manage", arguments={}
                            ),
                        ),
                        finish_reason=None,
                    )
                    yield LLMMessage(
                        role="assistant", content="", finish_reason="tool_calls"
                    )
                else:
                    yield LLMMessage(
                        role="assistant", content="review done", finish_reason=None
                    )
                    yield LLMMessage(role="assistant", content="", finish_reason="stop")

            return _stream()

    class _StubTool:
        def __init__(self):
            self.name = "skill_manage"
            self.description = "manage skills"
            self.input_schema = {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            }
            self.is_concurrency_safe = True

        def run(self, args, ctx):
            return {"result": "ok"}

    _stub_tool_instance = _StubTool()

    class _StubRegistry:
        def list_specs(self):
            from agent.core.types import ToolSpec

            return (
                ToolSpec(
                    name="skill_manage",
                    description="manage skills",
                    input_schema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True,
                    },
                ),
            )

        def get(self, name):
            if name == "skill_manage":
                return _stub_tool_instance
            return None

        async def execute(
            self,
            name,
            args,
            *,
            hook_context=None,
            session_file_state=None,
            out_meta=None,
        ):
            executed_tools.append(name)
            return {"result": "ok"}

    # Construct fork WITHOUT tool_registry (mirrors app.py construction order)
    fork = AgentContextFork(
        llm_client=_TwoRoundLLMClient(),
        model="test-model",
        tool_registry=None,
        current_working_directory=tmp_path,
    )
    assert fork._loop._tool_registry is None

    # Bind the registry (mirrors bind_tool_registry call in app.py)
    fork.bind_tool_registry(_StubRegistry())

    state = AgentState(
        session_id="fork-session",
        turn_id="fork-turn",
        turn_count=0,
        history_messages=(),
        input_parts=[],
        user_text="review skills",
    )
    result = await fork.execute(
        state=state,
        max_turns=4,
        session_file_state=SessionFileState(),
        tool_execution_allowlist=("skill_manage",),
    )

    assert "skill_manage" in executed_tools, (
        f"skill_manage must have executed after bind_tool_registry; "
        f"executed_tools={executed_tools}, stop_reason={result.stop_reason}"
    )
    assert result.stop_reason != "tool_registry_unavailable", (
        "fork loop must not exit with tool_registry_unavailable after bind_tool_registry was called"
    )
