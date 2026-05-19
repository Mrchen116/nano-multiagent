from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService


def test_create_session_survives_app_rebuild(tmp_path: Path) -> None:
    sessions_dir = tmp_path / "sessions"
    first_service = SessionService(store=JsonlSessionStore(data_dir=sessions_dir))
    first_app = create_app(session_store=first_service.manager._store)
    first_client = TestClient(first_app)

    response = first_client.post(
        "/v1/sessions",
        json={},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    session_id = response.json()["session_id"]

    second_app = create_app(session_store=SessionService(store=JsonlSessionStore(data_dir=sessions_dir)).manager._store)
    restored = second_app.state.session_service.get_session(session_id)

    assert restored is not None
    assert restored.session_id == session_id
    assert restored.status == "active"
