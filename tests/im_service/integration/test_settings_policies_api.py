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


def test_policies_reseed_missing_singleton_row(tmp_path: Path) -> None:
    """Recreate the singleton row when an older runtime DB is missing it."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        with app.state.connection:
            app.state.connection.execute("DELETE FROM settings_policies")

        reseeded = client.get("/im/v1/policies")
        assert reseeded.status_code == 200
        assert reseeded.json() == {
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
                "default_model": "gpt-5.4-settings-final",
                "max_turn_per_run": 23,
                "max_attachment_size_mb": 36,
                "retention_days": 52,
                "audit_level": "strict",
                "rate_limit_per_min": 111,
            },
        )
        assert updated.status_code == 200
        assert updated.json() == {
            "default_model": "gpt-5.4-settings-final",
            "max_turn_per_run": 23,
            "max_attachment_size_mb": 36,
            "retention_days": 52,
            "audit_level": "strict",
            "rate_limit_per_min": 111,
        }

        persisted = client.get("/im/v1/policies")
        assert persisted.status_code == 200
        assert persisted.json() == {
            "default_model": "gpt-5.4-settings-final",
            "max_turn_per_run": 23,
            "max_attachment_size_mb": 36,
            "retention_days": 52,
            "audit_level": "strict",
            "rate_limit_per_min": 111,
        }
