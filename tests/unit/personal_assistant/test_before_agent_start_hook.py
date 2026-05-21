"""Unit tests for the personal_assistant communication_context module (feat-379-M1).

After M1, the before_agent_start hook no longer injects a system_prompt override.
Group-chat communication context is now handled by the pa.communication_context
segment (order=900, cache_safe=False) in the segment assembler.

These tests verify:
1. _build_communication_context_block helper still produces correct output
   (it is reused by the pa.communication_context segment render function).
2. The hook's setup() function does NOT register a before_agent_start handler
   that returns a system_prompt key — prompt injection is retired.
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
# _build_communication_context_block helper tests (unchanged behaviour)
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
# Hook retirement tests (feat-379-M1)
# ---------------------------------------------------------------------------

def test_hook_does_not_register_before_agent_start_after_m1() -> None:
    """After M1, setup() must NOT register a before_agent_start handler.

    Group-chat context is now provided by the pa.communication_context segment,
    not by a hook that modifies the system_prompt override.
    """
    from agent.core.hooks.registry import HookRegistry, HookAPI
    from agent.products.personal_assistant.hooks import setup

    registry = HookRegistry()
    setup(HookAPI(registry, source="product", module_name="pa_hooks", file_path=None))
    handlers = registry.handlers_for("before_agent_start")
    assert not handlers, (
        "feat-379-M1: communication_context.setup() must not register "
        "before_agent_start after prompt injection is retired"
    )


def test_hook_group_no_longer_injects_system_prompt() -> None:
    """Verify that calling any registered before_agent_start handler (if present)
    does NOT return a system_prompt key for group chat.

    This is belt-and-suspenders: if the hook is somehow still registered, its
    return value must not carry a system_prompt to prevent double-injection when
    the segment assembler is also in use.
    """
    from agent.core.hooks.registry import HookRegistry, HookAPI
    from agent.products.personal_assistant.hooks import setup

    registry = HookRegistry()
    setup(HookAPI(registry, source="product", module_name="pa_hooks", file_path=None))
    handlers = registry.handlers_for("before_agent_start")

    # No handlers expected after M1 retirement.
    if not handlers:
        return  # Pass: hook correctly removed.

    ctx = _make_ctx(conversation_type="group", participant_agent_ids=["agent-a"], agent_id="agent-a")
    payload = {"message": "hello", "system_prompt": None}
    result = handlers[0].handler(payload, ctx)

    # If a handler is still present, it must not inject a system_prompt.
    if result is not None:
        assert "system_prompt" not in result or result.get("system_prompt") is None, (
            "Hook must not return system_prompt after M1: use pa.communication_context segment"
        )
