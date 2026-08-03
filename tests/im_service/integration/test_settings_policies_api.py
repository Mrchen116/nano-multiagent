"""Integration coverage for durable IM settings policies."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def test_policies_reseed_and_persist_across_app_reload(tmp_path: Path) -> None:
    """Recover a missing singleton, then persist edits across an app reload."""
    db_path = tmp_path / "im.db"
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        with app.state.connection:
            app.state.connection.execute("DELETE FROM settings_policies")

        reseeded = client.get("/im/v1/policies")
        assert reseeded.status_code == 200
        assert reseeded.json()["default_model"] == "codex_oauth:gpt-5.5"

        updated = client.patch(
            "/im/v1/policies",
            json={
                "default_model": "gpt-5.5-settings-final",
                "max_turn_per_run": 23,
                "max_attachment_size_mb": 36,
                "retention_days": 52,
                "audit_level": "strict",
                "rate_limit_per_min": 111,
            },
        )
        assert updated.status_code == 200

    reloaded_app = create_app(db_path=db_path)
    with TestClient(reloaded_app) as reloaded_client:
        persisted = reloaded_client.get("/im/v1/policies")

    assert persisted.status_code == 200
    assert persisted.json() == updated.json()
