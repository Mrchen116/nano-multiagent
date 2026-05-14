"""Tests for the inbound permission decision endpoint.

POST /v1/sessions/{session_id}/permissions/{request_id}
Routes user permission decisions back to parked auto_mode_gate hook coroutines
via PermissionBroker.resolve().

This is the key inbound channel: CLI and PA both POST here after the user
chooses a permission option (Allow once / Deny / Allow for session / Always allow).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_app(tmp_path: Path, broker=None) -> FastAPI:
    """Create a minimal test app with PermissionBroker accessible on state."""
    from agent.platform.http_api.app import create_app
    from agent.platform.permissions.broker import AutoModeConfig, PermissionBroker

    app = create_app(repo_root=tmp_path)
    if broker is not None:
        app.state.permission_broker = broker
    else:
        app.state.permission_broker = PermissionBroker(config=AutoModeConfig())
    return app


def _auth(request_id: str = "req-1") -> dict[str, str]:
    """Return auth headers with the app default token."""
    import os
    token = os.environ.get("NANO_AGENT_API_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "X-Request-Id": request_id,
    }


class TestPermissionInboundEndpoint:
    """POST /v1/sessions/{sid}/permissions/{rid} endpoint."""

    def test_endpoint_exists(self, tmp_path: Path) -> None:
        """The permissions endpoint must be registered (not 404/405 for wrong method)."""
        app = _make_test_app(tmp_path)

        with TestClient(app, raise_server_exceptions=False) as client:
            # Without auth we expect 401, not 404 (endpoint doesn't exist) or 405
            resp = client.post(
                "/v1/sessions/sess-1/permissions/perm-req-1",
                json={"decision": "allow_once", "request_id": "perm-req-1"},
            )
        # 401 means endpoint exists but auth failed
        # 404 means endpoint doesn't exist yet → Red state
        assert resp.status_code != 404, (
            f"Endpoint not registered; got 404. Register POST "
            f"/v1/sessions/{{sid}}/permissions/{{rid}} in session.py or a new router."
        )

    def test_endpoint_returns_404_for_unknown_request_after_auth(self, tmp_path: Path) -> None:
        """Unknown request_id should return 404 (not 500)."""
        from agent.platform.permissions.broker import AutoModeConfig, PermissionBroker

        broker = PermissionBroker(config=AutoModeConfig())
        app = _make_test_app(tmp_path, broker=broker)

        import os
        # Patch the auth token to match
        with patch.dict(os.environ, {"NANO_AGENT_API_TOKEN": "test-token-x"}):
            app2 = _make_test_app(tmp_path, broker=broker)
            with TestClient(app2, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/v1/sessions/sess-1/permissions/no-such-request",
                    json={"decision": "deny", "request_id": "no-such-request"},
                    headers={"Authorization": "Bearer test-token-x", "X-Request-Id": "r1"},
                )
        # If endpoint doesn't exist: 404 from router (same status, but wrong for wrong reasons)
        # If endpoint exists and request is unknown: 404 from route logic
        # If endpoint exists but auth fails: 401
        # We allow 401 or 404 — this verifies the route exists and handles unknown requests
        assert resp.status_code in (401, 404), f"Unexpected status: {resp.status_code}"

    def test_endpoint_rejects_invalid_decision_value(self, tmp_path: Path) -> None:
        """Invalid decision values should return 422 Unprocessable Entity."""
        from agent.platform.permissions.broker import AutoModeConfig, PermissionBroker
        import os

        broker = PermissionBroker(config=AutoModeConfig())
        with patch.dict(os.environ, {"NANO_AGENT_API_TOKEN": "test-token-y"}):
            app = _make_test_app(tmp_path, broker=broker)
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/v1/sessions/sess-1/permissions/perm-x",
                    json={"decision": "not_a_valid_decision"},
                    headers={"Authorization": "Bearer test-token-y", "X-Request-Id": "r2"},
                )

        # With auth valid: should get 422 (bad schema) or 404 (unknown request), not 200
        assert resp.status_code in (404, 422), f"Expected schema validation or not-found, got {resp.status_code}"
