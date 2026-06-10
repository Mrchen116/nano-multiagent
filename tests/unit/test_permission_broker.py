"""Tests for PermissionBroker — deny-count / session-allowlist / future resolution.

Covers:
- resolve a pending permission request
- deny-limit escalation to ask
- session-allowlist: allow_session marks tool as allowed for session
- unresolved futures resolved to deny on broker.cancel_all
- PermissionDecision / PermissionRequest / PermissionResponse / PermissionOption dataclasses
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.platform.permissions.broker import (
    PermissionBroker,
    PermissionDecision,
    PermissionOption,
    PermissionRequest,
    PermissionResponse,
)


class TestPermissionDecision:
    def test_allow_behavior(self):
        d = PermissionDecision(behavior="allow")
        assert d.behavior == "allow"
        assert d.reason == ""
        assert d.rule_source == ""

    def test_deny_behavior(self):
        d = PermissionDecision(
            behavior="deny", reason="too risky", rule_source="classifier"
        )
        assert d.behavior == "deny"
        assert d.reason == "too risky"

    def test_ask_behavior(self):
        d = PermissionDecision(behavior="ask", reason="uncertain")
        assert d.behavior == "ask"


class TestPermissionOption:
    def test_fields(self):
        opt = PermissionOption(
            id="allow_once", label="Allow once", description="Allow this time"
        )
        assert opt.id == "allow_once"
        assert opt.label == "Allow once"
        assert opt.description == "Allow this time"


class TestPermissionRequest:
    def test_fields(self):
        req = PermissionRequest(
            id="req-1",
            tool_name="bash",
            tool_input={"command": "rm -rf /tmp"},
            question="Allow bash?",
            options=(PermissionOption("allow_once", "Allow once", ""),),
        )
        assert req.id == "req-1"
        assert req.tool_name == "bash"
        assert len(req.options) == 1


class TestPermissionResponse:
    def test_fields(self):
        resp = PermissionResponse(decision="allow_once", request_id="req-1")
        assert resp.decision == "allow_once"
        assert resp.request_id == "req-1"


class TestPermissionBroker:
    def _make_broker(self, deny_limit: int = 3) -> PermissionBroker:
        from agent.platform.config.auto_mode import AutoModeConfig

        cfg = AutoModeConfig(deny_limit=deny_limit)
        broker = PermissionBroker(config=cfg)
        return broker

    def test_initial_deny_count_is_zero(self):
        broker = self._make_broker()
        assert broker.get_deny_count("run-1", "bash") == 0

    def test_increment_deny_count(self):
        broker = self._make_broker()
        broker.increment_deny_count("run-1", "bash")
        broker.increment_deny_count("run-1", "bash")
        assert broker.get_deny_count("run-1", "bash") == 2

    def test_deny_limit_exceeded(self):
        broker = self._make_broker(deny_limit=2)
        broker.increment_deny_count("run-1", "bash")
        broker.increment_deny_count("run-1", "bash")
        assert broker.is_deny_limit_exceeded("run-1", "bash") is True

    def test_deny_limit_not_exceeded(self):
        broker = self._make_broker(deny_limit=3)
        broker.increment_deny_count("run-1", "bash")
        assert broker.is_deny_limit_exceeded("run-1", "bash") is False

    def test_deny_limit_override_per_call(self):
        """The broker is per-app singleton but deny_limit is workspace-scoped.

        ``auto_mode_gate`` loads the active session's workspace config and
        passes its ``deny_limit`` per call. Without this override every IM
        session would silently inherit the broker's bootstrap default
        (``AutoModeConfig()`` = 3), making workspace ``deny_limit: 1``
        configs invisible to the hook.
        """
        broker = self._make_broker(deny_limit=3)  # bootstrap default
        broker.increment_deny_count("run-1", "bash")
        # Default broker limit not yet reached.
        assert broker.is_deny_limit_exceeded("run-1", "bash") is False
        # Workspace config override deny_limit=1 → 1 deny is enough to escalate.
        assert broker.is_deny_limit_exceeded("run-1", "bash", deny_limit=1) is True
        # Override deny_limit=5 → 1 deny still not enough.
        assert broker.is_deny_limit_exceeded("run-1", "bash", deny_limit=5) is False

    def test_reset_deny_count_on_allow(self):
        broker = self._make_broker(deny_limit=3)
        broker.increment_deny_count("run-1", "bash")
        broker.increment_deny_count("run-1", "bash")
        broker.reset_deny_count("run-1", "bash")
        assert broker.get_deny_count("run-1", "bash") == 0

    def test_session_allowlist_add_and_check(self):
        broker = self._make_broker()
        assert broker.is_session_allowed("sess-1", "bash") is False
        broker.add_session_allowlist("sess-1", "bash")
        assert broker.is_session_allowed("sess-1", "bash") is True

    def test_session_allowlist_does_not_cross_sessions(self):
        broker = self._make_broker()
        broker.add_session_allowlist("sess-1", "bash")
        assert broker.is_session_allowed("sess-2", "bash") is False

    @pytest.mark.asyncio
    async def test_register_and_resolve_future(self):
        broker = self._make_broker()
        loop = asyncio.get_event_loop()

        # Register a future for request id
        request_id = "req-123"
        future = broker.register_request(request_id)

        # Resolve from "outside"
        response = PermissionResponse(decision="allow_once", request_id=request_id)
        broker.resolve(request_id, response)

        # Future should now be done
        result = await asyncio.wait_for(future, timeout=1.0)
        assert result.decision == "allow_once"

    @pytest.mark.asyncio
    async def test_cancel_all_resolves_pending_as_deny(self):
        broker = self._make_broker()
        req_id = "req-pending"
        future = broker.register_request(req_id)

        broker.cancel_all_pending(run_id=None)

        result = await asyncio.wait_for(future, timeout=1.0)
        assert result.decision == "deny"
        assert "cancelled" in result.reason.lower() or "cancel" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_cancel_run_only_cancels_run_futures(self):
        broker = self._make_broker()

        # Register two futures with different run scopes
        future_run1 = broker.register_request("req-run1", run_id="run-1")
        future_run2 = broker.register_request("req-run2", run_id="run-2")

        broker.cancel_all_pending(run_id="run-1")

        # run-1 future should be cancelled to deny
        result1 = await asyncio.wait_for(future_run1, timeout=1.0)
        assert result1.decision == "deny"

        # run-2 future should still be pending (not done)
        assert not future_run2.done()

        # cleanup
        broker.cancel_all_pending(run_id="run-2")

    def test_resolve_unknown_request_id_is_noop(self):
        broker = self._make_broker()
        # Should not raise
        broker.resolve("nonexistent", PermissionResponse(decision="deny"))

    # ------------------------------------------------------------------
    # Finding 7: broker.resolve must return bool (TOCTOU fix)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_resolve_returns_true_when_found(self):
        """broker.resolve must return True when request_id was pending (finding 7)."""
        broker = self._make_broker()
        broker.register_request("req-bool")
        result = broker.resolve("req-bool", PermissionResponse(decision="allow_once"))
        assert result is True

    def test_resolve_returns_false_when_not_found(self):
        """broker.resolve must return False for unknown/already-resolved id (finding 7)."""
        broker = self._make_broker()
        result = broker.resolve("nonexistent", PermissionResponse(decision="deny"))
        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_idempotent_second_call_returns_false(self):
        """Second resolve call for same id must return False — no double set_result (finding 7)."""
        broker = self._make_broker()
        broker.register_request("req-dup")
        first = broker.resolve("req-dup", PermissionResponse(decision="allow_once"))
        second = broker.resolve("req-dup", PermissionResponse(decision="deny"))
        assert first is True
        assert second is False
