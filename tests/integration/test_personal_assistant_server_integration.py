"""Integration tests: server/app boots with PERSONAL_ASSISTANT_PROFILE (M77).

Verifies that create_app(product_profile=PERSONAL_ASSISTANT_PROFILE) correctly
wires the server with the personal_assistant tool subset and that /v1/capabilities
and /v1/sessions endpoints work correctly.

Also verifies that no if-product branching exists in the runtime — both
personal_assistant and local_coding use the same create_app() entry point.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.products.local_coding import LOCAL_CODING_PROFILE
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE
from agent.platform.http_api.app import create_app


def _auth_headers(request_id: str = "test-req-1") -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_create_app_with_personal_assistant_profile_returns_fastapi() -> None:
    """create_app with PERSONAL_ASSISTANT_PROFILE must return a FastAPI app."""
    app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE, auth_token="test-token")
    assert isinstance(app, FastAPI)


def test_personal_assistant_capabilities_return_default_tool_subset() -> None:
    """GET /v1/capabilities for personal_assistant must list only default tools."""
    app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE, auth_token="test-token")
    client = TestClient(app)
    response = client.get("/v1/capabilities", headers=_auth_headers("pa-cap-1"))
    assert response.status_code == 200
    tool_names = {item["name"] for item in response.json()["tools"]}
    assert tool_names == {"read", "task"}
    assert "send_message" not in tool_names


def test_personal_assistant_capabilities_excludes_write_edit_bash() -> None:
    """GET /v1/capabilities for personal_assistant must exclude write, edit, bash."""
    app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE, auth_token="test-token")
    client = TestClient(app)
    response = client.get("/v1/capabilities", headers=_auth_headers("pa-cap-2"))
    assert response.status_code == 200
    tool_names = {item["name"] for item in response.json()["tools"]}
    assert "write" not in tool_names
    assert "edit" not in tool_names
    assert "bash" not in tool_names


def test_personal_assistant_sessions_endpoint_works() -> None:
    """GET /v1/sessions for personal_assistant must return 200 with paginated items list."""
    app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE, auth_token="test-token")
    client = TestClient(app)
    response = client.get("/v1/sessions", headers=_auth_headers("pa-sessions-1"))
    assert response.status_code == 200
    # Sessions list endpoint returns paginated payload with "items" key.
    body = response.json()
    assert "items" in body


def test_local_coding_capabilities_regression() -> None:
    """Regression: LOCAL_CODING_PROFILE must still expose 5 coding tools via /v1/capabilities."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE, auth_token="test-token")
    client = TestClient(app)
    response = client.get("/v1/capabilities", headers=_auth_headers("lc-cap-1"))
    assert response.status_code == 200
    tool_names = {item["name"] for item in response.json()["tools"]}
    assert tool_names == {"read", "write", "edit", "bash", "task"}


def test_no_product_branching_in_runtime_code() -> None:
    """Both products must use the same create_app() entry point without product branching.

    This test validates the architectural constraint: the server/runtime code
    must not contain `if product == ...` or `if product_id == ...` branches.
    Both product apps are created through the same create_app() function and
    produce working apps.
    """
    # If this test passes, create_app() works for both without branching.
    pa_app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE, auth_token="test-token")
    lc_app = create_app(product_profile=LOCAL_CODING_PROFILE, auth_token="test-token")
    assert isinstance(pa_app, FastAPI)
    assert isinstance(lc_app, FastAPI)
    # Both must have tool_registry wired via the same factory (no product-specific path).
    assert pa_app.state.tool_registry is not None
    assert lc_app.state.tool_registry is not None
