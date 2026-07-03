"""Tests for PA's IM permission_response handler (feat-394-M14 repair).

Covers the IM→PA→kernel decision return path: when IM forwards a user's
Allow/Deny choice over the gateway WS, the handler resolves the pending
request via Kernel.submit_permission_decision.

request_id is globally unique (auto_mode_gate assigns it), so no session
lookup via run_context_store is required — the broker finds the future by id.
"""

from __future__ import annotations

from typing import Any

from personal_assistant.main import _build_permission_response_handler


class _FakeKernel:
    def __init__(self, *, result: bool = True) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result

    def submit_permission_decision(
        self,
        *,
        request_id: str,
        decision: str,
        reason: str = "",
    ) -> bool:
        self.calls.append(
            {"request_id": request_id, "decision": decision, "reason": reason}
        )
        return self.result


def test_handler_routes_to_kernel_submit_permission_decision() -> None:
    """Handler must call kernel.submit_permission_decision with request_id and decision."""
    kernel = _FakeKernel()
    handler = _build_permission_response_handler(kernel=kernel)

    accepted = handler({"request_id": "req-abc", "decision": "allow_once"})

    assert accepted is True
    assert kernel.calls == [
        {"request_id": "req-abc", "decision": "allow_once", "reason": ""}
    ]


def test_handler_passes_reason_field() -> None:
    """Handler must forward the optional reason field."""
    kernel = _FakeKernel()
    handler = _build_permission_response_handler(kernel=kernel)

    accepted = handler(
        {"request_id": "req-1", "decision": "deny", "reason": "user said no"}
    )

    assert accepted is True
    assert kernel.calls == [
        {"request_id": "req-1", "decision": "deny", "reason": "user said no"}
    ]


def test_handler_ignores_malformed_frames() -> None:
    """Handler must be a no-op when required fields are missing."""
    kernel = _FakeKernel()
    handler = _build_permission_response_handler(kernel=kernel)

    # Missing request_id
    assert handler({"decision": "allow_once"}) is False
    # Missing decision
    assert handler({"request_id": "r-1"}) is False
    # Empty strings
    assert handler({"request_id": "  ", "decision": "  "}) is False

    assert kernel.calls == []


def test_handler_returns_kernel_decision_state() -> None:
    """Handler must expose first-wins state for non-IM approval surfaces."""
    kernel = _FakeKernel(result=False)
    handler = _build_permission_response_handler(kernel=kernel)

    accepted = handler({"request_id": "req-old", "decision": "deny"})

    assert accepted is False
    assert kernel.calls == [
        {"request_id": "req-old", "decision": "deny", "reason": ""}
    ]


def test_handler_swallows_kernel_errors() -> None:
    """A failed kernel call must not crash the WS receiver loop."""

    class _ThrowingKernel:
        def submit_permission_decision(self, **_: Any) -> bool:
            raise RuntimeError("kernel unreachable")

    handler = _build_permission_response_handler(kernel=_ThrowingKernel())

    # Must not raise.
    assert handler({"request_id": "r-1", "decision": "deny"}) is False
