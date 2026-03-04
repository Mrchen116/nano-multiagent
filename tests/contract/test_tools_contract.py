from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_tools_contract_returns_name_description_and_schema() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    response = client.get("/v1/tools", headers=_auth_headers("req-tools-contract"))

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-tools-contract"

    payload = response.json()
    assert set(payload.keys()) == {"tools"}
    assert isinstance(payload["tools"], list)
    assert payload["tools"]

    first = payload["tools"][0]
    assert set(first.keys()) == {"name", "description", "input_schema"}
    assert isinstance(first["name"], str)
    assert isinstance(first["description"], str)
    assert isinstance(first["input_schema"], dict)

    names = {item["name"] for item in payload["tools"]}
    assert {"read", "write", "edit", "bash"}.issubset(names)


def test_tools_contract_descriptions_do_not_expose_placeholders() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    response = client.get("/v1/tools", headers=_auth_headers("req-tools-no-placeholder"))

    assert response.status_code == 200
    descriptions = [item["description"] for item in response.json()["tools"]]
    assert descriptions
    assert all("${" not in description for description in descriptions)
