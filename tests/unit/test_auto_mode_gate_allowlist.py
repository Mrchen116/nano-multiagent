"""Tests for auto_mode_gate: safe tool allowlist, tool input projection, gate hook setup."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    SAFE_TOOL_ALLOWLIST,
    is_safe_tool,
    project_tool_input,
    setup as gate_setup,
)


# ---------------------------------------------------------------------------
# Safe-tool allowlist
# ---------------------------------------------------------------------------

class TestSafeToolAllowlist:
    def test_read_is_safe(self):
        assert is_safe_tool("read", AutoModeConfig()) is True

    def test_web_fetch_not_safe(self):
        # S1 (bugfix-355 M1): web_fetch removed from SAFE_TOOL_ALLOWLIST;
        # routing now via WebFetch.check_permissions (M3).
        assert is_safe_tool("web_fetch", AutoModeConfig()) is False

    def test_web_search_not_safe(self):
        # S2 (bugfix-355 M1): web_search removed from SAFE_TOOL_ALLOWLIST;
        # falls to classifier (passthrough behavior).
        assert is_safe_tool("web_search", AutoModeConfig()) is False

    def test_task_tools_safe(self):
        for tool in ("task_create", "task_get", "task_update", "task_list", "task_stop", "task_output"):
            assert is_safe_tool(tool, AutoModeConfig()) is True

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

    def test_always_allow_tools_config_extension(self):
        cfg = AutoModeConfig(always_allow_tools=("my_custom_tool",))
        assert is_safe_tool("my_custom_tool", cfg) is True

    def test_safe_tool_allowlist_frozenset(self):
        assert isinstance(SAFE_TOOL_ALLOWLIST, frozenset)


# ---------------------------------------------------------------------------
# Tool input projection
# ---------------------------------------------------------------------------

class TestProjectToolInput:
    def test_bash_projects_command(self):
        result = project_tool_input("bash", {"command": "ls -la"})
        assert result == "ls -la"

    def test_read_projects_file_path(self):
        result = project_tool_input("read", {"file_path": "/home/user/main.py"})
        assert result == "/home/user/main.py"

    def test_write_projects_path_and_content_truncated(self):
        long_content = "x" * 500
        result = project_tool_input("write", {"file_path": "/tmp/f.py", "content": long_content})
        assert "/tmp/f.py" in result
        # Content truncated at 200 chars
        assert len(result) < len(long_content) + 50

    def test_edit_projects_path_and_new_string_truncated(self):
        long_content = "y" * 500
        result = project_tool_input("edit", {"file_path": "/tmp/f.py", "new_string": long_content})
        assert "/tmp/f.py" in result

    def test_unknown_tool_returns_empty(self):
        result = project_tool_input("unknown_tool", {"key": "value"})
        assert result == ""

    def test_bash_missing_command_returns_empty(self):
        result = project_tool_input("bash", {})
        assert result == ""


# ---------------------------------------------------------------------------
# Gate hook setup — registration uses timeout_ms=None
# ---------------------------------------------------------------------------

class TestGateSetup:
    def test_setup_registers_with_none_timeout(self):
        """auto_mode_gate must register with timeout_ms=None (self-managed)."""
        registrations = []

        class MockHooks:
            def on(self, event, handler, *, priority=100, timeout_ms=1500, **kwargs):
                registrations.append({
                    "event": event,
                    "priority": priority,
                    "timeout_ms": timeout_ms,
                })

        gate_setup(MockHooks())
        assert len(registrations) == 1
        assert registrations[0]["event"] == "tool_call"
        assert registrations[0]["timeout_ms"] is None
