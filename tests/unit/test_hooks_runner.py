import asyncio
from pathlib import Path

from nano_multiagent.core.hooks.context import HookContext
from nano_multiagent.core.hooks.registry import HookRegistry
from nano_multiagent.core.hooks.runner import HookRunner


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

    diagnostics = asyncio.run(runner.dispatch_observe("turn_start", {}, _context("s-2")))

    assert called == ["exploding", "timeout", "survivor"]
    assert {item.status for item in diagnostics} == {"error", "timeout", "ok"}


def test_intercept_input_short_circuit_and_tool_result_merge() -> None:
    registry = HookRegistry()
    order: list[str] = []

    async def transform_input(event, ctx):
        del ctx
        order.append("transform")
        return {"action": "transform", "text": event["text"].upper(), "images": event.get("images")}

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
        return {"content": [{"type": "text", "text": "A"}], "details": {"a": 1}, "is_error": False}

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
        runner.dispatch_intercept("input", {"text": "hello", "images": []}, _context("s-3"))
    )
    tool_result = asyncio.run(
        runner.dispatch_intercept(
            "tool_result",
            {"content": [{"type": "text", "text": "orig"}], "details": {"raw": 1}, "is_error": False},
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
        runner.dispatch_intercept("tool_call", {"name": "bash", "args": {}}, _context("s-4"))
    )

    assert called == ["allow", "block"]
    assert result.stopped is True
    assert result.payload["block"] is True
    assert result.payload["reason"] == "policy"
