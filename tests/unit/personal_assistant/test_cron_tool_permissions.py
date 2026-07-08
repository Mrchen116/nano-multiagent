"""Tests for cron tool action-level check_permissions gates auto_mode_gate.

bugfix-456 tightens cron from unconditional allow to action-level fast path:
list/runs are local read-only queries, while add/update/remove/run change
long-lived automation state or trigger execution and must fall through to the
classifier with a current action projection.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


class TestCronToolCheckPermissions:
    """CronTool.check_permissions must allow only read-only query actions."""

    def _get_cron_tool(self):
        from personal_assistant.tools.cron import make_cron_tool

        return make_cron_tool({})

    def test_cron_tool_has_check_permissions(self) -> None:
        """CronTool must implement check_permissions (not just passthrough via None)."""
        tool = self._get_cron_tool()
        assert hasattr(tool, "check_permissions"), (
            "CronTool must implement check_permissions so auto_mode_gate "
            "can fast-path low-risk queries and classify mutating actions"
        )
        assert callable(getattr(tool, "check_permissions")), (
            "check_permissions must be callable"
        )

    def test_check_permissions_allows_list_and_runs(self) -> None:
        tool = self._get_cron_tool()
        ctx = MagicMock()
        ctx.session_metadata = {}

        for action in ("list", "runs"):
            result = tool.check_permissions({"action": action}, ctx)
            behavior = getattr(result, "behavior", None)
            assert behavior == "allow"

    def test_check_permissions_passthrough_for_mutating_actions(self) -> None:
        tool = self._get_cron_tool()
        ctx = MagicMock()
        ctx.session_metadata = {}

        for action in ("add", "update", "remove", "run"):
            result = tool.check_permissions({"action": action}, ctx)
            assert getattr(result, "behavior", None) == "passthrough"

    def test_cron_projects_mutating_actions(self) -> None:
        tool = self._get_cron_tool()
        projection = tool.to_auto_classifier_input(
            {
                "action": "add",
                "job": {
                    "name": "daily summary",
                    "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                    "payload": {"kind": "agentTurn", "message": "summarize"},
                },
            }
        )
        assert "action=add" in projection
        assert "daily summary" in projection

    def test_check_permissions_allows_empty_input(self) -> None:
        """Empty input is not a query action, so it falls through to classifier."""
        tool = self._get_cron_tool()
        ctx = MagicMock()
        ctx.session_metadata = {}

        result = tool.check_permissions({}, ctx)
        behavior = getattr(result, "behavior", None)
        assert behavior == "passthrough"

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
        cron_module = importlib.import_module("personal_assistant.tools.cron")
        module_source = open(cron_module.__file__).read()
        # Should not directly import from platform layer (would violate dep direction).
        # refactor-406-M1: personal_assistant may only import agent.sdk, never
        # agent.platform / agent.core internals.
        assert "from agent.platform" not in module_source, (
            "cron.py must not import from agent.platform layer "
            "(AGENTS.md dependency direction rule)"
        )
        assert "from agent.core.agent.hooks" not in module_source, (
            "cron.py must not import from agent.core.agent.hooks "
            "(AGENTS.md dependency direction rule)"
        )
