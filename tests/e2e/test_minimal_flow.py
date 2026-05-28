from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_health_then_create_session(tmp_path: Path) -> None:
    # Bare create_app() has no product profile, so SessionService falls back to
    # the stateless store (data_dir=None) — every op must carry workspace_root.
    # This test exercises HTTP ops without workspace_root, so supply an explicit
    # data_dir-backed test store (legacy flat layout) as documented scaffolding.
    client = TestClient(create_app(session_store=JsonlSessionStore(data_dir=tmp_path)))

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
