"""Unit tests for AgentRuntime._ensure_memory_snapshot + _invalidate_memory_snapshot.

Validates:
- _ensure_memory_snapshot method exists
- _invalidate_memory_snapshot method exists
- _memory_snapshots dict is initialized on AgentRuntime
- feature gate: memory_curation=False → returns (None, None)
- workspace missing → returns (None, None)
- workspace_config_dirname missing → returns (None, None)
- cache: second call returns same snapshot without re-reading disk
- invalidate clears cache so next call re-freezes
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.core.agent.runtime import AgentRuntime


def _make_minimal_runtime(tmp_path: Path) -> AgentRuntime:
    from agent.core.session.manager import SessionManager
    from agent.core.session.jsonl_store import JsonlSessionStore

    store = JsonlSessionStore(data_dir=None, workspace_config_dirname=".nanocode")
    session_manager = SessionManager(store=store)
    return AgentRuntime(
        session_manager=session_manager,
        repo_root=tmp_path,
    )


def test_runtime_has_memory_snapshots_dict(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    assert hasattr(runtime, "_memory_snapshots")
    assert isinstance(runtime._memory_snapshots, dict)


def test_runtime_has_ensure_memory_snapshot(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    assert hasattr(runtime, "_ensure_memory_snapshot")
    assert callable(runtime._ensure_memory_snapshot)


def test_runtime_has_invalidate_memory_snapshot(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    assert hasattr(runtime, "_invalidate_memory_snapshot")
    assert callable(runtime._invalidate_memory_snapshot)


def test_ensure_memory_snapshot_gate_memory_curation_off(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    metadata = {
        "workspace_root": str(tmp_path),
        "workspace_config_dirname": ".nanoassistant",
        "agent_features": {"memory_curation": False},
    }
    snapshot = runtime._ensure_memory_snapshot("sess-1", metadata)
    assert snapshot["memory_block"] is None
    assert snapshot["user_profile_block"] is None


def test_ensure_memory_snapshot_no_workspace_root(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    metadata = {"workspace_config_dirname": ".nanoassistant"}
    snapshot = runtime._ensure_memory_snapshot("sess-2", metadata)
    assert snapshot["memory_block"] is None
    assert snapshot["user_profile_block"] is None


def test_ensure_memory_snapshot_no_dirname(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    metadata = {"workspace_root": str(tmp_path)}
    snapshot = runtime._ensure_memory_snapshot("sess-3", metadata)
    assert snapshot["memory_block"] is None
    assert snapshot["user_profile_block"] is None


def test_ensure_memory_snapshot_cache_hit(tmp_path: Path) -> None:
    """Second call returns cached result without re-reading disk."""
    runtime = _make_minimal_runtime(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    metadata = {
        "workspace_root": str(workspace),
        "workspace_config_dirname": ".nanoassistant",
    }
    # No memory files present → both None
    snapshot1 = runtime._ensure_memory_snapshot("sess-4", metadata)
    snapshot2 = runtime._ensure_memory_snapshot("sess-4", metadata)
    # Same object (or at least same content) due to caching
    assert snapshot1 == snapshot2
    # Cache should have the entry
    assert "sess-4" in runtime._memory_snapshots


def test_invalidate_memory_snapshot_clears_cache(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    runtime._memory_snapshots["sess-5"] = {"memory_block": "old", "user_profile_block": None}
    runtime._invalidate_memory_snapshot("sess-5")
    assert "sess-5" not in runtime._memory_snapshots


def test_invalidate_nonexistent_is_noop(tmp_path: Path) -> None:
    runtime = _make_minimal_runtime(tmp_path)
    # Should not raise
    runtime._invalidate_memory_snapshot("nonexistent-session")


def test_ensure_memory_snapshot_reads_memory_files(tmp_path: Path) -> None:
    """When memory files exist, snapshot contains rendered content."""
    runtime = _make_minimal_runtime(tmp_path)
    workspace = tmp_path / "workspace"
    memory_dir = workspace / ".nanoassistant" / "memory"
    memory_dir.mkdir(parents=True)

    # Create MEMORY.md with content
    (memory_dir / "MEMORY.md").write_text(
        "§ memory\n- Python venv is always in .venv/\n",
        encoding="utf-8",
    )

    metadata = {
        "workspace_root": str(workspace),
        "workspace_config_dirname": ".nanoassistant",
    }
    snapshot = runtime._ensure_memory_snapshot("sess-6", metadata)
    # memory_block should contain the rendered content
    assert snapshot["memory_block"] is not None
    assert "venv" in snapshot["memory_block"]
