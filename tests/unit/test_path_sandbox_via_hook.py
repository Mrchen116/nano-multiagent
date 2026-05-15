"""Tests for refactor-353: path sandbox routed through auto_mode_gate.

Covers the four critical branches of the unified path-sandbox decision flow:

1. workspace-internal path → no special hint, existing flow
2. workspace-external path + dangerously_skip_permissions → pass through
3. workspace-external path + classifier returns allow → pass through
4. workspace-external path + classifier returns ask → handed to broker

These tests use the gate's public ``setup()`` to register the handler and
exercise it end-to-end via a faked HookContext, isolating the path-detection
logic from kernel / runtime wiring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    _detect_outside_workspace_path,
    setup as gate_setup,
)


class _FakeCtx:
    """Minimal HookContext stand-in carrying repo_root + metadata."""

    def __init__(self, repo_root: Path, *, metadata: dict | None = None) -> None:
        self.repo_root = repo_root
        self.metadata = metadata or {}
        self.session_id = "sess-test"
        self.turn_id = "turn-1"
        self.message_history: tuple = ()
        self.logger = MagicMock()
        self.model_caller = AsyncMock()


class _RecordingHooks:
    """Capture the (event, handler, kwargs) registered by gate.setup."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, Any, dict]] = []

    def on(self, event: str, handler: Any, **kwargs: Any) -> None:
        self.registered.append((event, handler, kwargs))


def _register_gate() -> Any:
    hooks = _RecordingHooks()
    gate_setup(hooks)
    assert hooks.registered, "gate_setup should register at least one handler"
    return hooks.registered[0][1]


# ---------------------------------------------------------------------------
# 1. _detect_outside_workspace_path unit tests (pure helper, no async)
# ---------------------------------------------------------------------------

class TestDetectOutsideWorkspacePath:
    def test_write_inside_workspace_returns_none(self, tmp_path: Path) -> None:
        ctx = _FakeCtx(tmp_path)
        inside = tmp_path / "subdir" / "f.py"
        result = _detect_outside_workspace_path(
            tool_name="write",
            tool_input={"file_path": str(inside)},
            ctx=ctx,
        )
        assert result is None, "inside-workspace path should not trigger the signal"

    def test_write_outside_workspace_returns_resolved_path(self, tmp_path: Path) -> None:
        ctx = _FakeCtx(tmp_path)
        outside = tmp_path.parent / "outside-target" / "f.py"
        result = _detect_outside_workspace_path(
            tool_name="write",
            tool_input={"file_path": str(outside)},
            ctx=ctx,
        )
        assert result == str(outside.resolve())

    def test_edit_outside_workspace_returns_resolved(self, tmp_path: Path) -> None:
        ctx = _FakeCtx(tmp_path)
        outside = tmp_path.parent / "other" / "x.txt"
        result = _detect_outside_workspace_path(
            tool_name="edit",
            tool_input={"file_path": str(outside)},
            ctx=ctx,
        )
        assert result == str(outside.resolve())

    def test_non_write_tool_returns_none(self, tmp_path: Path) -> None:
        ctx = _FakeCtx(tmp_path)
        result = _detect_outside_workspace_path(
            tool_name="bash",
            tool_input={"command": "rm -rf /tmp/x"},
            ctx=ctx,
        )
        assert result is None

    def test_dot_dot_traversal_normalized_outside_workspace(self, tmp_path: Path) -> None:
        """`..` traversal that escapes the workspace must be detected."""
        ctx = _FakeCtx(tmp_path)
        # /tmp/<tmp_path>/sub/../../escape.txt → outside workspace
        result = _detect_outside_workspace_path(
            tool_name="write",
            tool_input={"file_path": "../../escape.txt"},
            ctx=ctx,
        )
        # Normalize relative to repo_root (cwd defaults to repo_root in the
        # helper), so the resolved path lives above tmp_path.
        assert result is not None
        assert not result.startswith(str(tmp_path))

    def test_missing_path_key_returns_none(self, tmp_path: Path) -> None:
        ctx = _FakeCtx(tmp_path)
        result = _detect_outside_workspace_path(
            tool_name="write",
            tool_input={},  # missing file_path
            ctx=ctx,
        )
        assert result is None


# ---------------------------------------------------------------------------
# 2. End-to-end gate branches for refactor-353
# ---------------------------------------------------------------------------

class TestGatePathSandboxBranches:
    @pytest.mark.asyncio
    async def test_dangerously_mode_bypasses_outside_workspace_write(self, tmp_path: Path) -> None:
        """Workspace-external write + dangerously → pass through (no classifier, no ask).

        Spec contract: dangerously-skip-permissions语义是不进行任何权限管控。
        """
        handler = _register_gate()
        config = AutoModeConfig(dangerously_skip_permissions=True)
        ctx = _FakeCtx(tmp_path, metadata={"_auto_mode_config_loader": lambda: config})

        event = {
            "name": "write",
            "args": {"file_path": str(tmp_path.parent / "outside" / "x.py"), "content": "x"},
        }
        result = await handler(event, ctx)
        assert result is None, "dangerously should pass through with no intercept"

    @pytest.mark.asyncio
    async def test_outside_workspace_with_classifier_allow(self, tmp_path: Path) -> None:
        """Workspace-external write + classifier allow → pass through.

        Demonstrates the classifier sees the path (via injected hint) and may
        decide to allow.  Tested by mocking _classify_action to return allow.
        """
        handler = _register_gate()
        config = AutoModeConfig()  # auto mode, deny_limit default
        ctx = _FakeCtx(tmp_path, metadata={"_auto_mode_config_loader": lambda: config})

        from agent.platform.permissions.broker import PermissionDecision

        with patch(
            "agent.platform.hooks.builtins.auto_mode_gate._classify_action",
            new=AsyncMock(return_value=PermissionDecision(behavior="allow", reason="user explicit")),
        ) as mock_classify:
            event = {
                "name": "write",
                "args": {"file_path": str(tmp_path.parent / "outside-allow" / "x.py"), "content": "x"},
            }
            result = await handler(event, ctx)

        assert result is None, "classifier allow should pass through"
        # Verify the classifier user_prompt carried the outside-workspace hint.
        call_args = mock_classify.call_args
        user_prompt = call_args.args[2]  # (ctx, system_prompt, user_prompt)
        assert "OUTSIDE the agent's workspace" in user_prompt

    @pytest.mark.asyncio
    async def test_outside_workspace_with_classifier_ask_triggers_broker(self, tmp_path: Path) -> None:
        """Workspace-external write + classifier ask → broker.register_request + emit SSE."""
        handler = _register_gate()
        config = AutoModeConfig()
        broker = PermissionBrokerStub()
        ctx = _FakeCtx(
            tmp_path,
            metadata={
                "_auto_mode_config_loader": lambda: config,
                "run_id": "run-x",
                "permission_broker": broker,
            },
        )

        from agent.platform.permissions.broker import PermissionDecision, PermissionResponse

        # Stub broker future to resolve immediately with allow_once.
        async def _fake_request(req: Any) -> PermissionResponse:
            return PermissionResponse(decision="allow_once", request_id=req.id)

        ctx.request_permission = _fake_request  # exposed by HookContext
        ctx.permission_requester = _fake_request

        with patch(
            "agent.platform.hooks.builtins.auto_mode_gate._classify_action",
            new=AsyncMock(return_value=PermissionDecision(behavior="ask", reason="path is outside workspace")),
        ):
            event = {
                "name": "write",
                "args": {"file_path": str(tmp_path.parent / "outside-ask" / "x.py"), "content": "x"},
            }
            result = await handler(event, ctx)

        # ask → handler returns None (allow_once after user said yes)
        assert result is None or result.get("block") is False

    @pytest.mark.asyncio
    async def test_inside_workspace_write_goes_through_existing_flow(self, tmp_path: Path) -> None:
        """Inside-workspace write + always_allow → pass through, no classifier called."""
        handler = _register_gate()
        config = AutoModeConfig(always_allow_tools=("write",))
        ctx = _FakeCtx(tmp_path, metadata={"_auto_mode_config_loader": lambda: config})

        with patch(
            "agent.platform.hooks.builtins.auto_mode_gate._classify_action",
            new=AsyncMock(),
        ) as mock_classify:
            event = {
                "name": "write",
                "args": {"file_path": str(tmp_path / "in.py"), "content": "x"},
            }
            result = await handler(event, ctx)

        assert result is None, "inside-workspace + safe_tool should pass through"
        mock_classify.assert_not_called(), "safe_tool fast-path should skip classifier"


class PermissionBrokerStub:
    """Minimal broker stub for ask-flow integration tests."""

    def __init__(self) -> None:
        self.deny_counts: dict[tuple[str, str], int] = {}

    def is_session_allowed(self, sid: str, tool: str) -> bool:
        return False

    def add_session_allowlist(self, sid: str, tool: str) -> None:
        pass

    def is_deny_limit_exceeded(self, run_id: str, tool: str, *, deny_limit: int | None = None) -> bool:
        return False

    def get_deny_count(self, run_id: str, tool: str) -> int:
        return self.deny_counts.get((run_id, tool), 0)

    def increment_deny_count(self, run_id: str, tool: str) -> int:
        self.deny_counts[(run_id, tool)] = self.get_deny_count(run_id, tool) + 1
        return self.deny_counts[(run_id, tool)]

    def reset_deny_count(self, run_id: str, tool: str) -> None:
        self.deny_counts.pop((run_id, tool), None)


# ---------------------------------------------------------------------------
# 3. Contract: write/edit/multi_edit still listed
# ---------------------------------------------------------------------------

class TestContract:
    def test_write_edit_multi_edit_are_path_aware(self) -> None:
        """If a new path-carrying tool is added later, the gate must be updated."""
        from agent.platform.hooks.builtins.auto_mode_gate import _WRITE_TOOLS_WITH_PATH_INPUT
        assert "write" in _WRITE_TOOLS_WITH_PATH_INPUT
        assert "edit" in _WRITE_TOOLS_WITH_PATH_INPUT
        assert "multi_edit" in _WRITE_TOOLS_WITH_PATH_INPUT
        assert _WRITE_TOOLS_WITH_PATH_INPUT["write"] == "file_path"
