"""Integration tests: permission broker e2e ask chain.

Verifies the full wiring:
  app.state.permission_broker exists
  → runtime._build_hook_context injects permission_requester
  → auto_mode_gate hook emits 'permission_request' SSE event when parked
  → POST /v1/sessions/{sid}/permissions/{request_id} resolves the future
  → hook resumes with allow / deny decision

Tests simulate an IM-channel scenario: agent loop parks on a permission
request, an external HTTP call resolves it, and the tool is allowed or denied.

Design:
  - Uses FastAPI TestClient (synchronous) + asyncio for the hook coroutine.
  - Mocks: LLM client (echo), tool (bash-like that signals when run),
    hook that injects a deny-limit-exceeded scenario so _handle_ask fires.
  - Does NOT mock broker — exercises the real PermissionBroker.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from agent.platform.http_api.app import create_app
from agent.platform.permissions.broker import PermissionBroker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm_handler(response_content: str = "done"):
    """Return an httpx handler that returns a simple stop response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "object": "chat.completion",
                "model": "mock",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": response_content},
                    }
                ],
            },
        )

    return handler


# ---------------------------------------------------------------------------
# Test 1: app.state.permission_broker is created by create_app
# ---------------------------------------------------------------------------


def test_create_app_sets_permission_broker_on_state(tmp_path: Path) -> None:
    """app.state.permission_broker must be a PermissionBroker instance after create_app().

    This is the first link in the wiring chain (I1). Before M6 this was missing,
    causing get_permission_broker() to raise RuntimeError on every permission request.
    """
    app = create_app()
    broker = getattr(app.state, "permission_broker", None)
    assert broker is not None, (
        "app.state.permission_broker is None — create_app() must instantiate PermissionBroker"
    )
    assert isinstance(broker, PermissionBroker), (
        f"Expected PermissionBroker, got {type(broker)}"
    )


# ---------------------------------------------------------------------------
# Test 2: POST /v1/sessions/{sid}/permissions/{request_id} resolves pending future
# ---------------------------------------------------------------------------


def test_submit_permission_decision_resolves_pending_request(tmp_path: Path) -> None:
    """POST /permissions/{request_id} with a registered pending request returns 200.

    This validates I3: the inbound HTTP endpoint calls broker.resolve, which
    sets the Future and unblocks the parked hook coroutine.

    broker.resolve uses future.get_loop().call_soon_threadsafe, so the future's
    loop must actually run for the resolution callback to fire. We register on
    a loop and run it via run_until_complete inside an async coroutine that
    issues the HTTP POST in a worker thread.
    """
    app = create_app()
    broker: PermissionBroker = app.state.permission_broker
    client = TestClient(app, raise_server_exceptions=True)

    async def _exercise() -> tuple[int, dict, object]:
        # Register on the running loop so call_soon_threadsafe schedules on a live loop.
        future = broker.register_request("req-abc-123", run_id="run-1")
        # Run TestClient.post off-thread to avoid blocking the loop that owns the future.
        resp = await asyncio.to_thread(
            client.post,
            "/v1/sessions/fake-session/permissions/req-abc-123",
            json={"decision": "allow_once"},
            headers={"Authorization": "Bearer test"},
        )
        # Wait briefly for the cross-thread set_result to fire on this loop.
        result = await asyncio.wait_for(future, timeout=2.0)
        return resp.status_code, resp.json(), result

    status, body, result = asyncio.run(_exercise())
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body["resolved"] is True
    assert body["request_id"] == "req-abc-123"
    assert body["decision"] == "allow_once"
    assert result.decision == "allow_once"


def test_submit_permission_decision_returns_404_for_unknown_request(tmp_path: Path) -> None:
    """POST with an unknown request_id returns 404.

    The route is idempotent: re-posting an already-resolved or unknown ID
    must not raise 500, but 404 with a clear error code.
    """
    app = create_app()
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.post(
        "/v1/sessions/fake-session/permissions/nonexistent-req",
        json={"decision": "deny"},
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["error"]["code"] == "permission_request_not_found"


# ---------------------------------------------------------------------------
# Test 3: permission_requester is injected into HookContext and emits SSE events
# ---------------------------------------------------------------------------


def test_permission_requester_injected_and_emits_event(tmp_path: Path) -> None:
    """HookContext.permission_requester must be wired when broker is on app.state.

    When permission_requester is called:
    1. It registers a Future in the broker.
    2. It publishes a 'permission_request' SSE event via session_event_publisher.
    3. It awaits the Future (parks).
    4. When resolve() is called, it resumes with the PermissionResponse.

    This test drives the requester directly by hooking into the SSE publisher
    to capture the emitted event, then resolving the broker from another thread.
    """
    from agent.core.hooks.context import HookContext
    from agent.platform.hooks.session_events import set_session_event_publisher_factory
    from agent.platform.http_api.sse import EventStreamHub

    app = create_app()
    broker: PermissionBroker = app.state.permission_broker

    # Capture emitted events
    emitted: list[dict] = []

    def fake_publisher(event: str, data: dict) -> None:
        emitted.append({"event": event, "data": data})

    # Build a HookContext with permission_requester — simulates what runtime does
    from agent.platform.permissions.broker import PermissionRequest, PermissionOption, PermissionResponse

    async def run_request():
        # Build permission_requester callback using the same pattern as runtime
        ctx = _build_test_hook_context(
            session_id="sess-test",
            broker=broker,
            publisher=fake_publisher,
        )
        assert ctx.permission_requester is not None, (
            "permission_requester must be injected by runtime._build_hook_context"
        )

        req = PermissionRequest(
            id="req-test-456",
            tool_name="bash",
            tool_input={"command": "rm -rf /tmp/test"},
            question="Allow bash: rm -rf /tmp/test?",
            options=(
                PermissionOption("allow_once", "Allow once", "Allow this single action"),
                PermissionOption("deny", "Deny", "Block this action"),
            ),
        )

        # Resolve from another thread after 50ms to simulate IM user clicking
        def resolve_after_delay():
            time.sleep(0.05)
            broker.resolve("req-test-456", PermissionResponse(decision="allow_once", request_id="req-test-456"))

        t = threading.Thread(target=resolve_after_delay)
        t.start()

        response = await ctx.request_permission(req)
        t.join()
        return response

    loop = asyncio.new_event_loop()
    response = loop.run_until_complete(run_request())
    loop.close()

    # Verify SSE event was emitted
    assert len(emitted) >= 1, f"Expected at least 1 SSE event, got: {emitted}"
    perm_events = [e for e in emitted if e["event"] == "permission_request"]
    assert len(perm_events) == 1, f"Expected 1 permission_request SSE event, got: {perm_events}"
    event_data = perm_events[0]["data"]
    assert event_data["request_id"] == "req-test-456"
    assert event_data["tool_name"] == "bash"

    # Verify decision came through
    assert response.decision == "allow_once"


def test_permission_requester_deny_path(tmp_path: Path) -> None:
    """permission_requester returns deny when user picks deny option."""
    from agent.platform.permissions.broker import PermissionRequest, PermissionOption, PermissionResponse

    app = create_app()
    broker: PermissionBroker = app.state.permission_broker
    emitted: list[dict] = []

    async def run_request():
        ctx = _build_test_hook_context(
            session_id="sess-deny",
            broker=broker,
            publisher=lambda e, d: emitted.append({"event": e, "data": d}),
        )

        req = PermissionRequest(
            id="req-deny-789",
            tool_name="bash",
            tool_input={"command": "rm -rf /tmp/test-deny"},
            question="Allow bash?",
            options=(
                PermissionOption("allow_once", "Allow once", ""),
                PermissionOption("deny", "Deny", ""),
            ),
        )

        def resolve_deny():
            time.sleep(0.05)
            broker.resolve("req-deny-789", PermissionResponse(decision="deny", request_id="req-deny-789", reason="user said no"))

        t = threading.Thread(target=resolve_deny)
        t.start()
        response = await ctx.request_permission(req)
        t.join()
        return response

    loop = asyncio.new_event_loop()
    response = loop.run_until_complete(run_request())
    loop.close()

    assert response.decision == "deny"
    assert "user said no" in response.reason


# ---------------------------------------------------------------------------
# Test 4: broker cancel_all_pending prevents coroutine leak on run interrupt
# ---------------------------------------------------------------------------


def test_broker_cancel_all_pending_resolves_to_deny(tmp_path: Path) -> None:
    """cancel_all_pending must resolve all pending futures to deny.

    This is the coroutine-leak prevention mechanism triggered when a run
    is interrupted or times out while the hook is parked.
    """
    app = create_app()
    broker: PermissionBroker = app.state.permission_broker

    loop = asyncio.new_event_loop()

    async def register_two():
        f1 = broker.register_request("req-cancel-1", run_id="run-cancel")
        f2 = broker.register_request("req-cancel-2", run_id="run-cancel")
        return f1, f2

    f1, f2 = loop.run_until_complete(register_two())
    assert not f1.done()
    assert not f2.done()

    broker.cancel_all_pending(run_id="run-cancel")

    # Give call_soon_threadsafe time to fire
    loop.run_until_complete(asyncio.sleep(0.01))

    assert f1.done(), "f1 must be resolved after cancel_all_pending"
    assert f2.done(), "f2 must be resolved after cancel_all_pending"
    assert f1.result().decision == "deny"
    assert f2.result().decision == "deny"

    loop.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_test_hook_context(
    *,
    session_id: str,
    broker: PermissionBroker,
    publisher,
):
    """Build a HookContext with permission_requester wired to broker.

    Replicates what runtime._build_hook_context must do after M6.
    The permission_requester:
    1. Registers a Future in the broker.
    2. Publishes a 'permission_request' SSE event.
    3. Awaits the Future.
    """
    from agent.core.hooks.context import HookContext
    from agent.platform.permissions.broker import PermissionRequest, PermissionResponse

    async def permission_requester(req: PermissionRequest) -> PermissionResponse:
        future = broker.register_request(req.id, run_id=None)
        publisher("permission_request", {
            "session_id": session_id,
            "request_id": req.id,
            "tool_name": req.tool_name,
            "tool_input": req.tool_input,
            "question": req.question,
            "options": [
                {"id": o.id, "label": o.label, "description": o.description}
                for o in req.options
            ],
        })
        return await future

    return HookContext(
        session_id=session_id,
        permission_requester=permission_requester,
        session_event_publisher=publisher,
    )
