from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def test_create_session_contract() -> None:
    client = TestClient(create_app())

    response = client.post('/v1/sessions', json={})

    assert response.status_code == 201
    payload = response.json()
    assert set(payload.keys()) == {'session_id', 'status', 'created_at'}
    assert payload['session_id'].startswith('sess_')
    assert payload['status'] == 'active'
    assert isinstance(payload['created_at'], str)
