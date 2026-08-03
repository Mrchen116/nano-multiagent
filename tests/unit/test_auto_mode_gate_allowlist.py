"""Tests for the auto-mode safe-tool boundary and hook registration."""

from __future__ import annotations

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
    def test_safe_allowlist_matches_current_policy(self):
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

    def test_always_allow_tools_config_extension(self):
        cfg = AutoModeConfig(always_allow_tools=("my_custom_tool",))
        assert is_safe_tool("my_custom_tool", cfg) is True


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
