"""Tests for JsonlSessionStore metadata query and agent_id index."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agent.core.session.jsonl_store import JsonlSessionStore, SessionConfig


def _make_store(tmpdir: str) -> JsonlSessionStore:
    return JsonlSessionStore(data_dir=Path(tmpdir))


def _write_session_file(path: Path, session_id: str, metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "type": "session_created",
        "session_id": session_id,
        "created_at": "2024-01-01T00:00:00",
        "workspace_root": "/tmp",
        "metadata": metadata,
    }
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# find_session_by_metadata
# ---------------------------------------------------------------------------


def test_find_by_agent_id_in_main_session() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        _write_session_file(
            Path(tmpdir) / "sessions" / "sess-a.jsonl",
            "sess-a",
            {"agent_id": "a1234567890abcdef", "kind": "subagent"},
        )
        result = store.find_session_by_metadata(
            parent_session_id=None,
            match={"agent_id": "a1234567890abcdef"},
        )
        assert result == "sess-a"


def test_find_by_agent_id_in_subagent_session() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        _write_session_file(
            Path(tmpdir) / "sessions" / "parent-1" / "subagents" / "sub-1.jsonl",
            "sub-1",
            {"agent_id": "a2234567890abcdef", "kind": "subagent"},
        )
        result = store.find_session_by_metadata(
            parent_session_id="parent-1",
            match={"agent_id": "a2234567890abcdef"},
        )
        assert result == "sub-1"


def test_find_isolated_by_parent_session_id() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        # Two subagents with same agent_id under different parents.
        _write_session_file(
            Path(tmpdir) / "sessions" / "parent-a" / "subagents" / "sub-a.jsonl",
            "sub-a",
            {"agent_id": "a3334567890abcdef"},
        )
        _write_session_file(
            Path(tmpdir) / "sessions" / "parent-b" / "subagents" / "sub-b.jsonl",
            "sub-b",
            {"agent_id": "a3334567890abcdef"},
        )
        result = store.find_session_by_metadata(
            parent_session_id="parent-a",
            match={"agent_id": "a3334567890abcdef"},
        )
        assert result == "sub-a"

        result_b = store.find_session_by_metadata(
            parent_session_id="parent-b",
            match={"agent_id": "a3334567890abcdef"},
        )
        assert result_b == "sub-b"


def test_find_missing_agent_returns_none() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        result = store.find_session_by_metadata(
            parent_session_id=None,
            match={"agent_id": "a999999999999999"},
        )
        assert result is None


def test_find_without_agent_id_returns_none() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        result = store.find_session_by_metadata(
            parent_session_id=None,
            match={"kind": "subagent"},
        )
        assert result is None


# ---------------------------------------------------------------------------
# Incremental index update on create
# ---------------------------------------------------------------------------


def test_create_updates_agent_index() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        config = SessionConfig(
            session_id="sess-1",
            created_at="2024-01-01T00:00:00",
            workspace_root=Path("/tmp"),
            metadata={"agent_id": "a4444567890abcdef"},
        )
        store.create("sess-1", config)
        result = store.find_session_by_metadata(
            parent_session_id=None,
            match={"agent_id": "a4444567890abcdef"},
        )
        assert result == "sess-1"


def test_create_with_parent_session_id_updates_index() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        config = SessionConfig(
            session_id="sub-1",
            created_at="2024-01-01T00:00:00",
            workspace_root=Path("/tmp"),
            metadata={"agent_id": "a5555567890abcdef"},
        )
        store.create("sub-1", config, parent_session_id="parent-1")
        result = store.find_session_by_metadata(
            parent_session_id="parent-1",
            match={"agent_id": "a5555567890abcdef"},
        )
        assert result == "sub-1"


# ---------------------------------------------------------------------------
# parent_session_id in create_session path resolution
# ---------------------------------------------------------------------------


def test_create_with_parent_uses_subagent_path() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        config = SessionConfig(
            session_id="sub-1",
            created_at="2024-01-01T00:00:00",
            workspace_root=Path("/tmp"),
        )
        store.create("sub-1", config, parent_session_id="parent-1")
        expected = Path(tmpdir) / "sessions" / "parent-1" / "subagents" / "sub-1.jsonl"
        assert expected.exists()
