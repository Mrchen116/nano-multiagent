"""Integration test: user message appears exactly once in session history.

When runtime.run() is called once, the session history must contain exactly one user message.
"""

from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


class _SucceedLLMClient:
    """LLM client that always returns a response."""

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="hello"),
            finish_reason="stop",
        )


async def test_runtime_run_user_message_appears_once(tmp_path: Path) -> None:
    """User message is written to session history exactly once."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    session = manager.create_session(workspace_root=workspace_root.resolve())

    # Seed history with prior assistant messages.
    manager.append_turn_message(
        session.session_id,
        turn_id="turn_pre_1",
        role="assistant",
        content="prior assistant 1",
        message_id="msg_pre_assistant_1",
    )
    manager.append_turn_message(
        session.session_id,
        turn_id="turn_pre_1",
        role="assistant",
        content="prior assistant 2",
        message_id="msg_pre_assistant_2",
    )

    llm = _SucceedLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="test-model",
    )

    result = await runtime.run(session.session_id, [{"type": "text", "text": "hello"}], stream=False)

    assert result.completed is True

    # Verify user message appears exactly once in session history
    entries = manager.list_entries(session.session_id)
    user_turn_entries = [
        e for e in entries
        if e.kind is SessionEntryKind.TURN_APPENDED and e.data.get("role") == "user"
    ]
    assert len(user_turn_entries) == 1, (
        f"Expected 1 user message in session history, got {len(user_turn_entries)}: "
        f"{[e.data for e in user_turn_entries]}"
    )
    assert user_turn_entries[0].data["content"] == "hello"
