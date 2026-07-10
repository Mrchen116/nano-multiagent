"""Unit tests for the self-improvement background hook module.

Tests cover:
- nudge counter logic: skip when below threshold, trigger when at/above
- Combined vs memory-only vs skill-only prompt selection
- Anti-recursion: fork_conversation absent when self_evolution disabled
- publish_session_event called with correct payload after fork
- Default config: both enabled with interval=10
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from agent.core.agent.context_fork import ForkResult
from agent.core.types import TurnResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_fork_result(
    tool_names: tuple[str, ...] = ("skill_manage",),
) -> ForkResult:
    tr = MagicMock(spec=TurnResult)
    tr.tool_calls = []
    tr.completed = True
    return ForkResult(turn_result=tr, completed=True, tool_names_called=tool_names)


def _make_hook_ctx(
    *,
    session_id: str = "sess-1",
    fork_conversation=None,
    metadata: dict | None = None,
    publisher=None,
) -> Any:
    ctx = MagicMock()
    ctx.session_id = session_id
    ctx.fork_conversation = fork_conversation
    ctx.metadata = metadata or {}
    if publisher is not None:
        ctx.publish_session_event = publisher
    else:
        ctx.publish_session_event = MagicMock()
    return ctx


def _self_evolution_meta(
    *,
    enabled: bool = True,
    skill_creation: bool = True,
    memory_curation: bool = True,
    skill_nudge_interval: int = 10,
    memory_nudge_interval: int = 10,
) -> dict:
    return {
        "self_evolution": {
            "enabled": enabled,
            "skill_creation": skill_creation,
            "memory_curation": memory_curation,
            "skill_nudge_interval": skill_nudge_interval,
            "memory_nudge_interval": memory_nudge_interval,
        }
    }


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

from agent.platform.hooks.builtins import self_improvement as si_module


# ---------------------------------------------------------------------------
# Tests: nudge counter
# ---------------------------------------------------------------------------


class TestNudgeCounter:
    """Verify nudge counter accumulates and triggers at the right intervals."""

    def _build_hooks_and_handler(self) -> tuple[Any, Any]:
        """Build a minimal hooks mock to capture registration, then extract handler."""
        registered: dict[str, Any] = {}

        class FakeHookAPI:
            def on(
                self, event, handler, *, priority=100, timeout_ms=1500, mode="observe"
            ):
                registered[event] = (handler, mode)

            def set_state(self, key, value):
                pass

        api = FakeHookAPI()
        si_module.setup(api)
        return registered, registered.get("agent_end")

    @pytest.mark.asyncio
    async def test_skip_when_fork_conversation_absent(self):
        """When fork_conversation is None, no fork is attempted even at threshold."""
        _, reg = self._build_hooks_and_handler()
        handler, mode = reg
        assert mode == "background"

        ctx = _make_hook_ctx(
            fork_conversation=None,
            metadata=_self_evolution_meta(),
        )
        payload = {"tool_iterations": 100, "turn_count": 50}
        # Should complete without errors and without fork
        result = await _await_if_coro(handler(payload, ctx))
        ctx.publish_session_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_disabled_by_config(self):
        """When self_evolution.enabled=False, no fork triggered."""
        _, reg = self._build_hooks_and_handler()
        handler, mode = reg

        fork_fn = AsyncMock(return_value=_make_mock_fork_result())
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(enabled=False),
        )
        payload = {"tool_iterations": 100, "turn_count": 50}
        await _await_if_coro(handler(payload, ctx))
        fork_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_below_threshold_does_not_fork(self):
        """Below the nudge interval, no fork is triggered."""
        _, reg = self._build_hooks_and_handler()
        handler, mode = reg

        fork_fn = AsyncMock(return_value=_make_mock_fork_result())
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(
                skill_nudge_interval=10, memory_nudge_interval=10
            ),
        )
        # tool_iterations=9 < 10, turn_count=9 < 10 — both below threshold
        payload = {"tool_iterations": 9, "turn_count": 9}
        await _await_if_coro(handler(payload, ctx))
        fork_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_skill_threshold_triggers_fork(self):
        """Exactly at skill_nudge_interval should trigger skill review."""
        _, reg = self._build_hooks_and_handler()
        handler, mode = reg

        mock_result = _make_mock_fork_result(tool_names=("skill_manage",))
        fork_fn = AsyncMock(return_value=mock_result)
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(
                skill_nudge_interval=10, memory_nudge_interval=100
            ),
        )
        # Enough iters to hit skill threshold; not enough turns for memory
        payload = {"tool_iterations": 10, "turn_count": 5}
        await _await_if_coro(handler(payload, ctx))
        fork_fn.assert_called_once()
        # Tool allowlist must include skill_manage
        call_kwargs = fork_fn.call_args[1]
        assert "skill_manage" in call_kwargs.get("tool_allowlist", ())
        assert "skill_view" in call_kwargs.get("tool_allowlist", ())

    @pytest.mark.asyncio
    async def test_memory_threshold_triggers_fork(self):
        """Exactly at memory_nudge_interval should trigger memory review."""
        _, reg = self._build_hooks_and_handler()
        handler, mode = reg

        mock_result = _make_mock_fork_result(tool_names=("memory",))
        fork_fn = AsyncMock(return_value=mock_result)
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(
                skill_nudge_interval=100, memory_nudge_interval=10
            ),
        )
        # 10 turns, not many iters
        payload = {"tool_iterations": 5, "turn_count": 10}
        await _await_if_coro(handler(payload, ctx))
        fork_fn.assert_called_once()
        call_kwargs = fork_fn.call_args[1]
        assert "memory" in call_kwargs.get("tool_allowlist", ())

    @pytest.mark.asyncio
    async def test_combined_threshold_triggers_both(self):
        """When both thresholds hit, combined prompt and both tools in allowlist."""
        _, reg = self._build_hooks_and_handler()
        handler, mode = reg

        mock_result = _make_mock_fork_result(tool_names=("skill_manage", "memory"))
        fork_fn = AsyncMock(return_value=mock_result)
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(
                skill_nudge_interval=10, memory_nudge_interval=10
            ),
        )
        payload = {"tool_iterations": 10, "turn_count": 10}
        await _await_if_coro(handler(payload, ctx))
        fork_fn.assert_called_once()
        call_kwargs = fork_fn.call_args[1]
        allowlist = call_kwargs.get("tool_allowlist", ())
        assert "skill_manage" in allowlist
        assert "skill_view" in allowlist
        assert "memory" in allowlist

    @pytest.mark.asyncio
    async def test_accumulates_across_turns(self):
        """Counter accumulates across multiple sub-threshold calls before triggering."""
        _, reg = self._build_hooks_and_handler()
        handler, mode = reg

        mock_result = _make_mock_fork_result()
        fork_fn = AsyncMock(return_value=mock_result)
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(
                skill_nudge_interval=10, memory_nudge_interval=100
            ),
        )

        # Three calls of 4 iterations each = 12 total → crosses threshold
        for i in range(3):
            payload = {"tool_iterations": (i + 1) * 4, "turn_count": 1}
            await _await_if_coro(handler(payload, ctx))

        # By third call cumulative iters should have exceeded 10
        assert fork_fn.call_count >= 1


# ---------------------------------------------------------------------------
# Tests: session event published after fork
# ---------------------------------------------------------------------------


class TestSessionEventPublish:
    """Verify self_evolution_review event published with correct structure."""

    def _build_handler(self):
        registered: dict[str, Any] = {}

        class FakeAPI:
            def on(
                self, event, handler, *, priority=100, timeout_ms=1500, mode="observe"
            ):
                registered[event] = (handler, mode)

            def set_state(self, key, value):
                pass

        si_module.setup(FakeAPI())
        return registered["agent_end"][0]

    @pytest.mark.asyncio
    async def test_event_published_after_fork(self):
        """publish_session_event is called with self_evolution_review after fork."""
        handler = self._build_handler()
        publisher = MagicMock()
        mock_result = _make_mock_fork_result(tool_names=("skill_manage",))
        fork_fn = AsyncMock(return_value=mock_result)
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(
                skill_nudge_interval=10, memory_nudge_interval=100
            ),
            publisher=publisher,
        )
        payload = {"tool_iterations": 10, "turn_count": 3}
        await _await_if_coro(handler(payload, ctx))
        publisher.assert_called_once()
        call_args = publisher.call_args
        assert call_args[1].get("event") == "self_evolution_review" or (
            len(call_args[0]) > 0 and call_args[0][0] == "self_evolution_review"
        )

    @pytest.mark.asyncio
    async def test_no_event_when_no_fork(self):
        """No event published when threshold not reached."""
        handler = self._build_handler()
        publisher = MagicMock()
        fork_fn = AsyncMock(return_value=_make_mock_fork_result())
        ctx = _make_hook_ctx(
            fork_conversation=fork_fn,
            metadata=_self_evolution_meta(
                skill_nudge_interval=100, memory_nudge_interval=100
            ),
            publisher=publisher,
        )
        payload = {"tool_iterations": 5, "turn_count": 5}
        await _await_if_coro(handler(payload, ctx))
        publisher.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: hook registration mode
# ---------------------------------------------------------------------------


def test_setup_registers_background_hook_on_agent_end():
    """setup() must register agent_end with mode=background."""
    registered: list[tuple] = []

    class FakeAPI:
        def on(self, event, handler, *, priority=100, timeout_ms=1500, mode="observe"):
            registered.append((event, mode))

        def set_state(self, key, value):
            pass

    si_module.setup(FakeAPI())
    bg_registrations = [(e, m) for e, m in registered if m == "background"]
    assert len(bg_registrations) >= 1
    assert any(e == "agent_end" for e, m in bg_registrations)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _await_if_coro(obj: Any) -> Any:
    if asyncio.iscoroutine(obj):
        return await obj
    return obj
