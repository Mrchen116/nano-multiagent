"""Session metadata fields must be present in HookContext.metadata at runtime."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Mapping

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


class EchoLLMClient:
    """LLM client that echoes user text as assistant response."""

    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        last_user_text = request.messages[-1].content
        response = LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{last_user_text}"),
            finish_reason="stop",
        )
        yield response.message
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


def _make_runtime(
    manager: SessionManager, registry: HookRegistry | None = None
) -> AgentRuntime:
    """Create an AgentRuntime wired to a JSONL store and echo LLM."""
    hook_runner = (
        HookRunner(registry=registry or HookRegistry())
        if registry is not None
        else None
    )
    return AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
        hook_runner=hook_runner or HookRunner(registry=HookRegistry()),
        repo_root=Path("/tmp"),
    )


async def test_session_metadata_merged_into_hook_context() -> None:
    """HookContext.metadata must include conversation_type from session metadata."""
    captured_contexts: list[HookContext] = []
    registry = HookRegistry()

    async def capture_ctx(payload: Mapping[str, Any], ctx: HookContext) -> None:
        captured_contexts.append(ctx)

    registry.on("before_agent_start", capture_ctx)

    store = JsonlSessionStore(data_dir=Path("/tmp") / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(
        workspace_root=Path("/tmp"),
        metadata={
            "conversation_type": "group",
            "participant_agent_ids": ["agent-a", "agent-b"],
            "agent_id": "agent-a",
        },
    )
    runtime = _make_runtime(manager, registry)
    await runtime.run(
        session.session_id, [{"type": "text", "text": "hello"}], stream=False
    )

    assert len(captured_contexts) == 1
    ctx_meta = captured_contexts[0].metadata
    assert ctx_meta.get("conversation_type") == "group"
    assert ctx_meta.get("participant_agent_ids") == ["agent-a", "agent-b"]
    assert ctx_meta.get("agent_id") == "agent-a"


async def test_runtime_keys_not_overwritten_by_session_metadata() -> None:
    """Runtime-injected keys (cwd, run_id) must not be overwritten by session metadata."""
    captured_contexts: list[HookContext] = []
    registry = HookRegistry()

    async def capture_ctx(payload: Mapping[str, Any], ctx: HookContext) -> None:
        captured_contexts.append(ctx)

    registry.on("before_agent_start", capture_ctx)

    store = JsonlSessionStore(data_dir=Path("/tmp") / "sessions")
    manager = SessionManager(store=store)
    # Session metadata tries to set cwd to a fake path — runtime's cwd must win.
    session = manager.create_session(
        workspace_root=Path("/tmp"),
        metadata={
            "cwd": "/should-not-overwrite",
            "conversation_type": "direct",
        },
    )
    runtime = _make_runtime(manager, registry)
    await runtime.run(
        session.session_id, [{"type": "text", "text": "hi"}], stream=False
    )

    assert len(captured_contexts) == 1
    ctx_meta = captured_contexts[0].metadata
    # cwd must be the workspace_root resolved by runtime, not the session metadata value
    assert ctx_meta.get("cwd") != "/should-not-overwrite"
    # but conversation_type from session metadata is still present
    assert ctx_meta.get("conversation_type") == "direct"


async def test_group_session_metadata_visible_in_hook_context() -> None:
    """Group session metadata flows through runtime into HookContext.metadata.

    feat-379-M1: The communication_context hook no longer injects a system_prompt
    override — the [Communication Context] block is now assembled by the
    pa.communication_context segment.  This test verifies the metadata pipeline
    (session config → hook_metadata → HookContext) still works correctly so that
    the wiring helper (build_prompt_context_from_metadata) can read it.
    """
    captured_contexts: list = []

    def _capture(payload: Any, ctx: Any) -> None:
        captured_contexts.append(ctx)

    registry = HookRegistry()
    registry.on(
        "before_agent_start", _capture, priority=100, timeout_ms=500, mode="observe"
    )

    store = JsonlSessionStore(data_dir=Path("/tmp") / "sessions")
    manager = SessionManager(store=store)
    llm = EchoLLMClient()
    session = manager.create_session(
        workspace_root=Path("/tmp"),
        metadata={
            "conversation_type": "group",
            "participant_agent_ids": ["agent-alpha", "agent-beta"],
            "agent_id": "agent-alpha",
        },
    )
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path("/tmp"),
    )
    await runtime.run(
        session.session_id, [{"type": "text", "text": "hello group"}], stream=False
    )

    assert len(captured_contexts) == 1
    meta = captured_contexts[0].metadata
    assert meta.get("conversation_type") == "group"
    assert "agent-alpha" in meta.get("participant_agent_ids", [])
    assert "agent-beta" in meta.get("participant_agent_ids", [])
