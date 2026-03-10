from fastapi.testclient import TestClient

from nano_multiagent.platform.http_api.app import create_app


def test_health_contract() -> None:
    client = TestClient(create_app())
    response = client.get('/v1/health')

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {'healthy', 'version', 'node_id'}
    assert isinstance(payload['healthy'], bool)
    assert isinstance(payload['version'], str)
    assert isinstance(payload['node_id'], str)
