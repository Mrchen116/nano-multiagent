from fastapi.testclient import TestClient

from nano_multiagent.platform.http_api.app import create_app


def test_health_endpoint_e2e() -> None:
    client = TestClient(create_app())
    response = client.get('/v1/health')

    assert response.status_code == 200
    assert response.json()['healthy'] is True
