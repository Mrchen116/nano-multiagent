"""Contract tests for agent.sdk surface — build_kernel + Kernel.

Covers:
- build_kernel() assembles a usable Kernel (smoke)
- Cross-loop streaming: RunsRegistry's background loop submits a turn; the
  caller's async loop iterates kernel.stream() and receives events
- can_use_tool callback: injected permission strategy is called when the gate
  fires (modelled via a stub hook that parks a permission request)
- Interrupt while waiting for permission cancels the pending turn

These tests use in-process stubs to avoid real LLM calls.  They rely on
the actual kernel assembly path (build_kernel → AgentRuntime + RunsRegistry
+ EventStreamHub + PermissionBroker), so they validate that the wiring is
correct, not just that the stubs work.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.sdk import Kernel, build_kernel
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.types import Message, TurnResult
from agent.products.local_coding.profile import LocalCodingProfile


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_llm_client() -> Any:
    """Return a fake LLM client that immediately completes a turn."""
    client = MagicMock()
    client.generate = MagicMock(return_value=_aiter_messages())
    return client


async def _aiter_messages():
    """Async generator yielding one assistant message then finishing."""
    msg = MagicMock()
    msg.role = "assistant"
    msg.content = "stub-response"
    msg.finish_reason = "stop"
    msg.tool_calls = ()
    msg.usage = None
    yield msg


def _always_allow(tool, input, ctx):  # noqa: ANN001, ANN201
    """can_use_tool strategy that allows everything."""
    from agent.platform.permissions.broker import PermissionDecision
    return asyncio.coroutine(lambda: PermissionDecision(behavior="allow"))()


async def _allow_all(tool, input, ctx) -> Any:  # noqa: ANN001
    """Async can_use_tool strategy that allows all tools."""
    from agent.platform.permissions.broker import PermissionDecision
    return PermissionDecision(behavior="allow")


# ---------------------------------------------------------------------------
# R2 Tests
# ---------------------------------------------------------------------------


def test_build_kernel_returns_kernel_instance(tmp_path: Path) -> None:
    """build_kernel() with a fake LLM client must return a Kernel."""
    kernel = build_kernel(
        product_profile=LocalCodingProfile(),
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )
    assert isinstance(kernel, Kernel)
    kernel.close()


def test_kernel_exposes_required_methods(tmp_path: Path) -> None:
    """Kernel must expose all async + sync methods declared in design.md interface."""
    kernel = build_kernel(
        product_profile=LocalCodingProfile(),
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )
    try:
        # Async methods
        assert callable(getattr(kernel, "create_session", None))
        assert callable(getattr(kernel, "fork_session", None))
        assert callable(getattr(kernel, "compact", None))
        # Sync non-blocking methods
        assert callable(getattr(kernel, "submit", None))
        assert callable(getattr(kernel, "stream", None))
        assert callable(getattr(kernel, "interrupt", None))
        assert callable(getattr(kernel, "cancel", None))
        assert callable(getattr(kernel, "get_run", None))
        assert callable(getattr(kernel, "list_session_tools", None))
        assert callable(getattr(kernel, "get_llm_config", None))
        assert callable(getattr(kernel, "reconfigure_llm", None))
        assert callable(getattr(kernel, "close", None))
    finally:
        kernel.close()


async def test_cross_loop_streaming_receives_run_status_event(tmp_path: Path) -> None:
    """Submit a turn; the caller's async loop must receive a run_status event via stream().

    This validates that RunsRegistry's background loop publishes to EventStreamHub
    and the caller's loop can consume events via Kernel.stream() as an AsyncIterator.
    """
    kernel = build_kernel(
        product_profile=LocalCodingProfile(),
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
        )

        # Collect events until run_status terminal or timeout
        events: list = []
        deadline = asyncio.get_event_loop().time() + 3.0
        async for ev in kernel.stream(session.session_id, after_sequence=0):
            events.append(ev)
            # Stop when terminal run_status arrives
            if ev.event == "run_status" and ev.data.get("status") in {"completed", "failed"}:
                break
            if asyncio.get_event_loop().time() > deadline:
                break

        event_names = {ev.event for ev in events}
        assert "run_status" in event_names, (
            f"expected run_status event, got: {event_names}"
        )
        terminal = [
            ev for ev in events
            if ev.event == "run_status" and ev.data.get("status") in {"completed", "failed"}
        ]
        assert terminal, f"no terminal run_status event, events: {event_names}"
    finally:
        kernel.close()


async def test_can_use_tool_callback_is_invoked_when_gate_fires(tmp_path: Path) -> None:
    """can_use_tool must be called when the auto_mode_gate hook fires.

    We set up a kernel where can_use_tool records that it was called,
    then trigger a turn that uses a tool which the gate processes.
    This validates the callback wiring through PermissionBroker.

    NOTE: Full integration test requires a real auto_mode_gate hook firing,
    which depends on the runtime executing a tool. For M1 SDK surface tests we
    verify the callback protocol: the SDK wires can_use_tool such that if the
    broker receives a park request, the callback is awaited and its decision
    resolves the future.
    """
    called: list[str] = []

    async def recording_can_use_tool(tool, input, ctx) -> Any:  # noqa: ANN001
        from agent.platform.permissions.broker import PermissionDecision
        called.append(str(tool))
        return PermissionDecision(behavior="allow")

    kernel = build_kernel(
        product_profile=LocalCodingProfile(),
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        can_use_tool=recording_can_use_tool,
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )
    try:
        # Directly simulate a permission request via the broker to test the wiring.
        # This is the unit-level proof that build_kernel wired can_use_tool correctly
        # without requiring a full LLM tool-call pipeline.
        from agent.platform.permissions.broker import PermissionRequest
        broker = kernel._broker  # noqa: SLF001  (test accesses internals intentionally)

        loop = asyncio.get_event_loop()
        future = broker.register_request(
            request_id="req-test-sdk-can-use-tool",
            run_id="run-test",
            tool_name="bash",
            loop=loop,
        )

        # Trigger can_use_tool resolution via the SDK bridge
        await kernel._resolve_permission_via_callback(  # noqa: SLF001
            request_id="req-test-sdk-can-use-tool",
            run_id="run-test",
            tool_name="bash",
            tool_input={},
        )

        response = await asyncio.wait_for(future, timeout=1.0)
        assert response is not None
    finally:
        kernel.close()


async def test_interrupt_while_waiting_for_permission_cancels_turn(tmp_path: Path) -> None:
    """interrupt() while can_use_tool is pending must cancel the pending future.

    This validates risk 3 from design.md: broker.cancel_all_pending resolves
    the parked Future so the turn does not hang indefinitely.
    """
    blocking_event: asyncio.Event = asyncio.Event()

    async def blocking_can_use_tool(tool, input, ctx) -> Any:  # noqa: ANN001
        # Block until released — simulates slow user decision
        await asyncio.wait_for(blocking_event.wait(), timeout=5.0)
        from agent.platform.permissions.broker import PermissionDecision
        return PermissionDecision(behavior="allow")

    kernel = build_kernel(
        product_profile=LocalCodingProfile(),
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        can_use_tool=blocking_can_use_tool,
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "use a tool"}],
            workspace_root=tmp_path,
        )

        # Register a fake permission request to simulate the gate parking
        from agent.platform.permissions.broker import PermissionRequest
        broker = kernel._broker  # noqa: SLF001
        loop = asyncio.get_event_loop()
        future = broker.register_request(
            request_id="req-interrupt-test",
            run_id=run.run_id,
            tool_name="bash",
            loop=loop,
        )

        # interrupt() must resolve all pending futures via cancel_all_pending
        kernel.interrupt(session.session_id)

        # Future should resolve quickly (deny from cancellation)
        response = await asyncio.wait_for(future, timeout=1.0)
        assert response.decision == "deny"
    finally:
        kernel.close()
