"""Tests for PA's IM permission_response handler — feat-333 Bug F fix.

Covers the IM→PA→kernel decision return path: when IM forwards a user's
Allow/Deny choice over the gateway WS, the handler resolves the matching
kernel session via run_context_store and POSTs the decision so the parked
auto_mode_gate hook can resume.
"""

from __future__ import annotations

from typing import Any

import pytest

from personal_assistant.main import _build_permission_response_handler


class _FakeKernelClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def submit_permission_decision(
        self,
        *,
        session_id: str,
        request_id: str,
        decision: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {"session_id": session_id, "request_id": request_id, "decision": decision}
        )
        return {"resolved": True, "request_id": request_id, "decision": decision}


def test_handler_routes_to_kernel_session_via_message_id_lookup() -> None:
    client = _FakeKernelClient()
    store: dict[str, dict[str, str]] = {
        "run-1": {
            "kernel_session_id": "sess-A",
            "message_id": "im-msg-7",
            "conversation_id": "c-1",
            "agent_id": "a-1",
        },
        "run-2": {
            "kernel_session_id": "sess-B",
            "message_id": "im-msg-9",
            "conversation_id": "c-2",
            "agent_id": "a-2",
        },
    }
    handler = _build_permission_response_handler(
        kernel_client=client,  # type: ignore[arg-type]
        run_context_store=store,
    )

    handler({"request_id": "req-xyz", "decision": "allow_once", "message_id": "im-msg-9"})

    assert client.calls == [
        {"session_id": "sess-B", "request_id": "req-xyz", "decision": "allow_once"}
    ]


def test_handler_falls_back_to_sole_active_session_when_message_id_misses() -> None:
    """If turn_start ack hasn't seeded message_id yet but only one session
    is active, route to it.  Otherwise IM Allow would race with ack and
    silently drop the user's decision."""
    client = _FakeKernelClient()
    store: dict[str, dict[str, str]] = {
        "run-1": {
            "kernel_session_id": "sess-only",
            "message_id": "",  # ack not yet stored
            "conversation_id": "c-1",
            "agent_id": "a-1",
        },
    }
    handler = _build_permission_response_handler(
        kernel_client=client,  # type: ignore[arg-type]
        run_context_store=store,
    )

    handler({"request_id": "req-1", "decision": "deny", "message_id": "im-msg-unknown"})

    assert client.calls == [
        {"session_id": "sess-only", "request_id": "req-1", "decision": "deny"}
    ]


def test_handler_skips_when_multiple_sessions_and_message_id_unknown() -> None:
    """Ambiguous routing — refuse rather than guess wrong session."""
    client = _FakeKernelClient()
    store: dict[str, dict[str, str]] = {
        "run-1": {"kernel_session_id": "sess-A", "message_id": ""},
        "run-2": {"kernel_session_id": "sess-B", "message_id": ""},
    }
    handler = _build_permission_response_handler(
        kernel_client=client,  # type: ignore[arg-type]
        run_context_store=store,
    )

    handler({"request_id": "req-1", "decision": "allow_once", "message_id": "x"})

    assert client.calls == []


def test_handler_ignores_malformed_frames() -> None:
    client = _FakeKernelClient()
    store: dict[str, dict[str, str]] = {
        "run-1": {"kernel_session_id": "sess-A", "message_id": "m-1"}
    }
    handler = _build_permission_response_handler(
        kernel_client=client,  # type: ignore[arg-type]
        run_context_store=store,
    )

    # Missing request_id
    handler({"decision": "allow_once", "message_id": "m-1"})
    # Missing decision
    handler({"request_id": "r-1", "message_id": "m-1"})
    # Empty strings
    handler({"request_id": "  ", "decision": "  ", "message_id": "m-1"})

    assert client.calls == []


def test_handler_swallows_kernel_errors() -> None:
    """A failed POST must not crash the WS receiver loop."""

    class _ThrowingClient:
        def submit_permission_decision(self, **_: Any) -> dict[str, Any]:
            raise RuntimeError("kernel unreachable")

    handler = _build_permission_response_handler(
        kernel_client=_ThrowingClient(),  # type: ignore[arg-type]
        run_context_store={"r": {"kernel_session_id": "s", "message_id": "m"}},
    )

    # Must not raise.
    handler({"request_id": "r-1", "decision": "deny", "message_id": "m"})
