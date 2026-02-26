from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def test_health_then_create_session() -> None:
    client = TestClient(create_app())

    health = client.get('/v1/health')
    create = client.post('/v1/sessions', json={})

    assert health.status_code == 200
    assert health.json()['healthy'] is True

    assert create.status_code == 201
    payload = create.json()
    assert payload['session_id'].startswith('sess_')
    assert payload['status'] == 'active'
