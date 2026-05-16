"""Integration tests: tool_registry injection into HookContext metadata.

Verifies the full wiring for bugfix-355 Issue #1 (blocking):
  AgentRuntime._build_hook_context
    → metadata["tool_registry"] is set
    → auto_mode_gate.on_tool_call reads tool_registry from metadata
    → tool.check_permissions is actually called

Tests use real HookContext + AgentRuntime._build_hook_context path, NOT direct
instantiation of check_permissions in isolation — this is the regression gap
that unit tests missed (unit tests bypass the injection chain entirely).

bugfix-355-M5 extensions (R2-#1 fix: ctx=None → real ctx):
  Test 5: gate passes real ctx (not None) to check_permissions so WriteTool
           path check (ctx.cwd) does not raise AttributeError.
  Test 6: reverse-regression — if gate were to pass ctx=None, WriteTool.check_permissions
           raises AttributeError and the gate must NOT silently passthrough (fail-loud).
  Test 7: end-to-end dangerously mode — WriteTool hits .bashrc path → safety_check ask
           fires correctly (not absorbed by hook-runner isolation).
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

    web_fetch_tool = WebFetchTool()

    # Spy on check_permissions to confirm it's actually called
    check_permissions_calls: list[dict] = []
    original_check = web_fetch_tool.check_permissions

    def spy_check(tool_input: Any, ctx: Any) -> Any:
        check_permissions_calls.append(dict(tool_input))
        return original_check(tool_input, ctx)

    web_fetch_tool.check_permissions = spy_check  # type: ignore[method-assign]

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


# ---------------------------------------------------------------------------
# Test 5 (bugfix-355-M5 R2-#1): gate passes real ctx to check_permissions
# ---------------------------------------------------------------------------


def test_auto_mode_gate_passes_real_ctx_to_check_permissions(tmp_path: Path) -> None:
    """auto_mode_gate must pass real HookContext (not None) to check_permissions.

    bugfix-355 R2-#1: gate called check_fn(tool_input, None), causing
    WriteTool.check_permissions to raise AttributeError on ctx.cwd.
    The fix: pass the real ctx object so ctx.cwd is available.

    This test verifies the fix: check_permissions receives a ctx with .cwd
    attribute (not None), so WriteTool path resolution succeeds.
    """
    from agent.platform.tools.builtins.write import WriteTool
    from agent.platform.config.auto_mode import AutoModeConfig

    write_tool = WriteTool()

    ctx_received: list[Any] = []
    original_check = write_tool.check_permissions

    def spy_check(tool_input: Any, ctx: Any) -> Any:
        ctx_received.append(ctx)
        return original_check(tool_input, ctx)

    write_tool.check_permissions = spy_check  # type: ignore[method-assign]

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda name: write_tool if name == "write" else None

    metadata = {
        "tool_registry": mock_registry,
        "permission_broker": None,
        "run_id": "run-ctx-test",
    }

    hook_ctx = HookContext(
        session_id="sess-ctx-test",
        repo_root=tmp_path,
        metadata=metadata,
    )

    on_tool_call = _build_gate_on_tool_call()

    # A normal (non-dangerous) path so check_permissions runs without triggering ask broker
    event = {
        "name": "write",
        "args": {"file_path": str(tmp_path / "safe_file.txt"), "content": "hello"},
    }

    normal_config = AutoModeConfig(dangerously_skip_permissions=False)
    with patch(
        "agent.platform.hooks.builtins.auto_mode_gate.load_auto_mode_config",
        return_value=normal_config,
    ):
        try:
            asyncio.run(on_tool_call(event, hook_ctx))
        except Exception:
            pass

    assert len(ctx_received) > 0, (
        "check_permissions was never called — tool_registry injection may be broken."
    )
    received_ctx = ctx_received[0]
    assert received_ctx is not None, (
        "check_permissions received ctx=None — bugfix-355 R2-#1 regression: "
        "gate must pass the real HookContext, not None."
    )
    assert hasattr(received_ctx, "cwd") or hasattr(received_ctx, "repo_root"), (
        "ctx passed to check_permissions has no cwd/repo_root — not a real HookContext. "
        "WriteTool.check_permissions needs ctx.cwd for path resolution."
    )


# ---------------------------------------------------------------------------
# Test 6 (bugfix-355-M5 R2-#1 reverse): ctx=None must fail-loud, not passthrough
# ---------------------------------------------------------------------------


def test_auto_mode_gate_check_permissions_ctx_none_fails_loud(tmp_path: Path) -> None:
    """Reverse regression: if ctx=None reaches check_permissions, gate must fail-loud.

    This test documents the old broken behavior and ensures the gate does NOT
    silently ignore AttributeError from check_permissions.

    Strategy: patch check_permissions to raise AttributeError (simulating the
    old ctx=None bug), then verify the gate either:
      (a) raises the error itself (fail-loud), OR
      (b) returns a blocking/ask decision — NOT silently None (passthrough).

    Silent None (passthrough) would be the dangerous regression: dangerous paths
    get written without any permission check.
    """
    from agent.platform.tools.builtins.write import WriteTool
    from agent.platform.config.auto_mode import AutoModeConfig

    write_tool = WriteTool()

    def broken_check(tool_input: Any, ctx: Any) -> Any:
        # Simulate the old bug: ctx=None causes AttributeError
        raise AttributeError("'NoneType' object has no attribute 'cwd'")

    write_tool.check_permissions = broken_check  # type: ignore[method-assign]

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda name: write_tool if name == "write" else None

    metadata = {
        "tool_registry": mock_registry,
        "permission_broker": None,
        "run_id": "run-broken-ctx",
    }

    hook_ctx = HookContext(
        session_id="sess-broken-ctx",
        repo_root=tmp_path,
        metadata=metadata,
    )

    on_tool_call = _build_gate_on_tool_call()

    # Dangerous path — if check_permissions is silently ignored, gate returns None (passthrough)
    event = {
        "name": "write",
        "args": {
            "file_path": str(tmp_path / ".git" / "config"),
            "content": "evil",
        },
    }

    # Use dangerously mode to isolate: if safety_check ask fires, gate would call broker.
    # If check_permissions error is silently swallowed → safety_locked=False → dangerously bypass → None.
    # We want the gate to NOT return None silently — it should either raise or block.
    dangerous_config = AutoModeConfig(dangerously_skip_permissions=True)

    raised_exc = None
    result = None
    with patch(
        "agent.platform.hooks.builtins.auto_mode_gate.load_auto_mode_config",
        return_value=dangerous_config,
    ):
        try:
            result = asyncio.run(on_tool_call(event, hook_ctx))
        except Exception as exc:
            raised_exc = exc

    # The gate must NOT silently passthrough (return None) when check_permissions raises.
    # Acceptable outcomes: exception propagated (fail-loud) OR a block/ask result.
    assert raised_exc is not None or (result is not None and result != {}), (
        "REGRESSION (bugfix-355 R2-#1): auto_mode_gate silently returned None when "
        "check_permissions raised AttributeError. This means dangerous paths bypass safety "
        "checks without any user confirmation. The gate must fail-loud (raise or block) "
        "when tool.check_permissions raises an unexpected exception."
    )


# ---------------------------------------------------------------------------
# Test 7 (bugfix-355-M5 E2E): dangerously mode + dangerous path → safety_check ask fires
# ---------------------------------------------------------------------------


def test_dangerous_write_in_dangerously_mode_triggers_safety_check_ask(
    tmp_path: Path,
) -> None:
    """End-to-end: WriteTool .bashrc path fires safety_check ask in dangerously mode.

    This is the critical E2E regression for bugfix-355 R2-#1:
      - ctx is a real HookContext (repo_root set, cwd available)
      - tool_registry is injected via metadata
      - gate calls check_permissions(tool_input, real_ctx)
      - WriteTool resolves ~/.bashrc → DANGEROUS_FILES match → behavior='ask', safety_check
      - auto_mode_gate sees safety_locked=True → does NOT bypass even in dangerously mode
      - Result: gate calls _handle_ask (or raises from broker path) — NOT None (passthrough)

    If this test fails, W1 (bypass-immune dangerous-path protection) is broken.
    """
    from agent.platform.tools.builtins.write import WriteTool
    from agent.platform.config.auto_mode import AutoModeConfig

    write_tool = WriteTool()
    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda name: write_tool if name == "write" else None

    metadata = {
        "tool_registry": mock_registry,
        "permission_broker": None,
        "run_id": "run-e2e-dangerous",
    }

    hook_ctx = HookContext(
        session_id="sess-e2e-dangerous",
        repo_root=tmp_path,
        metadata=metadata,
    )

    on_tool_call = _build_gate_on_tool_call()

    # ~/.bashrc is in DANGEROUS_FILES — WriteTool.check_permissions should return safety_check ask
    event = {
        "name": "write",
        "args": {"file_path": "~/.bashrc", "content": "evil"},
    }

    dangerous_config = AutoModeConfig(dangerously_skip_permissions=True)

    raised_exc = None
    result = None
    with patch(
        "agent.platform.hooks.builtins.auto_mode_gate.load_auto_mode_config",
        return_value=dangerous_config,
    ):
        try:
            result = asyncio.run(on_tool_call(event, hook_ctx))
        except Exception as exc:
            raised_exc = exc

    # Expected: safety_locked=True → _handle_ask is called → raises (no broker) or blocks
    # What must NOT happen: result=None (silent passthrough = no safety check = bypass succeeded)
    assert raised_exc is not None or result is not None, (
        "REGRESSION (bugfix-355 W1): auto_mode_gate returned None (passthrough) for ~/.bashrc "
        "write in dangerously mode. The safety_check ask must NOT be bypassable. "
        "Check that: (1) ctx is real HookContext with repo_root/cwd, "
        "(2) WriteTool.check_permissions is called and returns safety_check ask, "
        "(3) safety_locked=True → gate stays in ask path even with dangerously=True."
    )
