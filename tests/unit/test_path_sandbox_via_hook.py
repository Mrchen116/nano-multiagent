"""Tests for path sandbox via auto_mode_gate hook.

Covers the critical branches of the unified permission decision flow as updated
by bugfix-355 (M1):

1. workspace-internal path → existing flow (session allowlist / safe_tool / classifier)
2. workspace-external path + dangerously_skip_permissions → pass through (no bypass-immune)
3. workspace-external path + classifier returns allow → pass through
4. workspace-external path + classifier returns ask → handed to broker

Notes on changes from refactor-353 baseline:
- _detect_outside_workspace_path helper was removed; out-of-workspace write routing
  now handled via tool.check_permissions (bugfix-355 M1, Anchor F).
- _WRITE_TOOLS_WITH_PATH_INPUT constant was removed along with the helper.
- The OUTSIDE NOTE prepended to the classifier user_prompt was removed (W2).
- The gate now accepts a tool_result from tool.check_permissions before dispatching.

These tests use the gate's public ``setup()`` to register the handler and
exercise it end-to-end via a faked HookContext.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
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
# 1. End-to-end gate branches
# ---------------------------------------------------------------------------

class TestGatePathSandboxBranches:
    @pytest.mark.asyncio
    async def test_dangerously_mode_bypasses_outside_workspace_write(self, tmp_path: Path) -> None:
        """Workspace-external write + dangerously → pass through (no classifier, no ask).

        Spec contract: dangerously-skip-permissions语义是不进行任何权限管控。
        Non-safety-locked tools bypass completely even outside workspace.
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

        Classifier receives the standard prompt (no OUTSIDE NOTE prepended — W2
        from bugfix-355 M1 removed the workspace hint injection).
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
        # Classifier was called; verify the OUTSIDE NOTE is NOT injected (W2 change).
        assert mock_classify.called, "classifier should have been called for unlisted write tool"
        call_args = mock_classify.call_args
        user_prompt = call_args.args[2]  # (ctx, system_prompt, user_prompt)
        assert "OUTSIDE the agent's workspace" not in user_prompt, (
            "W2: OUTSIDE NOTE must not be prepended — path context now comes from tool.check_permissions"
        )

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
# 2. Contract: deleted symbols are gone, new architecture is in place
# ---------------------------------------------------------------------------

class TestContract:
    def test_detect_outside_workspace_path_is_deleted(self) -> None:
        """_detect_outside_workspace_path must not exist — it was removed in bugfix-355 M1 (Anchor F).

        Out-of-workspace write routing is now handled via tool.check_permissions.
        This test is a canary: if someone accidentally re-adds the helper, this will fail.
        """
        import agent.platform.hooks.builtins.auto_mode_gate as gate_module
        assert not hasattr(gate_module, "_detect_outside_workspace_path"), (
            "Anchor F: _detect_outside_workspace_path must be deleted — "
            "path routing now via tool.check_permissions"
        )

    def test_write_tools_with_path_input_is_deleted(self) -> None:
        """_WRITE_TOOLS_WITH_PATH_INPUT constant must not exist — removed with _detect_outside_workspace_path."""
        import agent.platform.hooks.builtins.auto_mode_gate as gate_module
        assert not hasattr(gate_module, "_WRITE_TOOLS_WITH_PATH_INPUT"), (
            "_WRITE_TOOLS_WITH_PATH_INPUT was part of the old path-detection approach and must be deleted"
        )
