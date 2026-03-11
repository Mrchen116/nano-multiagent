from fastapi.testclient import TestClient

from agent.platform.http_api.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_health_then_create_session() -> None:
    client = TestClient(create_app())

    health = client.get('/v1/health')
    create = client.post('/v1/sessions', json={}, headers=_auth_headers("req-e2e-create"))

    assert health.status_code == 200
    assert health.json()['healthy'] is True

    assert create.status_code == 201
    assert create.headers["x-request-id"] == "req-e2e-create"
    payload = create.json()
    assert payload['session_id'].startswith('sess_')
    assert payload['status'] == 'active'

    detail = client.get(
        f"/v1/sessions/{payload['session_id']}",
        headers=_auth_headers("req-e2e-detail"),
    )
    listing = client.get(
        "/v1/sessions?limit=10&offset=0",
        headers=_auth_headers("req-e2e-list"),
    )

    assert detail.status_code == 200
    assert detail.json()["session_id"] == payload["session_id"]
    assert listing.status_code == 200
    assert any(item["session_id"] == payload["session_id"] for item in listing.json()["items"])
