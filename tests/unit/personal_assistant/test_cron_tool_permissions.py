"""Tests for feat-394-M5 R1: cron tool check_permissions gates auto_mode_gate.

R3-1 fix: CronTool must implement check_permissions returning allow so that
auto_mode_gate bypasses the classifier for cron tool calls.
Without this, auto_mode_gate falls through to the classifier which denies
cron tool calls as "Unauthorized Persistence" (modifying cron jobs/schedules).

Design: cron tool is only injected into the agent's tool table when cron_enabled=True
(enforced by toolsets.py gate), which constitutes the user's authorization.
check_permissions therefore unconditionally allows the call — the gate for
"is this agent allowed to use cron" is at tool registration time, not at call time.

See acceptance.md Round 3 Issue R3-1.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


class TestCronToolCheckPermissions:
    """CronTool.check_permissions must return allow to bypass auto_mode_gate classifier."""

    def _get_cron_tool(self):
        from agent.products.personal_assistant.tools.cron import CronTool
        return CronTool()

    def test_cron_tool_has_check_permissions(self) -> None:
        """CronTool must implement check_permissions (not just passthrough via None)."""
        tool = self._get_cron_tool()
        assert hasattr(tool, "check_permissions"), (
            "CronTool must implement check_permissions so auto_mode_gate "
            "bypasses the classifier for cron tool calls (R3-1 fix)"
        )
        assert callable(getattr(tool, "check_permissions")), (
            "check_permissions must be callable"
        )

    def test_check_permissions_returns_allow_for_any_input(self) -> None:
        """check_permissions must return allow for any cron tool call.

        Authorization is at tool registration time (cron_enabled=True gate in toolsets.py).
        At call time, any registered cron invocation is pre-authorized.
        """
        tool = self._get_cron_tool()
        ctx = MagicMock()
        ctx.session_metadata = {}

        for action in ("list", "add", "update", "remove", "run", "runs"):
            result = tool.check_permissions({"action": action}, ctx)
            assert result is not None, f"check_permissions returned None for action={action}"
            behavior = getattr(result, "behavior", None)
            assert behavior == "allow", (
                f"check_permissions must return allow for action={action}, got {behavior!r}. "
                "The cron tool must not fall through to the classifier which would "
                "deny the call as 'Unauthorized Persistence'."
            )

    def test_check_permissions_allows_empty_input(self) -> None:
        """check_permissions must handle any input shape (including empty dict)."""
        tool = self._get_cron_tool()
        ctx = MagicMock()
        ctx.session_metadata = {}

        result = tool.check_permissions({}, ctx)
        behavior = getattr(result, "behavior", None)
        assert behavior == "allow"

    def test_check_permissions_result_has_behavior_attribute(self) -> None:
        """auto_mode_gate reads result.behavior — must be present."""
        tool = self._get_cron_tool()
        ctx = MagicMock()
        ctx.session_metadata = {}

        result = tool.check_permissions({"action": "list"}, ctx)
        assert hasattr(result, "behavior"), (
            "check_permissions result must have 'behavior' attribute "
            "for auto_mode_gate to dispatch (Step 5 in auto_mode_gate.on_tool_call)"
        )

    def test_check_permissions_allow_does_not_require_platform_import(self) -> None:
        """check_permissions must work without importing platform.permissions.broker.

        CronTool is in agent.products layer — must not import platform layer.
        A simple allow object (behavior='allow') is sufficient since auto_mode_gate
        only needs getattr(result, 'behavior', 'passthrough').
        """
        import importlib
        import sys

        # Verify the cron module does not import platform.permissions.broker at load time
        cron_module = importlib.import_module("agent.products.personal_assistant.tools.cron")
        module_source = open(cron_module.__file__).read()
        # Should not directly import from platform layer (would violate dep direction)
        assert "from agent.platform" not in module_source, (
            "cron.py must not import from agent.platform layer "
            "(AGENTS.md dependency direction rule)"
        )
        assert "from agent.core.agent.hooks" not in module_source, (
            "cron.py must not import from agent.core.agent.hooks "
            "(AGENTS.md dependency direction rule)"
        )
