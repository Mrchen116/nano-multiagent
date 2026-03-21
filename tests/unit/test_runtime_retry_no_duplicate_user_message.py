"""Integration test: retryable ModelError in loop does not duplicate user message in session history.

When runtime.run() is called once and LLM generate() fails transiently N times
before succeeding, the session history must contain exactly one user message.
"""

from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.entries import SessionEntryKind
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


class _RetryThenSucceedLLMClient:
    """LLM client that raises retryable ModelError N times then returns a response."""

    def __init__(self, *, fail_count: int) -> None:
        self.call_count = 0
        self._fail_count = fail_count

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise ModelError("transient upstream error", retryable=True)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="hello after retry"),
            finish_reason="stop",
        )


def test_runtime_run_retryable_model_error_user_message_appears_once(tmp_path: Path) -> None:
    """User message is written to session history exactly once even when LLM retries."""
    store = SQLiteSessionStore(db_path=tmp_path / "retry-dedup.sqlite3")
    manager = SessionManager(store=store)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    session = manager.create_session(metadata={"workspace_root": str(workspace_root.resolve())})

    llm = _RetryThenSucceedLLMClient(fail_count=3)
    runtime = AgentRuntime(session_manager=manager, llm_client=llm, model="test-model")

    result = runtime.run(session.session_id, [{"type": "text", "text": "hello"}], stream=False)

    assert result.completed is True
    assert llm.call_count == 4  # 3 failures + 1 success

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
