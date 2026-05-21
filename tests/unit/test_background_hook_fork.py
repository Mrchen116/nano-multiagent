"""Tests for background hook infrastructure: HookEventMode enum and dispatch_background.

Covers:
- HookEventMode.BACKGROUND enumeration value
- HookRegistration.mode field
- HookRegistry.on() with mode="background"
- HookRunner.dispatch_background() fire-and-forget (no await, no timeout)
"""

import asyncio
import time

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
    assert elapsed < 0.04, f"dispatch_background blocked for {elapsed:.3f}s — must be near-instant"
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
    assert len(observe_called) == 0, "dispatch_background must not fire observe handlers"
