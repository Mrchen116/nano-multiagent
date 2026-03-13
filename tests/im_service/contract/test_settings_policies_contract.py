"""Contract tests for IM settings policies endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def test_policies_contract_shape_and_patch_semantics(tmp_path: Path) -> None:
    """Expose stable policies fields for settings-page reads and writes."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        response = client.get("/im/v1/policies")
        assert response.status_code == 200
        assert set(response.json()) == {
            "default_model",
            "max_turn_per_run",
            "max_attachment_size_mb",
            "retention_days",
            "audit_level",
            "rate_limit_per_min",
        }

        updated = client.patch(
            "/im/v1/policies",
            json={
                "default_model": "gpt-5.2-codex",
                "max_turn_per_run": 21,
                "max_attachment_size_mb": 32,
                "retention_days": 90,
                "audit_level": "strict",
                "rate_limit_per_min": 88,
            },
        )
        assert updated.status_code == 200
        assert updated.json() == {
            "default_model": "gpt-5.2-codex",
            "max_turn_per_run": 21,
            "max_attachment_size_mb": 32,
            "retention_days": 90,
            "audit_level": "strict",
            "rate_limit_per_min": 88,
        }
