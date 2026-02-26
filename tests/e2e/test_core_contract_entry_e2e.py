from fastapi.testclient import TestClient

from nano_multiagent.core import ids
from nano_multiagent.server.app import create_app


def test_create_session_entry_respects_core_id_contract(monkeypatch) -> None:
    monkeypatch.setattr(ids, "make_session_id", lambda: "sess_contract_entry")
    client = TestClient(create_app())

    response = client.post(
        "/v1/sessions",
        json={},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    assert response.json()["session_id"] == "sess_contract_entry"
