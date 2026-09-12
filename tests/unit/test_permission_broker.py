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

    def test_allow_resets_consecutive_but_keeps_total(self):
        broker = self._make_broker()
        assert broker.get_auto_denial_counts("main") == (0, 0)
        assert broker.record_auto_decision("main", False) == (1, 1)
        assert broker.record_auto_decision("main", False) == (2, 2)
        assert broker.record_auto_decision("main", True) == (0, 2)
        assert broker.record_auto_decision("main", False) == (1, 3)

    def test_children_do_not_share_parent_or_sibling_counts(self):
        broker = self._make_broker()
        broker.record_auto_decision("main", False)
        broker.record_auto_decision("child-a", False)
        broker.record_auto_decision("child-a", False)
        assert broker.get_auto_denial_counts("main") == (1, 1)
        assert broker.get_auto_denial_counts("child-a") == (2, 2)
        assert broker.get_auto_denial_counts("child-b") == (0, 0)

    def test_total_limit_handles_one_action_then_resets(self):
        broker = self._make_broker()
        for _ in range(19):
            broker.record_auto_decision("main", False)
            broker.record_auto_decision("main", True)
        assert broker.record_auto_decision("main", False) == (1, 20)
        assert broker.get_auto_denial_counts("main") == (0, 0)
        assert broker.record_auto_decision("main", False, total_deny_limit=1) == (1, 1)
        assert broker.get_auto_denial_counts("main") == (0, 0)

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
