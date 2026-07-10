"""Tests for auto_mode_gate: safe tool allowlist, tool input projection, gate hook setup."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    SAFE_TOOL_ALLOWLIST,
    is_safe_tool,
    setup as gate_setup,
)


# ---------------------------------------------------------------------------
# Safe-tool allowlist
# ---------------------------------------------------------------------------


class TestSafeToolAllowlist:
    def test_safe_allowlist_matches_bugfix_456_policy(self):
        assert SAFE_TOOL_ALLOWLIST == frozenset(
            {
                "read",
                "web_search",
                "skill_view",
                "task_stop",
                "agent",
                "send_message",
                "memory",
            }
        )

    def test_read_is_safe(self):
        assert is_safe_tool("read", AutoModeConfig()) is True

    def test_web_fetch_not_safe(self):
        assert is_safe_tool("web_fetch", AutoModeConfig()) is False

    def test_web_search_is_safe(self):
        assert is_safe_tool("web_search", AutoModeConfig()) is True

    def test_skill_view_is_safe(self):
        assert is_safe_tool("skill_view", AutoModeConfig()) is True

    def test_task_stop_is_safe(self):
        assert is_safe_tool("task_stop", AutoModeConfig()) is True

    def test_other_task_tools_not_preapproved(self):
        for tool in (
            "task_create",
            "task_get",
            "task_update",
            "task_list",
            "task_output",
        ):
            assert is_safe_tool(tool, AutoModeConfig()) is False

    def test_agent_tool_safe(self):
        assert is_safe_tool("agent", AutoModeConfig()) is True

    def test_send_message_safe(self):
        assert is_safe_tool("send_message", AutoModeConfig()) is True

    def test_memory_safe(self):
        # bugfix-368: memory tool must fast-path allow in auto mode.
        # Without this entry, PA self-improvement loops on `tool blocked by hook`
        # because the classifier judges memory (a write/persistence tool) as deny.
        assert is_safe_tool("memory", AutoModeConfig()) is True

    def test_bash_not_safe(self):
        assert is_safe_tool("bash", AutoModeConfig()) is False

    def test_write_not_safe(self):
        assert is_safe_tool("write", AutoModeConfig()) is False

    def test_edit_not_safe(self):
        assert is_safe_tool("edit", AutoModeConfig()) is False

    def test_skill_manage_not_safe(self):
        assert is_safe_tool("skill_manage", AutoModeConfig()) is False

    def test_cron_not_safe(self):
        assert is_safe_tool("cron", AutoModeConfig()) is False

    def test_always_allow_tools_config_extension(self):
        cfg = AutoModeConfig(always_allow_tools=("my_custom_tool",))
        assert is_safe_tool("my_custom_tool", cfg) is True

    def test_safe_tool_allowlist_frozenset(self):
        assert isinstance(SAFE_TOOL_ALLOWLIST, frozenset)


# ---------------------------------------------------------------------------
# Gate hook setup — registration uses timeout_ms=None
# ---------------------------------------------------------------------------


class TestGateSetup:
    def test_setup_registers_with_none_timeout(self):
        """auto_mode_gate must register with timeout_ms=None (self-managed)."""
        registrations = []

        class MockHooks:
            def on(self, event, handler, *, priority=100, timeout_ms=1500, **kwargs):
                registrations.append(
                    {
                        "event": event,
                        "priority": priority,
                        "timeout_ms": timeout_ms,
                    }
                )

        gate_setup(MockHooks())
        assert len(registrations) == 1
        assert registrations[0]["event"] == "tool_call"
        assert registrations[0]["timeout_ms"] is None
