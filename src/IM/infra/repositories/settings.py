"""SQLite repositories for IM users, conversations, and messages."""

import sqlite3

from IM.domain.models import (
    SettingsPolicy,
)
from IM.infra.db import DEFAULT_SETTINGS_POLICIES


class SettingsPolicyRepository:
    """Persist and query the singleton settings-policy document."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_policies(self) -> SettingsPolicy:
        """Return the singleton settings-policy row."""
        row = self._connection.execute(
            """
            SELECT default_model, max_turn_per_run, max_attachment_size_mb, retention_days, audit_level, rate_limit_per_min
            FROM settings_policies
            WHERE singleton_key = 'default'
            """
        ).fetchone()
        if row is None:
            row = self._reseed_default_policy_row()
        return SettingsPolicy(
            default_model=str(row["default_model"]),
            max_turn_per_run=int(row["max_turn_per_run"]),
            max_attachment_size_mb=int(row["max_attachment_size_mb"]),
            retention_days=int(row["retention_days"]),
            audit_level=str(row["audit_level"]),
            rate_limit_per_min=int(row["rate_limit_per_min"]),
        )

    def _reseed_default_policy_row(self) -> sqlite3.Row:
        """Recreate the singleton settings-policy row for older runtime databases."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO settings_policies(
                    singleton_key,
                    default_model,
                    max_turn_per_run,
                    max_attachment_size_mb,
                    retention_days,
                    audit_level,
                    rate_limit_per_min
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(singleton_key) DO NOTHING
                """,
                (
                    DEFAULT_SETTINGS_POLICIES["singleton_key"],
                    DEFAULT_SETTINGS_POLICIES["default_model"],
                    DEFAULT_SETTINGS_POLICIES["max_turn_per_run"],
                    DEFAULT_SETTINGS_POLICIES["max_attachment_size_mb"],
                    DEFAULT_SETTINGS_POLICIES["retention_days"],
                    DEFAULT_SETTINGS_POLICIES["audit_level"],
                    DEFAULT_SETTINGS_POLICIES["rate_limit_per_min"],
                ),
            )
        row = self._connection.execute(
            """
            SELECT default_model, max_turn_per_run, max_attachment_size_mb, retention_days, audit_level, rate_limit_per_min
            FROM settings_policies
            WHERE singleton_key = 'default'
            """
        ).fetchone()
        assert row is not None
        return row

    def update_policies(
        self,
        *,
        default_model: str,
        max_turn_per_run: int,
        max_attachment_size_mb: int,
        retention_days: int,
        audit_level: str,
        rate_limit_per_min: int,
    ) -> SettingsPolicy:
        """Update the singleton settings-policy row and return the new snapshot."""
        if not default_model.strip():
            raise ValueError("default_model must be non-empty")
        if max_turn_per_run < 1:
            raise ValueError("max_turn_per_run must be >= 1")
        if max_attachment_size_mb < 1:
            raise ValueError("max_attachment_size_mb must be >= 1")
        if retention_days < 1:
            raise ValueError("retention_days must be >= 1")
        if rate_limit_per_min < 1:
            raise ValueError("rate_limit_per_min must be >= 1")
        if audit_level not in {"off", "basic", "strict"}:
            raise ValueError("audit_level must be one of off/basic/strict")
        with self._connection:
            self._connection.execute(
                """
                UPDATE settings_policies
                SET default_model = ?,
                    max_turn_per_run = ?,
                    max_attachment_size_mb = ?,
                    retention_days = ?,
                    audit_level = ?,
                    rate_limit_per_min = ?
                WHERE singleton_key = 'default'
                """,
                (
                    default_model,
                    max_turn_per_run,
                    max_attachment_size_mb,
                    retention_days,
                    audit_level,
                    rate_limit_per_min,
                ),
            )
        return self.get_policies()
