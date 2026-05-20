from fastapi.testclient import TestClient

from agent.platform.http_api.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_capabilities_contract_shape() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/capabilities", headers=_auth_headers("req-cap-contract"))

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-cap-contract"

    payload = response.json()
    assert set(payload.keys()) == {"llm", "tools"}

    llm_payload = payload["llm"]
    assert set(llm_payload.keys()) == {"active_provider", "active_model", "providers"}
    assert isinstance(llm_payload["active_provider"], str)
    assert isinstance(llm_payload["active_model"], str)
    assert isinstance(llm_payload["providers"], list)
    assert llm_payload["providers"]

    provider = llm_payload["providers"][0]
    assert set(provider.keys()) == {"provider", "default_model", "models"}
    assert isinstance(provider["provider"], str)
    assert isinstance(provider["default_model"], str)
    assert isinstance(provider["models"], list)
    assert provider["models"]

    model = provider["models"][0]
    assert set(model.keys()) == {
        "model",
        "default_base_url",
        "supports_text",
        "supports_image",
        "supports_tools",
        "supports_streaming",
    }

    assert isinstance(payload["tools"], list)
    assert payload["tools"]
    first_tool = payload["tools"][0]
    assert set(first_tool.keys()) == {"name", "description", "input_schema"}


def test_openapi_contract_is_available_under_v1() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/openapi.json", headers=_auth_headers("req-openapi-contract"))

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-openapi-contract"

    payload = response.json()
    assert isinstance(payload.get("openapi"), str)
    assert isinstance(payload.get("info"), dict)
    assert isinstance(payload.get("paths"), dict)
    assert "/v1/capabilities" in payload["paths"]
    assert "/v1/llm-config" in payload["paths"]
    assert "/v1/openapi.json" in payload["paths"]
