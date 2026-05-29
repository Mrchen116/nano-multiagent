"""Unit tests for MemoryTool per-session isolation.

MemoryTool must derive memory_root from session_metadata at call time (not at
construction) so each session's writes land in its own workspace directory.

Validates:
- MemoryTool._resolve_memory_root uses derive_memory_root from session_metadata
- workspace_root + workspace_config_dirname present → correct derived path
- _fixed_memory_root still works for tests (test scaffold)
- Missing workspace_root or dirname → raises RuntimeError (no silent fallback)
- bootstrap.py no longer passes memory_root to MemoryTool constructor
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.core.memory.path import derive_memory_root
from agent.platform.tools.builtins.memory import MemoryTool


def _make_ctx(workspace_root: str | None, dirname: str | None, session_id: str = "s1") -> MagicMock:
    ctx = MagicMock()
    ctx.session_id = session_id
    metadata: dict = {}
    if workspace_root is not None:
        metadata["workspace_root"] = workspace_root
    if dirname is not None:
        metadata["workspace_config_dirname"] = dirname
    ctx.session_metadata = metadata
    return ctx


def test_resolve_memory_root_uses_derive_memory_root(tmp_path: Path) -> None:
    workspace = str(tmp_path / "workspace")
    dirname = ".nanoassistant"
    ctx = _make_ctx(workspace, dirname)

    tool = MemoryTool()  # no fixed memory_root
    result = tool._resolve_memory_root(ctx)

    expected = derive_memory_root(Path(workspace), dirname)
    assert result == expected


def test_resolve_memory_root_lc_dirname(tmp_path: Path) -> None:
    workspace = str(tmp_path / "lc-workspace")
    dirname = ".nanocode"
    ctx = _make_ctx(workspace, dirname)

    tool = MemoryTool()
    result = tool._resolve_memory_root(ctx)
    assert result == Path(workspace) / ".nanocode" / "memory"


def test_resolve_memory_root_fixed_takes_precedence(tmp_path: Path) -> None:
    fixed_root = tmp_path / "fixed"
    ctx = _make_ctx(str(tmp_path / "workspace"), ".nanoassistant")

    tool = MemoryTool(memory_root=fixed_root)
    result = tool._resolve_memory_root(ctx)
    assert result == fixed_root


def test_resolve_memory_root_raises_when_workspace_root_missing() -> None:
    ctx = _make_ctx(None, ".nanoassistant")
    tool = MemoryTool()
    with pytest.raises(RuntimeError, match="memory_root cannot be resolved"):
        tool._resolve_memory_root(ctx)


def test_resolve_memory_root_raises_when_dirname_missing(tmp_path: Path) -> None:
    ctx = _make_ctx(str(tmp_path), None)
    tool = MemoryTool()
    with pytest.raises(RuntimeError, match="memory_root cannot be resolved"):
        tool._resolve_memory_root(ctx)


def test_bootstrap_memory_tool_constructed_without_fixed_root() -> None:
    """bootstrap.py should construct MemoryTool() without memory_root argument."""
    import importlib
    import inspect
    import ast

    import agent.platform.bootstrap as _bootstrap_module
    bootstrap_path = Path(_bootstrap_module.__file__)
    source = bootstrap_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find all MemoryTool(...) calls in bootstrap.py
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            func_name = getattr(func, "id", None) or getattr(func, "attr", None)
            if func_name == "MemoryTool":
                # Must not have memory_root keyword arg
                kwarg_names = [kw.arg for kw in node.keywords]
                assert "memory_root" not in kwarg_names, (
                    f"bootstrap.py MemoryTool() call at line {node.lineno} "
                    f"must not pass memory_root= (should be derived per-session)"
                )
