from fastapi.testclient import TestClient

from agent.platform.http_api.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_health_capabilities_openapi_entry_flow() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    health = client.get("/v1/health")
    capabilities = client.get("/v1/capabilities", headers=_auth_headers("req-cap-e2e"))
    openapi_resp = client.get("/v1/openapi.json", headers=_auth_headers("req-openapi-e2e"))

    assert health.status_code == 200
    assert health.json()["healthy"] is True

    assert capabilities.status_code == 200
    cap_payload = capabilities.json()
    assert cap_payload["llm"]["active_provider"] in {"openai_compat", "anthropic"}
    assert cap_payload["tools"]

    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert "/v1/capabilities" in schema["paths"]
    assert "/v1/sessions/{session_id}/messages" in schema["paths"]
