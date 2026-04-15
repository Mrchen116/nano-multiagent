"""M236: Session metadata fields must be present in HookContext.metadata at runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.manager import SessionManager
from agent.core.session.store import LoadedSession, SessionStore


# ---------------------------------------------------------------------------
# Shared test infrastructure
# ---------------------------------------------------------------------------


class InMemorySessionStore(SessionStore):
    """Minimal in-memory store for unit tests."""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.snapshots: dict[str, dict[str, object]] = {}

    def append_event(self, session_id: str, entry: object) -> None:
        self.events.append((session_id, entry))

    def load_session(self, session_id: str) -> LoadedSession | None:
        session_events = tuple(e for sid, e in self.events if sid == session_id)
        if not session_events and session_id not in self.snapshots:
            return None
        return LoadedSession(
            session_id=session_id,
            events=session_events,
            snapshot=self.snapshots.get(session_id),
        )

    def save_snapshot(self, session_id: str, snapshot: dict[str, object]) -> None:
        self.snapshots[session_id] = snapshot


class EchoLLMClient:
    """LLM client that echoes user text as assistant response."""

    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        last_user_text = request.messages[-1].content
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{last_user_text}"),
            finish_reason="stop",
        )


def _make_runtime(manager: SessionManager, registry: HookRegistry | None = None) -> AgentRuntime:
    """Create an AgentRuntime wired to an in-memory store and echo LLM."""
    hook_runner = HookRunner(registry=registry or HookRegistry()) if registry is not None else None
    return AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
        hook_runner=hook_runner or HookRunner(registry=HookRegistry()),
        repo_root=Path("/tmp"),
    )


# ---------------------------------------------------------------------------
# R2 tests
# ---------------------------------------------------------------------------


async def test_session_metadata_merged_into_hook_context() -> None:
    """HookContext.metadata must include conversation_type from session metadata."""
    captured_contexts: list[HookContext] = []
    registry = HookRegistry()

    async def capture_ctx(payload: Mapping[str, Any], ctx: HookContext) -> None:
        captured_contexts.append(ctx)

    registry.on("before_agent_start", capture_ctx)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session(
        workspace_root=Path("/tmp"),
        metadata={
            "conversation_type": "group",
            "participant_agent_ids": ["agent-a", "agent-b"],
            "agent_id": "agent-a",
        }
    )
    runtime = _make_runtime(manager, registry)
    await runtime.run(session.session_id, [{"type": "text", "text": "hello"}], stream=False)

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

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    # Session metadata tries to set cwd to a fake path — runtime's cwd must win.
    session = manager.create_session(
        workspace_root=Path("/tmp"),
        metadata={
            "cwd": "/should-not-overwrite",
            "conversation_type": "direct",
        }
    )
    runtime = _make_runtime(manager, registry)
    await runtime.run(session.session_id, [{"type": "text", "text": "hi"}], stream=False)

    assert len(captured_contexts) == 1
    ctx_meta = captured_contexts[0].metadata
    # cwd must be the workspace_root resolved by runtime, not the session metadata value
    assert ctx_meta.get("cwd") != "/should-not-overwrite"
    # but conversation_type from session metadata is still present
    assert ctx_meta.get("conversation_type") == "direct"


async def test_before_agent_start_reads_conversation_type_end_to_end() -> None:
    """End-to-end: group session metadata flows through runtime to LLM system prompt."""
    from agent.products.personal_assistant.hooks import setup

    registry = HookRegistry()

    class _FakeHookAPI:
        def on(self, event: str, handler: Any, **kwargs: Any) -> None:
            registry.on(event, handler, **kwargs)

    setup(_FakeHookAPI())

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    llm = EchoLLMClient()
    session = manager.create_session(
        workspace_root=Path("/tmp"),
        metadata={
            "conversation_type": "group",
            "participant_agent_ids": ["agent-alpha", "agent-beta"],
            "agent_id": "agent-alpha",
        }
    )
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path("/tmp"),
    )
    await runtime.run(session.session_id, [{"type": "text", "text": "hello group"}], stream=False)

    assert len(llm.requests) == 1
    system_message = llm.requests[0].messages[0]
    assert system_message.role == "system"
    # The hook must have injected the communication context block
    assert "[Communication Context]" in system_message.content
    assert "session_type: group" in system_message.content
    assert "agent-alpha" in system_message.content
    assert "agent-beta" in system_message.content


async def test_before_agent_start_noop_when_no_conversation_type() -> None:
    """Hook must be a no-op when session has no conversation_type (safe degradation)."""
    from agent.products.personal_assistant.hooks import setup

    registry = HookRegistry()

    class _FakeHookAPI:
        def on(self, event: str, handler: Any, **kwargs: Any) -> None:
            registry.on(event, handler, **kwargs)

    setup(_FakeHookAPI())

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    llm = EchoLLMClient()
    session = manager.create_session(
        workspace_root=Path("/tmp"),  # no conversation_type
    )
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path("/tmp"),
    )
    await runtime.run(session.session_id, [{"type": "text", "text": "just a regular message"}], stream=False)

    assert len(llm.requests) == 1
    system_message = llm.requests[0].messages[0]
    # No communication context block when conversation_type absent
    assert "[Communication Context]" not in system_message.content
