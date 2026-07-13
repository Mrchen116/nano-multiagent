"""Architecture guard for the per-conversation session ownership cutover."""

from __future__ import annotations

from pathlib import Path


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

    files = (SRC / "core" / "session" / "jsonl_files.py").read_text(
        encoding="utf-8"
    )
    writer = (SRC / "core" / "session" / "jsonl_writer.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("materialize", "repair", "append_message", "fork_session"):
        assert forbidden not in files
    for forbidden in ("append_sync", "enqueue_with_barrier"):
        assert forbidden not in writer
