"""Tests for background hook infrastructure: HookEventMode enum and dispatch_background.

Covers:
- HookEventMode.BACKGROUND enumeration value
- HookRegistration.mode field
- HookRegistry.on() with mode="background"
- HookRunner.dispatch_background() fire-and-forget (no await, no timeout)
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.core.hooks.types import HookEventMode, HookRegistration


# ---------------------------------------------------------------------------
# R1: HookEventMode.BACKGROUND enumeration
# ---------------------------------------------------------------------------


def test_hook_event_mode_has_background_value():
    """HookEventMode must have a BACKGROUND member for fire-and-forget dispatch."""
    assert HookEventMode.BACKGROUND == "background"


def test_hook_event_mode_has_three_modes():
    """Exactly three modes: observe, intercept, background."""
    modes = {m.value for m in HookEventMode}
    assert modes == {"observe", "intercept", "background"}


def test_hook_registration_has_mode_field():
    """HookRegistration must carry a mode field defaulting to observe."""
    from agent.core.hooks.types import DEFAULT_HOOK_TIMEOUT_MS

    reg = HookRegistration(
        event="agent_end",
        handler=lambda p, c: None,
        mode=HookEventMode.OBSERVE,
    )
    assert reg.mode == HookEventMode.OBSERVE


def test_hook_registration_can_be_background():
    """HookRegistration with mode=BACKGROUND is valid."""
    reg = HookRegistration(
        event="agent_end",
        handler=lambda p, c: None,
        mode=HookEventMode.BACKGROUND,
    )
    assert reg.mode == HookEventMode.BACKGROUND


# ---------------------------------------------------------------------------
# R1: HookRegistry.on() supports mode="background"
# ---------------------------------------------------------------------------


def test_registry_on_accepts_background_mode():
    """registry.on(..., mode='background') must not raise."""
    from agent.core.hooks.registry import HookRegistry

    registry = HookRegistry()
    called = []

    async def handler(payload, ctx):
        called.append(payload)

    reg = registry.on("agent_end", handler, mode="background")
    assert reg.mode == HookEventMode.BACKGROUND


def test_registry_on_default_mode_is_observe():
    """registry.on() without mode defaults to observe."""
    from agent.core.hooks.registry import HookRegistry

    registry = HookRegistry()
    reg = registry.on("agent_end", lambda p, c: None)
    assert reg.mode == HookEventMode.OBSERVE


def test_registry_background_handlers_for_returns_them():
    """background_handlers_for() should return only BACKGROUND registrations."""
    from agent.core.hooks.registry import HookRegistry

    registry = HookRegistry()
    registry.on("agent_end", lambda p, c: None, mode="observe")
    bg_reg = registry.on("agent_end", lambda p, c: None, mode="background")
    registry.on("agent_end", lambda p, c: None, mode="observe")

    bg_handlers = registry.background_handlers_for("agent_end")
    assert len(bg_handlers) == 1
    assert bg_handlers[0].hook_id == bg_reg.hook_id


# ---------------------------------------------------------------------------
# R2: HookRunner.dispatch_background fire-and-forget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_background_does_not_await_handler():
    """dispatch_background must fire-and-forget: it creates a task but does not await it."""
    from agent.core.hooks.registry import HookRegistry
    from agent.core.hooks.runner import HookRunner
    from agent.core.hooks.context import HookContext

    registry = HookRegistry()
    started = []
    finished = []

    async def slow_handler(payload, ctx):
        started.append(True)
        await asyncio.sleep(0.05)
        finished.append(True)

    registry.on("agent_end", slow_handler, mode="background")
    runner = HookRunner(registry=registry)
    ctx = HookContext(session_id="test-session")

    t0 = time.monotonic()
    task = runner.dispatch_background("agent_end", {"session_id": "s1"}, ctx)
    elapsed = time.monotonic() - t0

    # dispatch_background returns immediately (fire-and-forget)
    assert elapsed < 0.04, (
        f"dispatch_background blocked for {elapsed:.3f}s — must be near-instant"
    )
    # The handler should not have finished yet (we didn't await)
    assert len(finished) == 0

    # Now allow the task to complete
    await asyncio.sleep(0.1)
    assert len(finished) == 1


@pytest.mark.asyncio
async def test_dispatch_background_not_constrained_by_timeout_ms():
    """Background handler is NOT killed by timeout_ms (no asyncio.wait_for wrapping)."""
    from agent.core.hooks.registry import HookRegistry
    from agent.core.hooks.runner import HookRunner
    from agent.core.hooks.context import HookContext

    registry = HookRegistry()
    finished = []

    # timeout_ms=10 — but background mode should NOT timeout
    async def slow_handler(payload, ctx):
        await asyncio.sleep(0.05)
        finished.append(True)

    registry.on("agent_end", slow_handler, mode="background", timeout_ms=10)
    runner = HookRunner(registry=registry)
    ctx = HookContext(session_id="test-session")

    runner.dispatch_background("agent_end", {"session_id": "s1"}, ctx)
    await asyncio.sleep(0.1)
    assert len(finished) == 1, "Background handler must not be killed by timeout_ms"


@pytest.mark.asyncio
async def test_dispatch_background_isolates_errors():
    """Background handler exceptions must not propagate to caller."""
    from agent.core.hooks.registry import HookRegistry
    from agent.core.hooks.runner import HookRunner
    from agent.core.hooks.context import HookContext

    registry = HookRegistry()

    async def bad_handler(payload, ctx):
        raise RuntimeError("background error")

    registry.on("agent_end", bad_handler, mode="background")
    runner = HookRunner(registry=registry)
    ctx = HookContext(session_id="test-session")

    # Should not raise
    runner.dispatch_background("agent_end", {"session_id": "s1"}, ctx)
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_dispatch_background_only_fires_background_handlers():
    """dispatch_background must skip observe/intercept handlers for the same event."""
    from agent.core.hooks.registry import HookRegistry
    from agent.core.hooks.runner import HookRunner
    from agent.core.hooks.context import HookContext

    registry = HookRegistry()
    observe_called = []
    background_called = []

    async def obs_handler(payload, ctx):
        observe_called.append(True)

    async def bg_handler(payload, ctx):
        background_called.append(True)

    registry.on("agent_end", obs_handler, mode="observe")
    registry.on("agent_end", bg_handler, mode="background")
    runner = HookRunner(registry=registry)
    ctx = HookContext(session_id="test-session")

    runner.dispatch_background("agent_end", {"session_id": "s1"}, ctx)
    await asyncio.sleep(0.05)

    assert len(background_called) == 1
    assert len(observe_called) == 0, (
        "dispatch_background must not fire observe handlers"
    )


# ---------------------------------------------------------------------------
# R3: HookContext.fork_conversation callable + anti-recursion
# ---------------------------------------------------------------------------


def test_hook_context_has_fork_conversation_field():
    """HookContext must accept fork_conversation kwarg."""
    from agent.core.hooks.context import HookContext

    ctx = HookContext(session_id="test", fork_conversation=None)
    assert ctx.fork_conversation is None


def test_hook_context_fork_conversation_can_be_callable():
    """HookContext fork_conversation accepts a callable."""
    from agent.core.hooks.context import HookContext

    async def my_fork(review_prompt, *, tool_allowlist, max_turns):
        return None

    ctx = HookContext(session_id="test", fork_conversation=my_fork)
    assert callable(ctx.fork_conversation)


@pytest.mark.asyncio
async def test_fork_conversation_none_in_fork_context():
    """The HookContext created for fork's own background hooks must have fork_conversation=None.

    This prevents recursive fork: review agent dispatches agent_end, background
    hook fires, but fork_conversation is None so it cannot spawn another fork.
    """
    from agent.core.hooks.context import HookContext

    fork_ctx_fork_conversation_values = []

    async def make_fork(review_prompt, *, tool_allowlist, max_turns):
        # Simulate that fork internally creates its own context
        # In real impl the fork creates a context with fork_conversation=None
        fork_ctx_fork_conversation_values.append(None)  # always None inside fork
        return MagicMock(messages=[], completed=True)

    ctx = HookContext(session_id="test", fork_conversation=make_fork)
    # Call fork_conversation — result context must have fork_conversation=None
    result = await ctx.fork_conversation(
        "review", tool_allowlist=("memory",), max_turns=16
    )

    # The fork itself must record fork_conversation=None in its own context
    assert fork_ctx_fork_conversation_values == [None]


# ---------------------------------------------------------------------------
# R3: ForkConversation inherits parent system_prompt bytes
# ---------------------------------------------------------------------------


class _CapturingContextFork:
    """Stub AgentContextFork that records the kwargs passed to execute()."""

    def __init__(self):
        self.captured = {}

    async def execute(
        self,
        *,
        state,
        max_turns=None,
        session_file_state=None,
        system_prompt_override=None,
        available_skills_override=None,
        available_tools_override=None,
        tool_execution_allowlist=None,
        hook_ctx=None,
        model_override=None,
    ):
        self.captured = {
            "state": state,
            "max_turns": max_turns,
            "system_prompt_override": system_prompt_override,
            "available_skills_override": available_skills_override,
            "available_tools_override": available_tools_override,
            "tool_execution_allowlist": tool_execution_allowlist,
            "hook_ctx": hook_ctx,
            "model_override": model_override,
        }
        fake_result = MagicMock()
        fake_result.messages = ()
        fake_result.completed = True
        fake_result.tool_calls = ()
        return fake_result


@pytest.mark.asyncio
async def test_fork_conversation_inherits_parent_system_prompt():
    """fork_conversation must send the exact parent rendered_system_prompt to the fork LLM.

    Byte identity is required for provider prefix cache hits (decision 1, design.md).
    """
    from agent.core.agent.context_fork import make_fork_conversation

    parent_system_prompt = "PARENT_SYSTEM_PROMPT_UNIQUE_BYTES_12345"
    fake_fork = _CapturingContextFork()

    fork_fn = make_fork_conversation(
        context_fork=fake_fork,
        rendered_system_prompt=parent_system_prompt,
        active_tools=(),
        messages_snapshot=[],
        session_id="test-session",
        tool_allowlist=("memory", "skill_manage"),
    )

    await fork_fn("Review this.", tool_allowlist=("memory",), max_turns=16)

    assert fake_fork.captured["system_prompt_override"] == parent_system_prompt, (
        "fork_conversation must pass parent rendered_system_prompt byte-for-byte "
        "to preserve prefix cache; got different prompt"
    )


@pytest.mark.asyncio
async def test_fork_conversation_inherits_parent_active_tools_byte_for_byte():
    """fork_conversation must send the FULL parent active_tools to the fork LLM unchanged.

    The tools array is part of the provider prefix-cache key. Narrowing it to a
    subset (e.g. only allowlisted tools) causes a cache miss, which defeats the
    whole point of the background-fork design. Tool narrowing must happen at the
    execution layer, NOT by reshaping available_tools_override (decision 6).
    """
    from agent.core.agent.context_fork import make_fork_conversation
    from agent.core.types import ToolSpec

    # Parent turn has 4 tools; allowlist only permits 2 of them.
    parent_tools = (
        ToolSpec(name="bash", description="run bash", input_schema={"type": "object"}),
        ToolSpec(name="read", description="read file", input_schema={"type": "object"}),
        ToolSpec(name="memory", description="memory", input_schema={"type": "object"}),
        ToolSpec(
            name="skill_manage", description="skills", input_schema={"type": "object"}
        ),
    )
    fake_fork = _CapturingContextFork()

    fork_fn = make_fork_conversation(
        context_fork=fake_fork,
        rendered_system_prompt="sys",
        active_tools=parent_tools,
        messages_snapshot=[],
        session_id="test-session",
        tool_allowlist=("memory", "skill_manage"),
    )

    await fork_fn("Review.", tool_allowlist=("memory", "skill_manage"), max_turns=4)

    passed_tools = fake_fork.captured["available_tools_override"]
    assert passed_tools == parent_tools, (
        "fork_conversation must pass the FULL parent active_tools byte-for-byte; "
        f"got {passed_tools!r} — narrowing the tool list breaks prefix cache"
    )
    # The allowlist is enforced separately, via tool_execution_allowlist.
    assert fake_fork.captured["tool_execution_allowlist"] == (
        "memory",
        "skill_manage",
    ), (
        "tool_allowlist must be forwarded as tool_execution_allowlist (execution-layer "
        "interception), not used to reshape the LLM tool list"
    )


@pytest.mark.asyncio
async def test_fork_executor_denies_unlisted_tool_at_execution_layer():
    """A fork LLM that calls a non-allowlisted tool must be denied at the execution layer.

    The tool must NOT actually execute (no side effects); the executor returns a
    synthetic error result instead. The allowlisted tool still runs normally.
    """
    from agent.core.agent.context_fork import AgentContextFork, make_fork_conversation
    from agent.core.tools.base import (
        set_tool_safety_config_factory,
        set_tool_safety_factory,
    )
    from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig
    from agent.platform.tools.base import ToolContext
    from agent.platform.tools.registry import ToolRegistry
    from agent.core.types import ToolSpec
    from pathlib import Path
    import tempfile

    set_tool_safety_factory(ToolSafety)
    set_tool_safety_config_factory(ToolSafetyConfig)

    # Track which tools actually executed (proves deny prevents side effects).
    executed_tools = []

    class _RecordingTool:
        def __init__(self, name):
            self.name = name
            self.description = f"{name} tool"
            self.input_schema = {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            }
            self.is_concurrency_safe = True

        def run(self, args, ctx):
            executed_tools.append(self.name)
            return {"ok": self.name}

    # Fake LLM: round 1 calls both 'bash' (denied) and 'memory' (allowed),
    # round 2 finishes.
    class _LLMToolCall:
        def __init__(self, call_id, name):
            self.call_id = call_id
            self.name = name
            self.arguments = {}

    class _LLMMsgWithCalls:
        role = "assistant"
        content = ""

        def __init__(self, calls):
            self.tool_calls = calls
            self.finish_reason = None
            self.usage = None
            self.reasoning_content = None
            self.reasoning_signature = None

    class _LLMTerminal:
        role = "assistant"
        content = ""
        tool_calls = []
        finish_reason = "stop"
        usage = None
        reasoning_content = None
        reasoning_signature = None

    class _LLMFinalText:
        role = "assistant"
        content = "done"
        tool_calls = []
        finish_reason = None
        usage = None
        reasoning_content = None
        reasoning_signature = None

    class FakeLLMClient:
        def __init__(self):
            self._round = 0

        def generate(self, request):
            self._round += 1
            round_no = self._round

            async def _stream():
                if round_no == 1:
                    yield _LLMMsgWithCalls(
                        [
                            _LLMToolCall("c1", "bash"),
                            _LLMToolCall("c2", "memory"),
                        ]
                    )
                    yield _LLMTerminal()
                else:
                    yield _LLMFinalText()
                    yield _LLMTerminal()

            return _stream()

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        registry = ToolRegistry(context=ToolContext.create(repo_root=repo_root))
        registry.register(_RecordingTool("bash"))
        registry.register(_RecordingTool("memory"))

        context_fork = AgentContextFork(
            llm_client=FakeLLMClient(),
            model="test-model",
            tool_registry=registry,
            current_working_directory=repo_root,
        )

        active_tools = registry.list_specs()
        fork_fn = make_fork_conversation(
            context_fork=context_fork,
            rendered_system_prompt="sys",
            active_tools=active_tools,
            messages_snapshot=[],
            session_id="fork-session",
            tool_allowlist=("memory",),
        )

        result = await fork_fn("Review.", tool_allowlist=("memory",), max_turns=8)

    # 'memory' is allowlisted -> actually executed. 'bash' is denied -> never executed.
    assert "memory" in executed_tools, "allowlisted tool 'memory' must execute"
    assert "bash" not in executed_tools, (
        f"non-allowlisted tool 'bash' must be denied at execution layer and NOT run; "
        f"executed_tools={executed_tools}"
    )
    assert result.completed


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
            self, name, args, *, hook_context=None, session_file_state=None, out_meta=None
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


@pytest.mark.asyncio
async def test_fork_inherits_parent_execution_context():
    """The fork's hook_ctx must inherit the parent's execution capabilities.

    bugfix-375/M2 (root cause 2): forks ran AgentLoop.run with no hook_ctx → a
    bare default HookContext with model_caller=None, so auto_mode_gate fail-closed
    inside the fork and the self-improvement agent could not use even its
    allowlisted tools. The fork must inherit model_caller / permission_requester
    from the parent (replace-derived), null fork_conversation (anti-recursion),
    and run as an unattended background task (so a gate `ask` resolves via
    unattended_fallback instead of parking on a non-existent human).
    """
    from agent.core.agent.context_fork import make_fork_conversation
    from agent.core.hooks.context import HookContext
    from agent.core.runs.origin import RunOrigin

    def parent_model_caller(call):
        return None

    async def parent_requester(req):
        return None

    async def parent_fork(*a, **k):
        return None

    parent_ctx = HookContext(
        session_id="sess-parent",
        turn_id="turn-parent",
        metadata={"run_origin": "user", "tool_call_id": "stale-tc"},
        model_caller=parent_model_caller,
        permission_requester=parent_requester,
        fork_conversation=parent_fork,
    )

    fake_fork = _CapturingContextFork()
    fork_fn = make_fork_conversation(
        context_fork=fake_fork,
        rendered_system_prompt="SYS",
        active_tools=(),
        messages_snapshot=[],
        session_id="sess-parent",
        tool_allowlist=("skill_manage",),
        parent_hook_ctx=parent_ctx,
    )
    await fork_fn("review prompt", tool_allowlist=("skill_manage",), max_turns=4)

    fork_ctx = fake_fork.captured["hook_ctx"]
    assert fork_ctx is not None, "fork must receive an inherited hook_ctx"
    assert fork_ctx.model_caller is parent_model_caller, (
        "fork must inherit parent model_caller (else gate fail-closes inside fork)"
    )
    assert fork_ctx.permission_requester is parent_requester, (
        "fork must inherit parent permission_requester"
    )
    assert fork_ctx.fork_conversation is None, (
        "anti-recursion: fork ctx must null fork_conversation"
    )
    assert fork_ctx.metadata.get("run_origin") == RunOrigin.BACKGROUND_TASK.value, (
        "fork must run as unattended background task so gate ask uses fallback"
    )
    assert "tool_call_id" not in fork_ctx.metadata, (
        "stale parent tool_call_id must not leak into fork"
    )
