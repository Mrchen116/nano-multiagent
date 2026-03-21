"""Unit tests: AgentRuntime._resolve_session_available_tools dual-path filtering (M250)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock

import pytest

from agent.core.types import ToolSpec
from agent.core.session.models import Session


def _make_spec(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"Tool {name}", input_schema={})


def _make_session(metadata: dict | None = None) -> Session:
    """Build a minimal Session with given metadata."""
    return Session(
        session_id="sess_test",
        title="test",
        metadata=metadata or {},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def _make_runtime_with_registry(tool_names: list[str], default_tool_ids: list[str] | None = None):
    """Build a minimal AgentRuntime-like object with a mock tool registry and loop."""
    from unittest.mock import MagicMock
    from agent.core.agent.runtime import AgentRuntime
    from agent.core.session.manager import SessionManager

    session_manager = MagicMock(spec=SessionManager)
    llm_client = MagicMock()

    runtime = AgentRuntime.__new__(AgentRuntime)
    # Build a minimal mock loop with _tool_registry
    mock_loop = MagicMock()
    all_specs = tuple(_make_spec(n) for n in tool_names)
    mock_loop._active_tool_specs.return_value = all_specs
    mock_registry = MagicMock()
    mock_registry.list_specs.return_value = all_specs
    mock_loop._tool_registry = mock_registry

    runtime._loop = mock_loop
    runtime._default_tool_ids = default_tool_ids
    return runtime


def test_resolve_session_tools_no_allowlist_filters_by_default_tool_ids() -> None:
    """Without tool_allowlist, _resolve_session_available_tools must filter by _default_tool_ids."""
    from agent.core.agent.runtime import AgentRuntime

    runtime = _make_runtime_with_registry(
        tool_names=["read", "write", "send_message"],
        default_tool_ids=["read", "write"],
    )
    session = _make_session(metadata={"workspace_root": "/tmp"})
    result = runtime._resolve_session_available_tools(session=session)
    names = {spec.name for spec in result}
    assert names == {"read", "write"}, f"expected {{read, write}}, got {names}"
    assert "send_message" not in names


def test_resolve_session_tools_with_allowlist_includes_send_message() -> None:
    """With tool_allowlist containing send_message, _resolve_session_available_tools must return it."""
    runtime = _make_runtime_with_registry(
        tool_names=["read", "write", "send_message"],
        default_tool_ids=["read", "write"],
    )
    session = _make_session(metadata={
        "workspace_root": "/tmp",
        "tool_allowlist": ["read", "send_message"],
    })
    result = runtime._resolve_session_available_tools(session=session)
    names = {spec.name for spec in result}
    assert names == {"read", "send_message"}, f"expected {{read, send_message}}, got {names}"


def test_resolve_session_tools_no_allowlist_no_default_returns_all() -> None:
    """Without allowlist and without _default_tool_ids, all tools are returned (platform default behavior)."""
    runtime = _make_runtime_with_registry(
        tool_names=["read", "write", "send_message"],
        default_tool_ids=None,
    )
    session = _make_session(metadata={"workspace_root": "/tmp"})
    result = runtime._resolve_session_available_tools(session=session)
    names = {spec.name for spec in result}
    assert "read" in names
    assert "write" in names
    assert "send_message" in names
