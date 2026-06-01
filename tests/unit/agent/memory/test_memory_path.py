"""Unit tests for core/memory/path.py — derive_memory_root helper.

Validates:
- PA dirname (.nanoassistant) derives correct memory_root
- LC dirname (.nanocode) derives correct memory_root
- Path is always <workspace>/<dirname>/memory/
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.memory.path import derive_memory_root


def test_derive_memory_root_pa(tmp_path: Path) -> None:
    workspace = tmp_path / "agent-workspace"
    result = derive_memory_root(workspace, ".nanoassistant")
    assert result == workspace / ".nanoassistant" / "memory"


def test_derive_memory_root_lc(tmp_path: Path) -> None:
    workspace = tmp_path / "code-workspace"
    result = derive_memory_root(workspace, ".nanocode")
    assert result == workspace / ".nanocode" / "memory"


def test_derive_memory_root_returns_path_object(tmp_path: Path) -> None:
    result = derive_memory_root(tmp_path, ".nanoassistant")
    assert isinstance(result, Path)


def test_derive_memory_root_does_not_create_dirs(tmp_path: Path) -> None:
    workspace = tmp_path / "nonexistent-workspace"
    result = derive_memory_root(workspace, ".nanoassistant")
    assert not result.exists()
