"""Tests for auto_mode_gate permission dispatch.

Verifies:
- tool.check_permissions decisions are honored before classifier fallback
- safety_locked = True when check_permissions returns ask+safety_check
- dangerously mode + safety_locked → still asks (bypass-immune)
- dangerously mode + !safety_locked → passes through (true bypass)
- check_permissions allow → directly allowed without classifier
- check_permissions deny → directly denied without classifier
- check_permissions passthrough → falls through to bash/classifier
- unknown non-safe tool or missing projection → ask/fail-closed
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    setup as gate_setup,
)
from agent.platform.permissions.broker import PermissionBroker, PermissionDecision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_with_check_permissions(
    behavior: str, decision_reason: dict | None = None
):
    """Build a mock tool that implements check_permissions returning given behavior."""
    tool = MagicMock()
    tool.check_permissions = MagicMock(
        return_value=PermissionDecision(
            behavior=behavior, decision_reason=decision_reason
        )
    )
    tool.to_auto_classifier_input = MagicMock(return_value="mock projection")
    return tool


def _make_tool_without_check_permissions():
    """Build a mock tool that does NOT have check_permissions (pure passthrough)."""
    tool = MagicMock(spec=["name", "run", "serialize_result"])
    tool.name = "no_perm_tool"
    # explicitly ensure no check_permissions
    assert not hasattr(tool, "check_permissions")
    return tool


def _get_handler(config: AutoModeConfig | None = None):
    """Extract the on_tool_call handler via gate_setup."""
    if config is None:
        config = AutoModeConfig()
    handlers = []

    class MockHooks:
        def on(self, event, handler, **kwargs):
            handlers.append(handler)

        def get_state(self, key):
            return None

    gate_setup(MockHooks())
    return handlers[0], config


def _make_ctx(
    *,
    config: AutoModeConfig,
    tool_instance=None,
    run_origin: str = "user",
    session_id: str = "sess-1",
    call_model_result=None,
    broker: PermissionBroker | None = None,
):
    """Build a mock HookContext with tool_registry and config injected."""
    ctx = MagicMock()
    ctx.session_id = session_id
    ctx.repo_root = None

    # Build metadata
    meta: dict = {
        "run_origin": run_origin,
        "_auto_mode_config_loader": lambda: config,
    }
    if broker is not None:
        meta["permission_broker"] = broker

    # Inject tool_registry if tool_instance provided
    if tool_instance is not None:
        registry = MagicMock()
        registry.get = MagicMock(return_value=tool_instance)
        meta["tool_registry"] = registry

    ctx.metadata = meta

    if call_model_result is not None:

        async def _call_model(**kwargs):
            return call_model_result

        ctx.call_model = _call_model
    else:
        ctx.call_model = AsyncMock(return_value=MagicMock(content="<block>no</block>"))

    ctx.message_history = ()
    return ctx


# ---------------------------------------------------------------------------
# tool.check_permissions dispatch
# ---------------------------------------------------------------------------


class TestCheckPermissionsDispatch:
    @pytest.mark.asyncio
    async def test_check_permissions_allow_bypasses_classifier(self):
        """check_permissions returning allow must bypass classifier entirely."""
        tool = _make_tool_with_check_permissions("allow")
        config = AutoModeConfig()
        handler, _ = _get_handler(config)

        ctx = _make_ctx(config=config, tool_instance=tool)
        ctx.call_model = AsyncMock()  # must NOT be called

        result = await handler(
            {"name": "web_fetch", "args": {"url": "https://preapproved.example.com"}},
            ctx,
        )
        assert result is None or result.get("block") is not True
        ctx.call_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_permissions_deny_blocks_without_classifier(self):
        """check_permissions returning deny must block without classifier call."""
        tool = _make_tool_with_check_permissions("deny")
        config = AutoModeConfig()
        handler, _ = _get_handler(config)

        ctx = _make_ctx(config=config, tool_instance=tool)
        ctx.call_model = AsyncMock()  # must NOT be called

        result = await handler(
            {"name": "web_fetch", "args": {"url": "https://denied.example.com"}},
            ctx,
        )
        assert result is not None
        assert result.get("block") is True
        ctx.call_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_permissions_passthrough_falls_to_classifier(self):
        """check_permissions returning passthrough falls through to classifier."""
        tool = _make_tool_with_check_permissions("passthrough")
        config = AutoModeConfig()

        model_result = MagicMock()
        model_result.content = "<block>no</block>"

        handler, _ = _get_handler(config)
        ctx = _make_ctx(
            config=config, tool_instance=tool, call_model_result=model_result
        )

        result = await handler(
            {"name": "web_fetch", "args": {"url": "https://unknown.example.com"}},
            ctx,
        )
        # Classifier was called (passthrough → classifier → allow)
        assert result is None or result.get("block") is not True

    @pytest.mark.asyncio
    async def test_no_tool_registry_fails_closed_without_classifier(self):
        """Unknown non-safe tools must fail closed instead of classifying empty action."""
        config = AutoModeConfig()
        model_result = MagicMock()
        model_result.content = "<block>no</block>"

        handler, _ = _get_handler(config)
        # No tool_instance → no tool_registry in metadata
        ctx = _make_ctx(
            config=config, tool_instance=None, call_model_result=model_result
        )

        result = await handler(
            {"name": "web_fetch", "args": {"url": "https://example.com"}},
            ctx,
        )
        assert result is not None
        assert result.get("block") is True
        assert "projection" in result.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_missing_projection_fails_closed_without_classifier(self):
        """A registered non-safe tool without projection must not reach classifier."""
        tool = _make_tool_without_check_permissions()
        config = AutoModeConfig()
        handler, _ = _get_handler(config)
        ctx = _make_ctx(config=config, tool_instance=tool)
        ctx.call_model = AsyncMock()

        result = await handler({"name": "no_perm_tool", "args": {"x": 1}}, ctx)

        assert result is not None
        assert result.get("block") is True
        assert "projection" in result.get("reason", "").lower()
        ctx.call_model.assert_not_called()


# ---------------------------------------------------------------------------
# safety_locked bypass-immune behavior (W1)
# ---------------------------------------------------------------------------


class TestSafetyLockedBypassImmune:
    @pytest.mark.asyncio
    async def test_safety_check_ask_is_bypass_immune_in_dangerously_mode(self):
        """dangerously mode + safety_check ask → must still ask user (bypass-immune)."""
        tool = _make_tool_with_check_permissions(
            "ask",
            decision_reason={"type": "safety_check", "matched_path": "~/.bashrc"},
        )
        config = AutoModeConfig(dangerously_skip_permissions=True)
        handler, _ = _get_handler(config)

        deny_response = MagicMock()
        deny_response.decision = "deny"

        async def mock_requester(req):
            return deny_response

        ctx = _make_ctx(config=config, tool_instance=tool)
        ctx.request_permission = mock_requester

        result = await handler(
            {"name": "write", "args": {"file_path": "~/.bashrc", "content": "evil"}},
            ctx,
        )
        # Should be blocked (user denied the ask, even in dangerously mode)
        assert result is not None
        assert result.get("block") is True

    @pytest.mark.asyncio
    async def test_non_safety_check_ask_in_dangerously_mode_bypasses(self):
        """dangerously mode + non-safety-check ask → true bypass (no card)."""
        config = AutoModeConfig(dangerously_skip_permissions=True)
        handler, _ = _get_handler(config)

        # No tool_instance → getattr returns None → passthrough (no safety_locked)
        ctx = _make_ctx(config=config, tool_instance=None)

        result = await handler(
            {"name": "bash", "args": {"command": "rm -rf /tmp/test"}},
            ctx,
        )
        # dangerously + no safety_locked → bypass
        assert result is None or result.get("block") is not True
