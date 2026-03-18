"""Unit tests for the personal_assistant before_agent_start hook (M232).

Tests verify that the hook appends the correct communication context block for
group chats and a simplified version for direct chats, and is a no-op when
conversation_type is absent.
"""

from __future__ import annotations

from agent.core.hooks.context import HookContext
from agent.products.personal_assistant.hooks import _build_communication_context_block


def _make_ctx(*, conversation_type: str | None = None, participant_agent_ids: list[str] | None = None, agent_id: str | None = None) -> HookContext:
    """Build a HookContext with injected session-level group metadata."""
    metadata: dict = {}
    if conversation_type is not None:
        metadata["conversation_type"] = conversation_type
    if participant_agent_ids is not None:
        metadata["participant_agent_ids"] = participant_agent_ids
    if agent_id is not None:
        metadata["agent_id"] = agent_id
    return HookContext(session_id="sess-test", metadata=metadata)


# ---------------------------------------------------------------------------
# _build_communication_context_block helper tests
# ---------------------------------------------------------------------------

def test_build_context_block_group_contains_required_fields() -> None:
    """Group context block contains conversation_type, agent_id, and participant list."""
    block = _build_communication_context_block(
        conversation_type="group",
        agent_id="agent-a",
        participant_agent_ids=["agent-a", "agent-b"],
    )
    assert "[Communication Context]" in block
    assert "group" in block
    assert "agent-a" in block
    assert "agent-b" in block


def test_build_context_block_direct_contains_agent_id_only() -> None:
    """Direct-chat context block contains agent_id but no participant list."""
    block = _build_communication_context_block(
        conversation_type="direct",
        agent_id="agent-x",
        participant_agent_ids=None,
    )
    assert "[Communication Context]" in block
    assert "direct" in block
    assert "agent-x" in block
    # Direct chat should not list participants.
    assert "participants" not in block.lower() or "[]" in block


# ---------------------------------------------------------------------------
# Hook integration tests (via setup/dispatch simulation)
# ---------------------------------------------------------------------------

def _run_hook(payload: dict, ctx: HookContext) -> dict | None:
    """Invoke the registered before_agent_start handler directly."""
    from agent.core.hooks.registry import HookRegistry, HookAPI
    from agent.products.personal_assistant.hooks import setup

    registry = HookRegistry()
    setup(HookAPI(registry, source="product", module_name="pa_hooks", file_path=None))
    handlers = registry.handlers_for("before_agent_start")
    assert handlers, "no before_agent_start handler registered"
    # Use first registered handler (synchronous).
    result = handlers[0].handler(payload, ctx)
    return result  # type: ignore[return-value]


def test_hook_group_appends_context_block_to_none_base_prompt() -> None:
    """When base system_prompt is None and conversation_type=group, hook returns a non-None system_prompt."""
    ctx = _make_ctx(conversation_type="group", participant_agent_ids=["agent-a", "agent-b"], agent_id="agent-a")
    result = _run_hook({"message": "hello", "system_prompt": None}, ctx)

    assert result is not None
    assert "system_prompt" in result
    assert result["system_prompt"] is not None
    assert "[Communication Context]" in result["system_prompt"]
    assert "group" in result["system_prompt"]


def test_hook_group_appends_context_block_after_existing_prompt() -> None:
    """When base system_prompt is provided, group context is appended after it."""
    base = "You are a helpful assistant."
    ctx = _make_ctx(conversation_type="group", participant_agent_ids=["agent-a"], agent_id="agent-a")
    result = _run_hook({"message": "hi", "system_prompt": base}, ctx)

    assert result is not None
    sp = result["system_prompt"]
    assert sp.startswith(base)
    assert "[Communication Context]" in sp


def test_hook_direct_appends_simplified_context() -> None:
    """Direct-chat hook appends a simplified context block with agent_id."""
    ctx = _make_ctx(conversation_type="direct", agent_id="agent-z")
    result = _run_hook({"message": "hi", "system_prompt": None}, ctx)

    assert result is not None
    assert "system_prompt" in result
    assert result["system_prompt"] is not None
    assert "[Communication Context]" in result["system_prompt"]
    assert "agent-z" in result["system_prompt"]


def test_hook_no_conversation_type_returns_none() -> None:
    """When ctx.metadata lacks conversation_type, hook returns None (safe no-op)."""
    ctx = _make_ctx()  # no conversation_type
    result = _run_hook({"message": "hi", "system_prompt": None}, ctx)

    assert result is None
