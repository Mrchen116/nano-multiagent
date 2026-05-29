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
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from agent.sdk import Kernel, build_kernel
from agent.core.llm.factory import LLMFactoryConfig
from agent.products.local_coding.profile import LOCAL_CODING_PROFILE


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _allow_all(tool, input, ctx) -> Any:  # noqa: ANN001
    """Async can_use_tool strategy that allows all tools."""
    from agent.platform.permissions.broker import PermissionDecision
    return PermissionDecision(behavior="allow")


def _fake_llm_client() -> Any:
    """Return a fake LLM client whose generate() returns an async generator each call.

    The runtime calls ``client.generate(request)`` and iterates the async generator.
    We return a new generator object on every call so the client is reusable across runs.
    """
    class _FakeClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            return _async_stub_messages()

    return _FakeClient()


async def _async_stub_messages():
    """Async generator yielding one assistant message then finishing."""
    msg = MagicMock()
    msg.role = "assistant"
    msg.content = "stub-response"
    msg.finish_reason = "stop"
    msg.tool_calls = ()
    msg.usage = None
    yield msg


# ---------------------------------------------------------------------------
# R2 Tests
# ---------------------------------------------------------------------------


def test_build_kernel_returns_kernel_instance(tmp_path: Path) -> None:
    """build_kernel() with a fake LLM client must return a Kernel."""
    kernel = build_kernel(
        product_profile=LOCAL_CODING_PROFILE,
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
        product_profile=LOCAL_CODING_PROFILE,
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
        product_profile=LOCAL_CODING_PROFILE,
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


async def test_can_use_tool_callback_is_invoked_via_permission_requester(tmp_path: Path) -> None:
    """The SDK-injected permission_requester must call can_use_tool and use its decision.

    This validates the callback wiring: when a permission request arrives at the
    runtime's HookContext.request_permission(), the SDK bridges it to can_use_tool
    and resolves the broker Future with the callback's PermissionDecision.
    """
    called: list[str] = []

    async def recording_can_use_tool(tool, input, ctx) -> Any:  # noqa: ANN001
        from agent.platform.permissions.broker import PermissionDecision
        called.append(str(tool))
        return PermissionDecision(behavior="allow")

    kernel = build_kernel(
        product_profile=LOCAL_CODING_PROFILE,
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
        # Simulate a permission request coming through the runtime's hook context.
        # The SDK wires a permission_requester into the runtime; we call it directly
        # to verify that can_use_tool is invoked and the decision is returned.
        from agent.platform.permissions.broker import PermissionRequest

        requester = kernel._c.runtime._permission_requester  # noqa: SLF001
        assert requester is not None, "SDK must inject a permission_requester into runtime"

        # Build a minimal PermissionRequest
        req = PermissionRequest(
            id="req-sdk-can-use-tool",
            tool_name="bash",
            tool_input={"command": "echo hi"},
            question="Allow bash?",
            options=(),
        )
        response = await asyncio.wait_for(requester(req), timeout=2.0)

        # can_use_tool returned allow → response should be allow_once
        assert response.decision == "allow_once"
        assert "bash" in called
    finally:
        kernel.close()


async def test_interrupt_while_waiting_for_permission_cancels_turn(tmp_path: Path) -> None:
    """interrupt() while can_use_tool is pending must cancel the pending future.

    This validates risk 3 from design.md: when interrupt fires, cancel_all_pending
    resolves the broker Future to deny so the awaiting permission_requester returns
    without hanging indefinitely.
    """
    blocking_event: asyncio.Event = asyncio.Event()

    async def blocking_can_use_tool(tool, input, ctx) -> Any:  # noqa: ANN001
        # Block until released — simulates slow user decision
        await asyncio.wait_for(blocking_event.wait(), timeout=5.0)
        from agent.platform.permissions.broker import PermissionDecision
        return PermissionDecision(behavior="allow")

    kernel = build_kernel(
        product_profile=LOCAL_CODING_PROFILE,
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

        from agent.platform.permissions.broker import PermissionRequest

        requester = kernel._c.runtime._permission_requester  # noqa: SLF001
        assert requester is not None

        req = PermissionRequest(
            id="req-interrupt-perm",
            tool_name="bash",
            tool_input={"command": "echo hi"},
            question="Allow bash?",
            options=(),
        )

        # Start awaiting permission in background — will block on blocking_can_use_tool
        perm_task = asyncio.create_task(requester(req))

        # Give the task a moment to start and park in broker
        await asyncio.sleep(0.05)

        # interrupt() must cancel the blocking permission wait via cancel_all_pending
        kernel.interrupt(session.session_id)

        # The pending permission should resolve quickly after interrupt
        response = await asyncio.wait_for(perm_task, timeout=2.0)
        # Broker cancel_all_pending resolves to deny
        assert response.decision == "deny"
    finally:
        kernel.close()
