"""Integration tests: tool_registry injection into HookContext metadata.

Verifies the full wiring for bugfix-355 Issue #1 (blocking):
  AgentRuntime._build_hook_context
    → metadata["tool_registry"] is set
    → auto_mode_gate.on_tool_call reads tool_registry from metadata
    → tool.check_permissions is actually called

Tests use real HookContext + AgentRuntime._build_hook_context path, NOT direct
instantiation of check_permissions in isolation — this is the regression gap
that unit tests missed (unit tests bypass the injection chain entirely).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock, patch

import pytest

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookAPI, HookRegistry
from agent.core.agent.runtime import AgentRuntime
from agent.platform.http_api.app import create_app
from agent.platform.permissions.broker import PermissionBroker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_gate_on_tool_call():
    """Register auto_mode_gate into a HookRegistry and extract on_tool_call handler."""
    import agent.platform.hooks.builtins.auto_mode_gate as gate_module

    registry = HookRegistry()
    api = HookAPI(registry, source="builtin", module_name="auto_mode_gate", file_path=None)
    gate_module.setup(api)

    # Extract the registered tool_call handler
    registrations = registry._registrations.get("tool_call", [])
    assert registrations, "auto_mode_gate must register a tool_call handler via setup()"
    return registrations[0].handler


def _build_runtime(tmp_path: Path) -> AgentRuntime:
    """Build a minimal AgentRuntime mirroring the create_app wiring path."""
    from agent.platform.hooks.loader import build_hook_registry
    from agent.core.hooks.runner import HookRunner
    from agent.platform.config.auto_mode import AutoModeConfig

    broker = PermissionBroker(config=AutoModeConfig())
    hook_registry = build_hook_registry(repo_root=tmp_path)
    hook_runner = HookRunner(registry=hook_registry)

    runtime = AgentRuntime(
        session_manager=MagicMock(),
        hook_runner=hook_runner,
        repo_root=tmp_path,
        permission_broker=broker,
    )
    return runtime


# ---------------------------------------------------------------------------
# Test 1: metadata["tool_registry"] is present in HookContext built by runtime
# ---------------------------------------------------------------------------


def test_build_hook_context_injects_tool_registry(tmp_path: Path) -> None:
    """runtime._build_hook_context must inject tool_registry into metadata.

    This is the root cause of bugfix-355 Issue #1 (blocking): tool_registry was
    never put into metadata, so auto_mode_gate.on_tool_call always got None and
    check_permissions was never called.

    After the fix, metadata["tool_registry"] must be a non-None object that
    supports .get(tool_name) so the gate can call tool.check_permissions.
    """
    runtime = _build_runtime(tmp_path)

    # Simulate binding a tool_registry (mirrors create_app bind_tool_registry path)
    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    runtime.bind_tool_registry(mock_registry)

    hook_ctx = runtime._build_hook_context(
        session_id="test-session",
        turn_id="turn-1",
        metadata={"run_id": "run-1"},
    )

    injected = hook_ctx.metadata.get("tool_registry")
    assert injected is not None, (
        "metadata['tool_registry'] is None after _build_hook_context — "
        "runtime must inject tool_registry into HookContext metadata so "
        "auto_mode_gate can call tool.check_permissions. "
        "Fix: add resolved_metadata['tool_registry'] = self._tool_registry in _build_hook_context."
    )


# ---------------------------------------------------------------------------
# Test 2: auto_mode_gate calls WriteTool.check_permissions via metadata chain
# ---------------------------------------------------------------------------


def test_auto_mode_gate_calls_write_tool_check_permissions_via_metadata(
    tmp_path: Path,
) -> None:
    """auto_mode_gate must call WriteTool.check_permissions for dangerous write paths.

    This is the end-to-end regression test for Issue #1. Unit tests passed because
    they called check_permissions directly, bypassing the metadata injection chain.
    This test exercises: metadata["tool_registry"] → gate → tool.check_permissions.

    With tool_registry injected, .git/config write triggers safety_check → ask,
    and even in dangerously mode, the gate must consult tool_registry.get("write").
    Without the fix, tool_registry is None and get() is never called.
    """
    from agent.platform.tools.builtins.write import WriteTool
    from agent.platform.config.auto_mode import AutoModeConfig

    write_tool = WriteTool()

    # Mock registry that returns WriteTool for "write"
    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda name: write_tool if name == "write" else None

    metadata = {
        "tool_registry": mock_registry,
        "permission_broker": None,
        "run_id": "run-test",
        "cwd": str(tmp_path),
    }

    hook_ctx = HookContext(
        session_id="sess-test",
        repo_root=tmp_path,
        metadata=metadata,
    )

    on_tool_call = _build_gate_on_tool_call()

    # .git/config is a dangerous path — safety_check ask should fire even in dangerously mode
    event = {
        "name": "write",
        "args": {"file_path": str(tmp_path / ".git" / "config"), "content": "evil"},
    }

    dangerous_config = AutoModeConfig(dangerously_skip_permissions=True)

    with patch(
        "agent.platform.hooks.builtins.auto_mode_gate.load_auto_mode_config",
        return_value=dangerous_config,
    ):
        # safety_locked path tries to call _handle_ask → needs broker/permission_requester
        # We expect either a block result or an exception from the ask path
        # The key assertion is that tool_registry.get("write") was called
        try:
            result = asyncio.run(on_tool_call(event, hook_ctx))
        except Exception:
            pass  # exception from ask path without broker is acceptable

    mock_registry.get.assert_called_with("write"), (
        "tool_registry.get('write') was NOT called — this means tool_registry was None "
        "in HookContext metadata. Fix: inject tool_registry in _build_hook_context. "
        "This is the blocking Issue #1 root cause."
    )


# ---------------------------------------------------------------------------
# Test 3: auto_mode_gate calls WebFetchTool.check_permissions via metadata chain
# ---------------------------------------------------------------------------


def test_auto_mode_gate_calls_web_fetch_check_permissions_for_preapproved_host(
    tmp_path: Path,
) -> None:
    """auto_mode_gate calls WebFetchTool.check_permissions so preapproved → allow.

    Without tool_registry injection, web_fetch always falls to the classifier.
    With the fix, docs.python.org (preapproved) should get behavior='allow'
    via check_permissions, returning None from the gate (allow, no classifier).
    """
    from agent.platform.tools.builtins.web_fetch import WebFetchTool
    from agent.platform.config.auto_mode import AutoModeConfig

    web_fetch_tool = WebFetchTool(config=AutoModeConfig())

    # Spy on check_permissions to confirm it's actually called
    check_permissions_calls: list[dict] = []
    original_check = web_fetch_tool.check_permissions.__func__  # type: ignore[attr-defined]

    def spy_check(self: Any, tool_input: Any, ctx: Any) -> Any:
        check_permissions_calls.append(dict(tool_input))
        return original_check(self, tool_input, ctx)

    web_fetch_tool.__class__.check_permissions = spy_check  # type: ignore[assignment]

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda name: web_fetch_tool if name == "web_fetch" else None

    metadata = {
        "tool_registry": mock_registry,
        "permission_broker": None,
        "run_id": "run-webfetch-test",
        "cwd": str(tmp_path),
    }

    hook_ctx = HookContext(
        session_id="sess-webfetch",
        repo_root=tmp_path,
        metadata=metadata,
    )

    on_tool_call = _build_gate_on_tool_call()

    event = {
        "name": "web_fetch",
        "args": {"url": "https://docs.python.org/3/tutorial/"},
    }

    normal_config = AutoModeConfig(dangerously_skip_permissions=False)
    with patch(
        "agent.platform.hooks.builtins.auto_mode_gate.load_auto_mode_config",
        return_value=normal_config,
    ):
        result = asyncio.run(on_tool_call(event, hook_ctx))

    # Restore original method
    del web_fetch_tool.__class__.check_permissions

    assert len(check_permissions_calls) > 0, (
        "WebFetchTool.check_permissions was NEVER called via auto_mode_gate. "
        "tool_registry must be None in metadata — blocking Issue #1 still present."
    )
    # docs.python.org is preapproved → gate returns None (allow)
    assert result is None, (
        f"Expected None (allow) for preapproved docs.python.org, got {result!r}. "
        "check_permissions returned unexpected behavior."
    )


# ---------------------------------------------------------------------------
# Test 4: create_app wires tool_registry into runtime._build_hook_context
# ---------------------------------------------------------------------------


def test_create_app_tool_registry_accessible_from_hook_metadata(tmp_path: Path) -> None:
    """create_app must wire tool_registry into runtime so HookContext gets it.

    Verifies the full assembly path: create_app → bind_tool_registry →
    _build_hook_context → metadata['tool_registry'] is populated.

    This is the primary integration gate for the fix.
    """
    app = create_app(repo_root=tmp_path)
    runtime = app.state.agent_runtime

    hook_ctx = runtime._build_hook_context(
        session_id="test-sess",
        metadata={"run_id": "test-run"},
    )

    injected = hook_ctx.metadata.get("tool_registry")
    assert injected is not None, (
        "After create_app(), runtime._build_hook_context must inject tool_registry into "
        "HookContext metadata. Without this, auto_mode_gate never calls tool.check_permissions "
        "and W1/S1 bypass-immune safety checks are silently disabled."
    )
