from fastapi.testclient import TestClient

from agent.platform.http_api.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_llm_config_get_contract_shape() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    response = client.get("/v1/llm-config", headers=_auth_headers("req-llm-config-get-contract"))

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-llm-config-get-contract"

    payload = response.json()
    assert set(payload.keys()) == {"provider", "model", "base_url", "api_key", "timeout_seconds"}
    assert isinstance(payload["provider"], str)
    assert isinstance(payload["model"], str)
    assert isinstance(payload["base_url"], str)
    assert payload["api_key"] is None or isinstance(payload["api_key"], str)
    assert isinstance(payload["timeout_seconds"], (int, float))


def test_llm_config_patch_contract_shape_and_runtime_effect() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    response = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-patch-contract"),
        json={
            "provider": "anthropic",
            "model": "kimiCoding:K2.6",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-llm-config-patch-contract"

    payload = response.json()
    assert set(payload.keys()) == {"provider", "model", "base_url", "api_key", "timeout_seconds"}
    assert payload["provider"] == "anthropic"
    assert payload["model"] == "kimiCoding:K2.6"

    capabilities = client.get("/v1/capabilities", headers=_auth_headers("req-cap-after-llm-config-contract"))
    assert capabilities.status_code == 200
    capabilities_payload = capabilities.json()
    assert capabilities_payload["llm"]["active_provider"] == "anthropic"
    assert capabilities_payload["llm"]["active_model"] == "kimiCoding:K2.6"


def test_llm_config_patch_error_contract_shape() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    response = client.patch("/v1/llm-config", headers=_auth_headers("req-llm-config-patch-error"), json={})

    assert response.status_code == 400
    assert response.headers["x-request-id"] == "req-llm-config-patch-error"

    payload = response.json()
    assert set(payload.keys()) == {"error"}
    error = payload["error"]
    assert set(error.keys()) == {"code", "message", "retryable", "trace_id"}
    assert error["code"] == "invalid_request"
    assert isinstance(error["message"], str)
    assert error["retryable"] is False
    assert isinstance(error["trace_id"], str)
