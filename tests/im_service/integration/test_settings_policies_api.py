"""Integration tests for IM settings policies APIs."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def test_policies_defaults_and_roundtrip_persistence(tmp_path: Path) -> None:
    """Return stable defaults, then persist policy edits across reloads."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        initial = client.get("/im/v1/policies")
        assert initial.status_code == 200
        assert initial.json() == {
            "default_model": "gpt-5.2-codex",
            "max_turn_per_run": 14,
            "max_attachment_size_mb": 15,
            "retention_days": 30,
            "audit_level": "basic",
            "rate_limit_per_min": 45,
        }

        updated = client.patch(
            "/im/v1/policies",
            json={
                "default_model": "claude-sonnet-4",
                "max_turn_per_run": 24,
                "max_attachment_size_mb": 48,
                "retention_days": 60,
                "audit_level": "strict",
                "rate_limit_per_min": 120,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["default_model"] == "claude-sonnet-4"
        assert updated.json()["audit_level"] == "strict"

        reloaded = client.get("/im/v1/policies")
        assert reloaded.status_code == 200
        assert reloaded.json() == {
            "default_model": "claude-sonnet-4",
            "max_turn_per_run": 24,
            "max_attachment_size_mb": 48,
            "retention_days": 60,
            "audit_level": "strict",
            "rate_limit_per_min": 120,
        }
