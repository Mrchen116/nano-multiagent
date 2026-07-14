"""Architecture guard for the per-conversation session ownership cutover."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.llm.interfaces import LLMMessage
from agent.core.session.types import SessionRef
from agent.sdk import LLMConfig, build_kernel


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "agent"


def test_legacy_session_owners_are_deleted() -> None:
    """The final composition must not retain a second session aggregate."""

    retired = (
        SRC / "core" / "session" / "manager.py",
        SRC / "core" / "session" / "jsonl_store.py",
        SRC / "platform" / "persistence" / "session" / "service.py",
    )

    assert not [path for path in retired if path.exists()]


def test_production_has_no_legacy_session_owner_imports() -> None:
    """Production code reaches sessions only through the final aggregate types."""

    forbidden = (
        "SessionManager",
        "SessionService",
        "JsonlSessionStore",
        "AgentRuntime",
    )
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(name in text for name in forbidden):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_engine_has_no_session_id_keyed_live_state() -> None:
    """Conversation state belongs to ConversationSession, never AgentEngine maps."""

    runtime = (SRC / "core" / "agent" / "runtime.py").read_text(encoding="utf-8")
    forbidden = (
        "_session_histories",
        "_session_configs",
        "_session_paths",
        "_session_locks",
        "_memory_snapshots",
        "_file_states",
        "_prompt_slots",
        "_active_run_models",
    )

    assert not [name for name in forbidden if name in runtime]


def test_raw_jsonl_dependencies_do_not_expose_session_semantics() -> None:
    """Only JsonlTranscript may own materialize, recovery, and parent-chain logic."""

    files = (SRC / "core" / "session" / "jsonl_files.py").read_text(encoding="utf-8")
    writer = (SRC / "core" / "session" / "jsonl_writer.py").read_text(encoding="utf-8")

    for forbidden in ("materialize", "repair", "append_message", "fork_session"):
        assert forbidden not in files
    for forbidden in ("append_sync", "enqueue_with_barrier"):
        assert forbidden not in writer


@pytest.mark.asyncio
async def test_kernel_reuses_one_session_stateless_engine(tmp_path: Path) -> None:
    """Conversation identity must not allocate a second engine/client graph."""

    class _Client:
        async def generate(self, request):  # noqa: ANN001, ANN201
            yield LLMMessage(role="assistant", content="ok", finish_reason="stop")

    kernel = build_kernel(
        llm=LLMConfig(
            provider="anthropic",
            model="test-model",
            base_url="http://127.0.0.1:4000",
        ),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        first = await kernel.create_session(workspace_root=tmp_path)
        second = await kernel.create_session(workspace_root=tmp_path)
        first_conversation = kernel._c.directory.open(  # type: ignore[attr-defined]
            SessionRef(session_id=first.session_id, workspace_root=tmp_path)
        )
        second_conversation = kernel._c.directory.open(  # type: ignore[attr-defined]
            SessionRef(session_id=second.session_id, workspace_root=tmp_path)
        )

        assert first_conversation._engine is kernel._c.engine_services  # type: ignore[attr-defined]
        assert second_conversation._engine is kernel._c.engine_services  # type: ignore[attr-defined]
    finally:
        kernel.close()
