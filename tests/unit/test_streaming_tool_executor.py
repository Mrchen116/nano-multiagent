"""Unit tests for StreamingToolExecutor."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest

from agent.core.agent.tool_executor import StreamingToolExecutor
from agent.core.tools.base import Tool
from agent.core.tools.registry import ToolRegistry
from agent.core.tools.base import ToolContext
from agent.core.types import ToolCall, ToolResult


class _FakeTool(Tool):
    def __init__(
        self,
        *,
        name: str,
        is_concurrency_safe: bool = False,
        delay: float = 0.0,
        raise_error: bool = False,
        approval: str | None = None,
    ) -> None:
        self.name = name
        self.description = "Fake"
        self.input_schema: Mapping[str, Any] = {"type": "object"}
        self.is_concurrency_safe = is_concurrency_safe
        self.max_result_size_chars: int | None = None
        self._delay = delay
        self._raise = raise_error
        # feat-434-M1: emulate the gate stamping approval into out_meta (written by
        # registry.execute on the success path) BEFORE the tool's body runs/blocks.
        self._approval = approval

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        raise NotImplementedError("use async registry mock")

    def serialize_result(
        self, output: Any, error: str | None = None
    ) -> str | list[dict[str, Any]]:
        return str(output) if output else error or ""


class _FakeRegistry(ToolRegistry):
    """Registry whose execute() is overridden to avoid real tool safety infra."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._executed: list[tuple[str, Mapping[str, Any]]] = []
        self._start_times: dict[str, float] = {}

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        self._tools[tool.name] = tool

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context=None,
        session_file_state=None,
        out_meta=None,
    ) -> Mapping[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise RuntimeError(f"unknown tool: {name}")
        self._executed.append((name, args))
        self._start_times[name] = asyncio.get_event_loop().time()
        # feat-434-M1: gate stamps approval into out_meta up-front (before the tool
        # body), so it is already present when a sibling abort cancels this call
        # mid-flight — the synthetic_error path must still carry it.
        if out_meta is not None and tool._approval is not None:
            out_meta["approval"] = tool._approval
        if tool._delay:
            await asyncio.sleep(tool._delay)
        if tool._raise:
            raise RuntimeError(f"{name} failed")
        return {"name": name, "args": dict(args)}

    @property
    def execution_order(self) -> list[str]:
        return [n for n, _ in self._executed]

    def _last_start(self, name: str) -> float:
        return self._start_times.get(name, 0.0)


@pytest.fixture
def registry() -> _FakeRegistry:
    return _FakeRegistry()


def _call(name: str, args: Mapping[str, Any] | None = None) -> ToolCall:
    return ToolCall(call_id=f"call_{name}", name=name, arguments=args or {})


# ---------------------------------------------------------------------------
# Basic enqueue / completion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_tool_completes(registry: _FakeRegistry) -> None:
    registry.register(_FakeTool(name="read", is_concurrency_safe=True))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("read", {"path": "/tmp/foo"}))
    await asyncio.sleep(0.05)

    results = executor.get_completed_results()
    assert len(results) == 1
    assert results[0].name == "read"
    assert results[0].output == {"name": "read", "args": {"path": "/tmp/foo"}}
    assert not executor.has_unfinished()


@pytest.mark.asyncio
async def test_nonexistent_tool_records_error(registry: _FakeRegistry) -> None:
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("missing"))
    await asyncio.sleep(0.05)

    results = executor.get_completed_results()
    assert len(results) == 1
    assert results[0].name == "missing"
    assert results[0].error is not None
    assert "unknown tool" in results[0].error


# ---------------------------------------------------------------------------
# Concurrency: safe tools run in parallel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safe_tools_run_in_parallel(registry: _FakeRegistry) -> None:
    """Two safe tools with non-zero delay should overlap in time."""
    registry.register(_FakeTool(name="r1", is_concurrency_safe=True, delay=0.1))
    registry.register(_FakeTool(name="r2", is_concurrency_safe=True, delay=0.1))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("r1"))
    executor.add_tool(_call("r2"))
    await asyncio.sleep(0.05)  # both should have started

    # Both should be executing or completed by now
    results = executor.get_remaining_results()
    items = []
    async for r in results:
        items.append(r)
    assert len(items) == 2

    # Overlap: r2 should have started before r1 finished
    t1 = registry._last_start("r1")
    t2 = registry._last_start("r2")
    assert abs(t2 - t1) < 0.08, "safe tools should start almost simultaneously"


# ---------------------------------------------------------------------------
# Blocking: non-safe tools block subsequent items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_safe_blocks_subsequent(registry: _FakeRegistry) -> None:
    """[unsafe, safe] → safe must wait for unsafe to finish."""
    registry.register(_FakeTool(name="bash", is_concurrency_safe=False, delay=0.15))
    registry.register(_FakeTool(name="read", is_concurrency_safe=True, delay=0.0))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("bash"))
    executor.add_tool(_call("read"))
    await asyncio.sleep(0.05)  # bash still running

    # read should still be queued because bash is executing and unsafe
    assert executor.has_unfinished()

    # Wait for everything
    items = []
    async for r in executor.get_remaining_results():
        items.append(r)
    assert len(items) == 2
    assert registry.execution_order == ["bash", "read"]
    # read started after bash finished
    assert registry._last_start("read") >= registry._last_start("bash") + 0.1


@pytest.mark.asyncio
async def test_safe_then_non_safe_blocks_later_safe(registry: _FakeRegistry) -> None:
    """[safe, unsafe, safe] → third safe waits for unsafe."""
    registry.register(_FakeTool(name="r1", is_concurrency_safe=True, delay=0.05))
    registry.register(_FakeTool(name="bash", is_concurrency_safe=False, delay=0.1))
    registry.register(_FakeTool(name="r2", is_concurrency_safe=True, delay=0.0))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("r1"))
    executor.add_tool(_call("bash"))
    executor.add_tool(_call("r2"))
    await asyncio.sleep(0.02)  # r1 started

    # bash should be executing now, r2 queued
    items = []
    async for r in executor.get_remaining_results():
        items.append(r)

    assert len(items) == 3
    # r2 started after bash finished
    assert registry._last_start("r2") >= registry._last_start("bash") + 0.08


# ---------------------------------------------------------------------------
# Results yielded in order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_results_yielded_in_enqueue_order(registry: _FakeRegistry) -> None:
    registry.register(_FakeTool(name="r1", is_concurrency_safe=True, delay=0.02))
    registry.register(_FakeTool(name="r2", is_concurrency_safe=True, delay=0.01))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("r1"))
    executor.add_tool(_call("r2"))

    items = []
    async for r in executor.get_remaining_results():
        items.append(r)
    names = [r.name for r in items]
    assert names == ["r1", "r2"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_error_is_captured(registry: _FakeRegistry) -> None:
    registry.register(_FakeTool(name="bad", is_concurrency_safe=True, raise_error=True))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("bad"))
    await asyncio.sleep(0.05)

    results = executor.get_completed_results()
    assert len(results) == 1
    assert results[0].name == "bad"
    assert results[0].error is not None
    assert "bad failed" in results[0].error


# ---------------------------------------------------------------------------
# Discard / abort
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discard_aborts_queued_tools(registry: _FakeRegistry) -> None:
    registry.register(_FakeTool(name="bash", is_concurrency_safe=False, delay=0.2))
    registry.register(_FakeTool(name="read", is_concurrency_safe=True))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("bash"))
    executor.add_tool(_call("read"))
    await asyncio.sleep(0.02)

    executor.discard()

    # After discard, nothing should be unfinished
    assert not executor.has_unfinished()

    results = executor.get_completed_results()
    names = [r.name for r in results]
    assert "read" in names
    read_result = [r for r in results if r.name == "read"][0]
    assert read_result.error is not None
    assert "discarded" in read_result.error


@pytest.mark.asyncio
async def test_discard_does_not_affect_already_completed(
    registry: _FakeRegistry,
) -> None:
    registry.register(_FakeTool(name="read", is_concurrency_safe=True))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("read"))
    await asyncio.sleep(0.05)

    # Already completed
    results_before = executor.get_completed_results()
    assert len(results_before) == 1
    assert results_before[0].output is not None

    # Discard is a no-op for already-completed
    executor.discard()
    results_after = executor.get_completed_results()
    assert len(results_after) == 0  # already yielded


# ---------------------------------------------------------------------------
# Bash sibling abort cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bash_error_cancels_sibling_bash(registry: _FakeRegistry) -> None:
    """One bash failing triggers sibling abort for other parallel bash tools.

    Both bash tools must be concurrency-safe so they start in parallel;
    otherwise FIFO blocking prevents the second from ever starting.
    """
    registry.register(_FakeTool(name="bash", is_concurrency_safe=True, delay=0.15))
    registry.register(
        _FakeTool(name="bash", is_concurrency_safe=True, delay=0.0, raise_error=True)
    )
    executor = StreamingToolExecutor(registry)

    executor.add_tool(
        ToolCall(call_id="call_bash_1", name="bash", arguments={"cmd": "sleep 1"})
    )
    executor.add_tool(
        ToolCall(call_id="call_bash_2", name="bash", arguments={"cmd": "false"})
    )
    await asyncio.sleep(0.05)  # bash2 fails quickly

    # bash1 should be cancelled by sibling abort
    items = []
    async for r in executor.get_remaining_results():
        items.append(r)

    assert len(items) == 2
    results_by_call_id = {r.call_id: r for r in items}
    # One of them failed (the one that raised), the other was cancelled by sibling abort
    errors = [r.error for r in items if r.error is not None]
    assert len(errors) == 2
    assert any("cancelled by sibling bash error" in e for e in errors)


class _CmdKeyedRegistry(_FakeRegistry):
    """Resolve the behaviour by ``args['cmd']`` instead of tool name, so two
    distinct bash behaviours (a slow gate-approved one + a fast failing one) can
    coexist under the same tool name ``bash`` — needed because sibling-abort only
    cancels tools named ``bash`` (tool_executor._should_cancel)."""

    def __init__(self, by_cmd: dict[str, _FakeTool]) -> None:
        super().__init__()
        self._by_cmd = by_cmd
        for t in by_cmd.values():
            self._tools[t.name] = t

    async def execute(
        self, name, args, *, hook_context=None, session_file_state=None, out_meta=None
    ):
        tool = self._by_cmd[args["cmd"]]
        if out_meta is not None and tool._approval is not None:
            out_meta["approval"] = tool._approval
        if tool._delay:
            await asyncio.sleep(tool._delay)
        if tool._raise:
            raise RuntimeError(f"{name} failed")
        return {"name": name, "args": dict(args)}


@pytest.mark.asyncio
async def test_sibling_abort_preserves_user_allow_approval() -> None:
    """feat-434-M1 (F2): a user-allowed tool cancelled by a sibling bash error must
    NOT lose its approval=user_allow.

    Race: two concurrency-safe bash tools start in parallel. The slow one had already
    been gate-approved (approval written into out_meta by registry.execute) and is
    mid-flight when the fast one raises → sibling abort cancels the slow one. The
    synthetic error result must still carry approval=user_allow, else the front-end
    gate region silently drops 「已授权」 for a genuinely user-approved tool.
    """
    registry = _CmdKeyedRegistry(
        {
            "slow": _FakeTool(
                name="bash", is_concurrency_safe=True, delay=0.2, approval="user_allow"
            ),
            "boom": _FakeTool(
                name="bash", is_concurrency_safe=True, delay=0.0, raise_error=True
            ),
        }
    )
    executor = StreamingToolExecutor(registry)
    executor.add_tool(
        ToolCall(call_id="call_allow", name="bash", arguments={"cmd": "slow"})
    )
    executor.add_tool(
        ToolCall(call_id="call_fail", name="bash", arguments={"cmd": "boom"})
    )
    await asyncio.sleep(0.05)

    results = {r.call_id: r async for r in executor.get_remaining_results()}
    cancelled = results["call_allow"]
    assert cancelled.error is not None  # cancelled → synthetic error
    assert "cancelled by sibling bash error" in cancelled.error
    assert cancelled.approval == "user_allow", (
        "a sibling-cancelled but user-approved tool must keep approval=user_allow"
    )


class _ApprovedThenBlockRegistry(_FakeRegistry):
    """execute() stamps approval into out_meta (gate already decided), then blocks
    forever — so an external task.cancel() interrupts it mid-await and drives the
    ``except asyncio.CancelledError`` branch of _execute_one (the other cancel path,
    distinct from sibling-abort)."""

    def __init__(self, approval: str | None) -> None:
        super().__init__()
        self._approval = approval
        self._tools["bash"] = _FakeTool(name="bash", is_concurrency_safe=True)
        self.started = asyncio.Event()

    async def execute(
        self, name, args, *, hook_context=None, session_file_state=None, out_meta=None
    ):
        if out_meta is not None and self._approval is not None:
            out_meta["approval"] = self._approval
        self.started.set()
        await asyncio.Event().wait()  # block until cancelled


@pytest.mark.asyncio
async def test_cancelled_error_preserves_user_allow_approval() -> None:
    """feat-434-M1 (C2): a user-approved tool whose run is interrupted by
    CancelledError (after the gate stamped approval into out_meta) must keep
    approval=user_allow on its synthetic 'tool execution discarded' result — same
    invariant as the sibling-abort path, just the other cancel branch (line ~194).
    """
    registry = _ApprovedThenBlockRegistry(approval="user_allow")
    executor = StreamingToolExecutor(registry)
    item = ToolCall(call_id="call_cx", name="bash", arguments={"cmd": "x"})
    executor.add_tool(item)
    await asyncio.wait_for(registry.started.wait(), timeout=1.0)

    queued = executor._queue[0]
    assert queued.task is not None
    queued.task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued.task

    assert queued.result is not None
    assert queued.result.error is not None
    assert "discarded" in queued.result.error
    assert queued.result.approval == "user_allow", (
        "a CancelledError-interrupted but user-approved tool must keep approval"
    )


@pytest.mark.asyncio
async def test_non_bash_error_does_not_cancel_siblings(registry: _FakeRegistry) -> None:
    """Non-bash tool error does not trigger sibling abort."""
    registry.register(_FakeTool(name="read", is_concurrency_safe=True, delay=0.15))
    registry.register(
        _FakeTool(name="bad", is_concurrency_safe=True, delay=0.0, raise_error=True)
    )
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("read"))
    executor.add_tool(_call("bad"))
    await asyncio.sleep(0.05)

    items = []
    async for r in executor.get_remaining_results():
        items.append(r)

    assert len(items) == 2
    bad_result = [r for r in items if r.name == "bad"][0]
    read_result = [r for r in items if r.name == "read"][0]
    assert bad_result.error is not None
    assert "bad failed" in bad_result.error
    # read should complete normally despite bad failing
    assert read_result.output is not None
    assert read_result.error is None


# ---------------------------------------------------------------------------
# get_completed_results is non-blocking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_completed_results_non_blocking(registry: _FakeRegistry) -> None:
    registry.register(_FakeTool(name="r1", is_concurrency_safe=True, delay=0.1))
    registry.register(_FakeTool(name="r2", is_concurrency_safe=True, delay=0.2))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("r1"))
    executor.add_tool(_call("r2"))
    await asyncio.sleep(0.15)  # r1 done, r2 still running

    results = executor.get_completed_results()
    assert len(results) == 1
    assert results[0].name == "r1"
    assert executor.has_unfinished()  # r2 still going

    # Calling again yields nothing new (r1 already yielded)
    results2 = executor.get_completed_results()
    assert len(results2) == 0


# ---------------------------------------------------------------------------
# RC1 regression: get_completed_results must not skip executing safe tools
# (bugfix-376: parallel safe tools could produce out-of-order tool_results)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_completed_results_does_not_return_b_while_a_executing(
    registry: _FakeRegistry,
) -> None:
    """[A(executing,safe), B(completed,safe)] → get_completed_results must return nothing.

    Bug: the old break condition `not item.is_safe` evaluates to False for safe
    tools, so the loop skips over executing-A and returns completed-B.  That puts
    B's tool_result ahead of A's in llm_messages, which causes the upstream
    (kimi K2.6) to see a tool_result before its paired tool_use and reject with
    "tool_call_ids did not have response messages".
    """
    registry.register(_FakeTool(name="r1", is_concurrency_safe=True, delay=0.15))
    registry.register(_FakeTool(name="r2", is_concurrency_safe=True, delay=0.0))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("r1"))
    executor.add_tool(_call("r2"))

    # Give r2 time to finish but r1 is still executing (delay=0.15).
    await asyncio.sleep(0.05)

    # r2 is done, r1 is still executing.
    # get_completed_results() must return nothing because r1 (index 0) is still executing.
    results = executor.get_completed_results()
    assert results == [], (
        f"expected no results while earlier safe tool is executing, got {[r.name for r in results]}"
    )
    assert executor.has_unfinished()

    # Drain remaining — order must be r1 then r2.
    items = []
    async for r in executor.get_remaining_results():
        items.append(r)
    assert [r.name for r in items] == ["r1", "r2"]


@pytest.mark.asyncio
async def test_parallel_safe_tool_results_in_enqueue_order(
    registry: _FakeRegistry,
) -> None:
    """Full round-trip: parallel safe tools must yield results in enqueue order.

    Scenario mirrors the bugfix-376 upstream-req at 21-43-10:
      - Two parallel read calls (A slower, B faster)
      - Mid-stream get_completed_results() must not return B alone
      - Combined results from get_completed_results() + get_remaining_results()
        must be [A, B], matching the assistant's tool_use order
    """
    registry.register(_FakeTool(name="r1", is_concurrency_safe=True, delay=0.12))
    registry.register(_FakeTool(name="r2", is_concurrency_safe=True, delay=0.02))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("r1"))
    executor.add_tool(_call("r2"))

    early: list = []
    # Simulate mid-stream polling: r2 should have finished but r1 hasn't yet.
    await asyncio.sleep(0.06)
    early.extend(executor.get_completed_results())

    # Wait for the rest.
    remaining: list = []
    async for r in executor.get_remaining_results():
        remaining.append(r)

    all_results = early + remaining
    assert [r.name for r in all_results] == ["r1", "r2"], (
        f"expected [r1, r2] in enqueue order, got {[r.name for r in all_results]}"
    )


# ---------------------------------------------------------------------------
# feat-440-M1: semantic rejection text on ToolResult.error
# ---------------------------------------------------------------------------


class _BlockingRegistry(ToolRegistry):
    """Registry whose execute() raises a ToolError carrying gate block details."""

    def __init__(self, details: Mapping[str, Any]) -> None:
        self._tools: dict[str, Tool] = {}
        self._details = details

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        self._tools[tool.name] = tool

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context=None,
        session_file_state=None,
        out_meta=None,
    ) -> Mapping[str, Any]:
        from agent.core.errors import ToolError

        raise ToolError(
            "tool blocked by hook", tool_name=name, details=dict(self._details)
        )


async def _drain(executor: StreamingToolExecutor) -> list[ToolResult]:
    items: list[ToolResult] = []
    async for r in executor.get_remaining_results():
        items.append(r)
    return items


@pytest.mark.asyncio
async def test_non_allowlisted_tool_yields_subagent_reject_message() -> None:
    """A non-allowlisted tool in a fork side-chain → SUBAGENT_REJECT_MESSAGE,
    not the raw 'is not allowed in this background review context' string."""
    from agent.core.agent.reject_messages import SUBAGENT_REJECT_MESSAGE

    registry = _FakeRegistry()
    registry.register(_FakeTool(name="read"))
    # feat-440-M2 (F6): the fork construction point now sets is_fork_sidechain=True
    # explicitly — the allowlist alone no longer implies subagent.
    executor = StreamingToolExecutor(
        registry, tool_execution_allowlist=("read",), is_fork_sidechain=True
    )

    executor.add_tool(_call("bash"))
    results = await _drain(executor)

    assert len(results) == 1
    assert results[0].error == SUBAGENT_REJECT_MESSAGE


@pytest.mark.asyncio
async def test_subagent_allowlisted_tool_gate_blocked_yields_subagent_reject() -> None:
    """F5 (row 1b): inside a fork side-chain, a tool that IS on the execution
    allowlist (so it reaches registry.execute) but is then blocked by the gate must
    still land on SUBAGENT_REJECT — the subagent wording wins over the gate's
    user_deny/reason signals because there is no user to wait on in a fork.

    This covers the path the M1 suite missed: M1 only tested the non-allowlisted
    synthetic-error branch (never reaches the registry), not an allowlisted-but-
    gate-denied tool flowing through the ToolError catch branch."""
    from agent.core.agent.reject_messages import SUBAGENT_REJECT_MESSAGE

    registry = _BlockingRegistry(
        {
            "blocked_by_hook": True,
            "reason": "some gate reason",
            "reason_code": "denied",
            "approval": "user_deny",
        }
    )
    registry.register(_FakeTool(name="edit"))
    # edit IS allowlisted → passes execution-layer narrowing, reaches execute(),
    # which raises the gate ToolError; is_fork_sidechain=True → SUBAGENT wording.
    executor = StreamingToolExecutor(
        registry, tool_execution_allowlist=("edit",), is_fork_sidechain=True
    )

    executor.add_tool(_call("edit"))
    results = await _drain(executor)

    assert results[0].error == SUBAGENT_REJECT_MESSAGE
    # The gate badge signals still survive even though the text is SUBAGENT.
    assert results[0].reason_code == "denied"


@pytest.mark.asyncio
async def test_user_deny_with_reason_yields_with_reason_prefix() -> None:
    """Main-session user deny + reason → REJECT_MESSAGE_WITH_REASON_PREFIX + reason."""
    from agent.core.agent.reject_messages import REJECT_MESSAGE_WITH_REASON_PREFIX

    registry = _BlockingRegistry(
        {
            "blocked_by_hook": True,
            "reason": "先别动这个文件",
            "reason_code": "denied",
            "approval": "user_deny",
        }
    )
    registry.register(_FakeTool(name="edit"))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("edit"))
    results = await _drain(executor)

    assert results[0].error == REJECT_MESSAGE_WITH_REASON_PREFIX + "先别动这个文件"
    # Existing badge signals must still survive onto the result.
    assert results[0].reason_code == "denied"
    assert results[0].approval == "user_deny"


@pytest.mark.asyncio
async def test_user_deny_without_reason_yields_reject_message() -> None:
    from agent.core.agent.reject_messages import REJECT_MESSAGE

    registry = _BlockingRegistry(
        {
            "blocked_by_hook": True,
            "reason": "",
            "reason_code": "denied",
            "approval": "user_deny",
        }
    )
    registry.register(_FakeTool(name="edit"))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("edit"))
    results = await _drain(executor)

    assert results[0].error == REJECT_MESSAGE


@pytest.mark.asyncio
async def test_auto_block_yields_auto_reject_message() -> None:
    """Automatic block (no approval) → auto_reject_message(reason)."""
    from agent.core.agent.reject_messages import auto_reject_message

    registry = _BlockingRegistry(
        {
            "blocked_by_hook": True,
            "reason": "deny-limit exceeded",
            "reason_code": "denied",
            "approval": None,
        }
    )
    registry.register(_FakeTool(name="bash"))
    executor = StreamingToolExecutor(registry)

    executor.add_tool(_call("bash"))
    results = await _drain(executor)

    assert results[0].error == auto_reject_message("deny-limit exceeded")
    assert results[0].reason_code == "denied"


# ---------------------------------------------------------------------------
# feat-440-M2 (F6): is_subagent decoupled from tool_execution_allowlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_session_with_allowlist_user_deny_stays_main_reject() -> None:
    """F6: an execution allowlist must NOT imply 'subagent' for the reject-message
    choice. A main session that one day gains a tool_execution_allowlist (e.g. a
    sandbox mode) and whose user Denies a tool must still get the main-session
    REJECT_MESSAGE — not the semantically inverted SUBAGENT_REJECT. The is_subagent
    signal now rides an explicit fork flag, not the allowlist's presence."""
    from agent.core.agent.reject_messages import REJECT_MESSAGE

    registry = _BlockingRegistry(
        {
            "blocked_by_hook": True,
            "reason": "",
            "reason_code": "denied",
            "approval": "user_deny",
        }
    )
    registry.register(_FakeTool(name="edit"))
    # allowlist active (edit permitted to execute) but NOT a fork side-chain.
    executor = StreamingToolExecutor(
        registry, tool_execution_allowlist=("edit",), is_fork_sidechain=False
    )

    executor.add_tool(_call("edit"))
    results = await _drain(executor)

    assert results[0].error == REJECT_MESSAGE


@pytest.mark.asyncio
async def test_fork_sidechain_flag_drives_subagent_reject_without_allowlist() -> None:
    """F6: the explicit fork flag alone selects SUBAGENT_REJECT — independent of any
    allowlist. A user_deny block inside a fork-flagged executor → SUBAGENT (row 1)."""
    from agent.core.agent.reject_messages import SUBAGENT_REJECT_MESSAGE

    registry = _BlockingRegistry(
        {
            "blocked_by_hook": True,
            "reason": "ignored in subagent",
            "reason_code": "denied",
            "approval": "user_deny",
        }
    )
    registry.register(_FakeTool(name="edit"))
    executor = StreamingToolExecutor(registry, is_fork_sidechain=True)

    executor.add_tool(_call("edit"))
    results = await _drain(executor)

    assert results[0].error == SUBAGENT_REJECT_MESSAGE
