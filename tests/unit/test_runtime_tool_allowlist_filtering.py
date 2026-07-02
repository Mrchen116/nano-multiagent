"""Unit tests: AgentRuntime._resolve_session_available_tools dual-path filtering (M250)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from agent.core.session.models import Session
from agent.core.types import ToolSpec


def _make_spec(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"Tool {name}", input_schema={})


def _make_session(
    tool_allowlist: list[str] | None = None,
    workspace_root: str = "/tmp",
) -> Session:
    return Session(
        session_id="test-session",
        status="active",
        created_at="2024-01-01T00:00:00Z",
        workspace_root=Path(workspace_root),
        system_prompt=None,
        skills=None,
        tool_allowlist=tuple(tool_allowlist) if tool_allowlist is not None else None,
    )


def _make_runtime_with_specs(
    tool_names: list[str], default_tool_ids: list[str] | None = None
):
    """Build a minimal AgentRuntime-like object with a mock loop returning fixed specs."""
    from agent.core.agent.runtime import AgentRuntime

    runtime = AgentRuntime.__new__(AgentRuntime)
    mock_loop = MagicMock()
    all_specs = tuple(_make_spec(n) for n in tool_names)
    mock_loop.active_tool_specs.return_value = all_specs
    runtime._loop = mock_loop
    runtime._default_tool_ids = default_tool_ids
    return runtime


def test_resolve_session_tools_no_allowlist_filters_by_default_tool_ids() -> None:
    """Without tool_allowlist, _resolve_session_available_tools must filter by _default_tool_ids."""
    runtime = _make_runtime_with_specs(
        tool_names=["read", "write", "send_message"],
        default_tool_ids=["read", "write"],
    )
    session = _make_session(tool_allowlist=None)
    result = runtime._resolve_session_available_tools(session)
    names = {spec.name for spec in result}
    assert names == {"read", "write"}, f"expected {{read, write}}, got {names}"
    assert "send_message" not in names


def test_unconfigured_pa_defaults_include_skill_view_without_widening_explicit_allowlist() -> (
    None
):
    """Empty PA allowlist uses product defaults; explicit allowlist stays exact."""
    from personal_assistant.product import DEFAULT_TOOL_IDS

    runtime = _make_runtime_with_specs(
        tool_names=["read", "skill_manage", "skill_view", "send_message"],
        default_tool_ids=list(DEFAULT_TOOL_IDS),
    )

    default_session = _make_session(tool_allowlist=None)
    default_names = {spec.name for spec in runtime._resolve_session_available_tools(default_session)}
    assert "skill_view" in default_names

    explicit_session = _make_session(tool_allowlist=["read", "skill_manage"])
    explicit_names = {spec.name for spec in runtime._resolve_session_available_tools(explicit_session)}
    assert explicit_names == {"read", "skill_manage"}
    assert "skill_view" not in explicit_names


def test_resolve_session_tools_with_allowlist_includes_send_message() -> None:
    """With tool_allowlist containing send_message, _resolve_session_available_tools must return it."""
    runtime = _make_runtime_with_specs(
        tool_names=["read", "write", "send_message"],
        default_tool_ids=["read", "write"],
    )
    session = _make_session(tool_allowlist=["read", "send_message"])
    result = runtime._resolve_session_available_tools(session)
    names = {spec.name for spec in result}
    assert names == {"read", "send_message"}, (
        f"expected {{read, send_message}}, got {names}"
    )


def test_resolve_session_tools_no_allowlist_no_default_returns_all() -> None:
    """Without allowlist and without _default_tool_ids, all tools are returned (platform default behavior)."""
    runtime = _make_runtime_with_specs(
        tool_names=["read", "write", "send_message"],
        default_tool_ids=None,
    )
    session = _make_session(tool_allowlist=None)
    result = runtime._resolve_session_available_tools(session)
    names = {spec.name for spec in result}
    assert "read" in names
    assert "write" in names
    assert "send_message" in names
