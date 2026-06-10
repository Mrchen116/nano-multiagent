"""Regression tests for feat-394-M14 Issue A: permission decision loop repair.

Root cause: broker.resolve was never called when the user clicked Allow/Deny in IM.

Chain of failures:
1. runtime._build_hook_context builds _permission_requester that registers a broker
   future and awaits it — this is correct.
2. SDK Kernel.__init__ assigns _make_permission_requester() to runtime._permission_requester
   (an attribute runtime never reads) — dead code.
3. gateway permission_response_handler=None — IM card clicks silently dropped.
4. No Kernel.submit_permission_decision() method existed — no way to resolve from outside.

Fix: Kernel gains submit_permission_decision(); gateway wires a real handler that calls it;
SDK stops writing the dead runtime attribute.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Kernel.submit_permission_decision — new public API
# ---------------------------------------------------------------------------


class TestKernelSubmitPermissionDecision:
    """Kernel must expose submit_permission_decision to resolve broker futures."""

    def _build_kernel_with_pending(self):
        """Build a minimal Kernel with one pending permission future."""
        from agent.platform.config.auto_mode import AutoModeConfig
        from agent.platform.permissions.broker import (
            PermissionBroker,
            PermissionResponse,
        )
        from agent.sdk.kernel import Kernel, _KernelComponents

        broker = PermissionBroker(config=AutoModeConfig())
        future = broker.register_request("req-1", run_id="run-1")

        # Build a minimal Kernel without starting a real runtime.
        components = MagicMock(spec=_KernelComponents)
        components.permission_broker = broker

        kernel = Kernel.__new__(Kernel)
        kernel._c = components
        kernel._can_use_tool = None
        return kernel, future

    @pytest.mark.asyncio
    async def test_submit_permission_decision_resolves_broker_future(self):
        """submit_permission_decision must resolve a pending broker future."""
        kernel, future = self._build_kernel_with_pending()

        result = kernel.submit_permission_decision(
            request_id="req-1",
            decision="allow_once",
        )

        assert result is True, (
            "submit_permission_decision must return True for known request_id"
        )
        # broker.resolve uses call_soon_threadsafe; give the loop one iteration to process.
        await asyncio.sleep(0)
        assert future.done(), "broker future must be resolved after submit"
        response = future.result()
        assert response.decision == "allow_once"

    @pytest.mark.asyncio
    async def test_submit_permission_decision_deny(self):
        """submit_permission_decision must work for deny decision."""
        kernel, future = self._build_kernel_with_pending()

        result = kernel.submit_permission_decision(
            request_id="req-1",
            decision="deny",
            reason="user denied",
        )

        assert result is True
        await asyncio.sleep(0)
        assert future.done()
        response = future.result()
        assert response.decision == "deny"
        assert response.reason == "user denied"

    @pytest.mark.asyncio
    async def test_submit_permission_decision_unknown_request_returns_false(self):
        """submit_permission_decision must return False for unknown request_id."""
        kernel, _ = self._build_kernel_with_pending()

        result = kernel.submit_permission_decision(
            request_id="unknown-req",
            decision="allow_once",
        )

        assert result is False, (
            "submit_permission_decision must return False for unknown id"
        )

    @pytest.mark.asyncio
    async def test_submit_permission_decision_allow_session(self):
        """submit_permission_decision must accept all valid decision values."""
        kernel, future = self._build_kernel_with_pending()

        result = kernel.submit_permission_decision(
            request_id="req-1",
            decision="allow_session",
        )

        assert result is True
        await asyncio.sleep(0)
        assert future.done()
        assert future.result().decision == "allow_session"


# ---------------------------------------------------------------------------
# _build_permission_response_handler wires to kernel.submit_permission_decision
# ---------------------------------------------------------------------------


class TestPermissionResponseHandlerUsesKernel:
    """_build_permission_response_handler must call kernel.submit_permission_decision."""

    def test_handler_calls_submit_on_kernel(self):
        """Handler must route IM permission_response frame to kernel.submit_permission_decision."""
        from personal_assistant.main import _build_permission_response_handler

        kernel_mock = MagicMock()
        kernel_mock.submit_permission_decision.return_value = True

        handler = _build_permission_response_handler(kernel=kernel_mock)

        # Simulate IM sending a permission_response frame.
        handler({"request_id": "req-abc", "decision": "allow_once"})

        kernel_mock.submit_permission_decision.assert_called_once_with(
            request_id="req-abc",
            decision="allow_once",
            reason="",
        )

    def test_handler_no_crash_on_missing_fields(self):
        """Handler must be a no-op when required fields are missing (defensive)."""
        from personal_assistant.main import _build_permission_response_handler

        kernel_mock = MagicMock()
        handler = _build_permission_response_handler(kernel=kernel_mock)

        # Missing request_id → no-op.
        handler({"decision": "allow_once"})
        kernel_mock.submit_permission_decision.assert_not_called()

        # Missing decision → no-op.
        handler({"request_id": "req-1"})
        kernel_mock.submit_permission_decision.assert_not_called()

    def test_handler_passes_reason(self):
        """Handler must forward the reason field when present."""
        from personal_assistant.main import _build_permission_response_handler

        kernel_mock = MagicMock()
        kernel_mock.submit_permission_decision.return_value = True
        handler = _build_permission_response_handler(kernel=kernel_mock)

        handler({"request_id": "req-1", "decision": "deny", "reason": "sensitive"})

        kernel_mock.submit_permission_decision.assert_called_once_with(
            request_id="req-1",
            decision="deny",
            reason="sensitive",
        )


# ---------------------------------------------------------------------------
# Finding 4: submit_permission_decision must validate decision whitelist
# ---------------------------------------------------------------------------


class TestSubmitPermissionDecisionValidation:
    """SDK boundary must reject illegal decision strings (finding 4)."""

    def _make_kernel_with_pending(self):
        from agent.platform.config.auto_mode import AutoModeConfig
        from agent.platform.permissions.broker import PermissionBroker
        from agent.sdk.kernel import Kernel, _KernelComponents

        broker = PermissionBroker(config=AutoModeConfig())
        broker.register_request("req-v", run_id="run-v")

        components = MagicMock(spec=_KernelComponents)
        components.permission_broker = broker

        kernel = Kernel.__new__(Kernel)
        kernel._c = components
        kernel._can_use_tool = None
        return kernel

    @pytest.mark.asyncio
    async def test_valid_allow_once_accepted(self):
        kernel = self._make_kernel_with_pending()
        result = kernel.submit_permission_decision(
            request_id="req-v", decision="allow_once"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_valid_deny_accepted(self):
        kernel = self._make_kernel_with_pending()
        result = kernel.submit_permission_decision(request_id="req-v", decision="deny")
        assert result is True

    @pytest.mark.asyncio
    async def test_valid_allow_session_accepted(self):
        kernel = self._make_kernel_with_pending()
        result = kernel.submit_permission_decision(
            request_id="req-v", decision="allow_session"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_valid_allow_always_accepted(self):
        kernel = self._make_kernel_with_pending()
        result = kernel.submit_permission_decision(
            request_id="req-v", decision="allow_always"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_decision_returns_false(self):
        """Invalid decision string must return False without resolving broker (finding 4)."""
        kernel = self._make_kernel_with_pending()
        result = kernel.submit_permission_decision(
            request_id="req-v", decision="Allow_Once"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_garbage_decision_returns_false(self):
        """Garbage decision string must return False (finding 4)."""
        kernel = self._make_kernel_with_pending()
        result = kernel.submit_permission_decision(
            request_id="req-v", decision="yes_please"
        )
        assert result is False


# ---------------------------------------------------------------------------
# Finding 7: submit_permission_decision uses broker.resolve return value (TOCTOU)
# ---------------------------------------------------------------------------


class TestSubmitPermissionDecisionTOCTOU:
    """submit_permission_decision must use broker.resolve bool, not is_pending pre-check (finding 7)."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_idempotent(self):
        """Concurrent submit calls for same request_id: exactly one returns True (finding 7)."""
        import asyncio as _asyncio

        from agent.platform.config.auto_mode import AutoModeConfig
        from agent.platform.permissions.broker import PermissionBroker
        from agent.sdk.kernel import Kernel, _KernelComponents

        broker = PermissionBroker(config=AutoModeConfig())
        broker.register_request("req-concurrent")

        components = MagicMock(spec=_KernelComponents)
        components.permission_broker = broker

        kernel = Kernel.__new__(Kernel)
        kernel._c = components
        kernel._can_use_tool = None

        # Run two concurrent resolves for same id
        results = await _asyncio.gather(
            _asyncio.to_thread(
                kernel.submit_permission_decision,
                request_id="req-concurrent",
                decision="allow_once",
            ),
            _asyncio.to_thread(
                kernel.submit_permission_decision,
                request_id="req-concurrent",
                decision="deny",
            ),
        )
        # Exactly one must succeed (True), one must fail (False)
        assert sorted(results) == [False, True]
