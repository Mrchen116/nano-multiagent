import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner


def _context(session_id: str) -> HookContext:
    return HookContext(session_id=session_id, repo_root=Path.cwd())


def test_observe_same_priority_respects_registration_order() -> None:
    registry = HookRegistry()
    order: list[str] = []

    def h1(event, ctx):
        del event, ctx
        order.append("h1")

    def h2(event, ctx):
        del event, ctx
        order.append("h2")

    def h3(event, ctx):
        del event, ctx
        order.append("h3")

    registry.on("turn_start", h1, priority=100)
    registry.on("turn_start", h2, priority=100)
    registry.on("turn_start", h3, priority=100)
    runner = HookRunner(registry=registry)

    asyncio.run(runner.dispatch_observe("turn_start", {"turn": 1}, _context("s-1")))

    assert order == ["h1", "h2", "h3"]


def test_observe_timeout_and_exception_are_isolated_fail_open() -> None:
    registry = HookRegistry()
    called: list[str] = []

    async def exploding(event, ctx):
        del event, ctx
        called.append("exploding")
        raise RuntimeError("boom")

    async def timeout_handler(event, ctx):
        del event, ctx
        called.append("timeout")
        await asyncio.sleep(0.05)

    async def survivor(event, ctx):
        del event, ctx
        called.append("survivor")

    registry.on("turn_start", exploding, priority=10, timeout_ms=200)
    registry.on("turn_start", timeout_handler, priority=20, timeout_ms=10)
    registry.on("turn_start", survivor, priority=30, timeout_ms=200)
    runner = HookRunner(registry=registry)

    diagnostics = asyncio.run(
        runner.dispatch_observe("turn_start", {}, _context("s-2"))
    )

    assert called == ["exploding", "timeout", "survivor"]
    assert {item.status for item in diagnostics} == {"error", "timeout", "ok"}


def test_intercept_input_short_circuit_and_tool_result_merge() -> None:
    registry = HookRegistry()
    order: list[str] = []

    async def transform_input(event, ctx):
        del ctx
        order.append("transform")
        return {
            "action": "transform",
            "text": event["text"].upper(),
            "images": event.get("images"),
        }

    async def handled_input(event, ctx):
        del event, ctx
        order.append("handled")
        return {"action": "handled"}

    async def should_not_run(event, ctx):
        del event, ctx
        order.append("late")
        return {"action": "continue"}

    async def rewrite_a(event, ctx):
        del ctx
        return {
            "content": [{"type": "text", "text": "A"}],
            "details": {"a": 1},
            "is_error": False,
        }

    async def rewrite_b(event, ctx):
        del event, ctx
        return {"details": {"b": 2}, "is_error": True}

    registry.on("input", transform_input, priority=10)
    registry.on("input", handled_input, priority=20)
    registry.on("input", should_not_run, priority=30)
    registry.on("tool_result", rewrite_a, priority=10)
    registry.on("tool_result", rewrite_b, priority=20)
    runner = HookRunner(registry=registry)

    input_result = asyncio.run(
        runner.dispatch_intercept(
            "input", {"text": "hello", "images": []}, _context("s-3")
        )
    )
    tool_result = asyncio.run(
        runner.dispatch_intercept(
            "tool_result",
            {
                "content": [{"type": "text", "text": "orig"}],
                "details": {"raw": 1},
                "is_error": False,
            },
            _context("s-3"),
        )
    )

    assert order == ["transform", "handled"]
    assert input_result.stopped is True
    assert input_result.payload["text"] == "HELLO"
    assert tool_result.stopped is False
    assert tool_result.payload["content"] == [{"type": "text", "text": "A"}]
    assert tool_result.payload["details"] == {"b": 2}
    assert tool_result.payload["is_error"] is True


def test_tool_call_block_short_circuits_following_handlers() -> None:
    registry = HookRegistry()
    called: list[str] = []

    def allow(event, ctx):
        del event, ctx
        called.append("allow")
        return {"block": False}

    def block(event, ctx):
        del event, ctx
        called.append("block")
        return {"block": True, "reason": "policy"}

    def late(event, ctx):
        del event, ctx
        called.append("late")
        return {"block": False}

    registry.on("tool_call", allow, priority=10)
    registry.on("tool_call", block, priority=20)
    registry.on("tool_call", late, priority=30)
    runner = HookRunner(registry=registry)

    result = asyncio.run(
        runner.dispatch_intercept(
            "tool_call", {"name": "bash", "args": {}}, _context("s-4")
        )
    )

    assert called == ["allow", "block"]
    assert result.stopped is True
    assert result.payload["block"] is True
    assert result.payload["reason"] == "policy"


# ---------------------------------------------------------------------------
# R3: HookContext extensions — message_history + permission_requester +
#     request_permission (R3 of feat-333-M1)
# ---------------------------------------------------------------------------


class TestHookContextMessageHistory:
    """message_history field: tuple of LLM messages for classifier transcript."""

    def test_default_message_history_is_empty_tuple(self) -> None:
        ctx = HookContext(session_id="s-mh-1")
        assert ctx.message_history == ()

    def test_message_history_stored_and_accessible(self) -> None:
        msgs = (
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        )
        ctx = HookContext(session_id="s-mh-2", message_history=msgs)
        assert ctx.message_history == msgs

    def test_message_history_coerced_to_tuple(self) -> None:
        """Any sequence passed as message_history should be accessible as-is (tuple)."""
        msgs = ({"role": "user", "content": "test"},)
        ctx = HookContext(session_id="s-mh-3", message_history=msgs)
        assert isinstance(ctx.message_history, tuple)
        assert len(ctx.message_history) == 1


class TestHookContextPermissionRequester:
    """permission_requester field and request_permission method."""

    @pytest.mark.asyncio
    async def test_request_permission_without_requester_returns_deny(self) -> None:
        """When no permission_requester is set, request_permission fail-closes to deny."""
        from agent.platform.permissions.broker import (
            PermissionRequest,
            PermissionOption,
        )

        ctx = HookContext(session_id="s-pr-1")
        req = PermissionRequest(
            id="req-1",
            tool_name="write",
            tool_input={"file_path": "/tmp/f"},
            question="Allow write?",
            options=(
                PermissionOption("allow_once", "Allow once", ""),
                PermissionOption("deny", "Deny", ""),
            ),
        )
        response = await ctx.request_permission(req)
        assert response.decision == "deny"
        assert "no permission channel" in response.reason

    @pytest.mark.asyncio
    async def test_request_permission_delegates_to_requester(self) -> None:
        """When permission_requester is set, request_permission awaits it."""
        from agent.platform.permissions.broker import (
            PermissionRequest,
            PermissionOption,
            PermissionResponse,
        )

        async def allow_requester(req):
            return PermissionResponse(decision="allow_once", request_id=req.id)

        ctx = HookContext(session_id="s-pr-2", permission_requester=allow_requester)
        req = PermissionRequest(
            id="req-2",
            tool_name="bash",
            tool_input={"command": "ls"},
            question="Allow ls?",
            options=(PermissionOption("allow_once", "Allow once", ""),),
        )
        response = await ctx.request_permission(req)
        assert response.decision == "allow_once"
        assert response.request_id == "req-2"

    def test_permission_requester_default_is_none(self) -> None:
        ctx = HookContext(session_id="s-pr-3")
        assert ctx.permission_requester is None


class TestHookRunnerTimeoutNone:
    """Hooks registered with timeout_ms=None are not wrapped in asyncio.wait_for."""

    @pytest.mark.asyncio
    async def test_timeout_none_hook_runs_without_cancellation(self) -> None:
        """A hook with timeout_ms=None can run longer than the default timeout."""
        registry = HookRegistry()
        called = []

        async def long_hook(event, ctx):
            # Sleeps 20ms — would be cancelled under default 1500ms timeout IF
            # the hook was registered with a very short timeout_ms. We just
            # confirm it runs to completion when timeout_ms=None.
            await asyncio.sleep(0.02)
            called.append("done")
            return None

        registry.on("turn_start", long_hook, timeout_ms=None)
        runner = HookRunner(registry=registry)
        diagnostics = await runner.dispatch_observe(
            "turn_start", {}, HookContext(session_id="s-tn-1")
        )
        assert called == ["done"]
        assert diagnostics[0].status == "ok"

    def test_registration_allows_none_timeout_ms(self) -> None:
        registry = HookRegistry()

        def noop(event, ctx):
            return None

        reg = registry.on("tool_call", noop, timeout_ms=None)
        assert reg.timeout_ms is None


def test_dispatch_observe_skips_intercept_mode_handlers() -> None:
    """An INTERCEPT-mode handler must NOT execute during dispatch_observe.

    Regression (bugfix-377): the auto_mode_gate classifier is dispatched for
    "tool_call". "tool_call" is dispatched twice per tool — once as intercept
    (where the block decision is honored, with the populated tool transcript)
    and once as observe (for stream/metrics observers). Because handlers_for
    ignored mode, the gate ALSO ran in the observe pass: it burned a model call
    on a ctx with no message_history (empty <transcript> -> blind classify,
    escalating to a second stage) and its result was discarded. Observe dispatch
    must run only observe-mode handlers.
    """
    from agent.core.hooks.types import HookEventMode

    registry = HookRegistry()
    ran: list[str] = []

    def observer(event, ctx):
        del event, ctx
        ran.append("observe")

    def gate(event, ctx):
        del event, ctx
        ran.append("intercept")
        return {"block": False}

    registry.on("tool_call", observer, mode=HookEventMode.OBSERVE)
    registry.on("tool_call", gate, mode=HookEventMode.INTERCEPT)
    runner = HookRunner(registry=registry)

    asyncio.run(
        runner.dispatch_observe("tool_call", {"name": "bash"}, _context("s-obs"))
    )
    assert ran == ["observe"], (
        f"intercept handler must not run in observe dispatch, got {ran}"
    )

    # And the intercept handler DOES run during dispatch_intercept.
    ran.clear()
    asyncio.run(
        runner.dispatch_intercept(
            "tool_call", {"name": "bash", "block": False}, _context("s-int")
        )
    )
    assert "intercept" in ran, "intercept handler must run in intercept dispatch"


def test_strip_fork_conversation_preserves_message_history_and_permission_requester() -> (
    None
):
    """_strip_fork_conversation must null ONLY fork_conversation, keeping every
    other field — notably message_history and permission_requester.

    Regression (bugfix-377): the manual rebuild in _strip_fork_conversation
    copied a hand-listed subset of fields and silently dropped message_history
    and permission_requester (added to HookContext later, on 2026-05-15, without
    updating this rebuild). Result: any observe/intercept dispatch whose ctx
    carried a fork_conversation reached the auto_mode_gate classifier with an
    EMPTY transcript — the classifier ran blind and over-blocked — and lost the
    PermissionBroker so request_permission fail-closed to deny.
    """
    from agent.core.hooks.runner import _strip_fork_conversation

    sentinel_history = ("user-msg", "assistant-tool_use")

    async def requester(req):
        return None

    async def make_fork(review_prompt, *, tool_allowlist, max_turns):
        return None

    ctx = HookContext(
        session_id="sess-strip",
        turn_id="turn-1",
        message_history=sentinel_history,
        permission_requester=requester,
        fork_conversation=make_fork,
    )

    stripped = _strip_fork_conversation(ctx)

    assert stripped.fork_conversation is None
    assert stripped.message_history == sentinel_history, (
        "message_history must survive fork_conversation stripping"
    )
    assert stripped.permission_requester is requester, (
        "permission_requester must survive fork_conversation stripping"
    )
