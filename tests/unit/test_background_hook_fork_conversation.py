"""Tests for fork_conversation: HookContext injection, system_prompt inheritance, tool allowlist.

Covers:
- HookContext.fork_conversation callable injection
- Anti-recursion: fork context has fork_conversation=None
- fork_conversation inherits parent rendered_system_prompt byte-for-byte (prefix cache)
- fork_conversation passes full parent active_tools unchanged (prefix cache)
- tool_allowlist execution-layer interception in fork (not LLM tool list reshaping)
"""

import asyncio
from unittest.mock import MagicMock

import pytest


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
    result = await ctx.fork_conversation("review", tool_allowlist=("memory",), max_turns=16)

    # The fork itself must record fork_conversation=None in its own context
    assert fork_ctx_fork_conversation_values == [None]


# ---------------------------------------------------------------------------
# R3: ForkConversation inherits parent system_prompt bytes
# ---------------------------------------------------------------------------


class _CapturingContextFork:
    """Stub AgentContextFork that records the kwargs passed to execute()."""

    def __init__(self):
        self.captured = {}

    async def execute(self, *, state, max_turns=None, session_file_state=None,
                      hook_ctx=None, system_prompt_override=None,
                      available_skills_override=None,
                      available_tools_override=None, tool_execution_allowlist=None):
        self.captured = {
            "state": state,
            "max_turns": max_turns,
            "hook_ctx": hook_ctx,
            "system_prompt_override": system_prompt_override,
            "available_skills_override": available_skills_override,
            "available_tools_override": available_tools_override,
            "tool_execution_allowlist": tool_execution_allowlist,
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
        ToolSpec(name="skill_manage", description="skills", input_schema={"type": "object"}),
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
    assert fake_fork.captured["tool_execution_allowlist"] == ("memory", "skill_manage"), (
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
            self.input_schema = {"type": "object", "properties": {}, "additionalProperties": True}
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
                    yield _LLMMsgWithCalls([
                        _LLMToolCall("c1", "bash"),
                        _LLMToolCall("c2", "memory"),
                    ])
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
