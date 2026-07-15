"""Independent SQLite transaction owner for external channel control state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal, Mapping
from uuid import uuid4

from IM.infra.channel_credentials import ChannelEnvelopeAad, seal_channel_secret


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ChannelControlError(RuntimeError):
    """Stable application error emitted by one channel-control command."""

    def __init__(self, code: str, *, status_code: int, current: object = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.current = current


@dataclass(frozen=True, slots=True)
class ChannelView:
    """Secret-free desired and observed projection returned to authenticated users."""

    channel_id: str
    provider: str
    enabled: bool
    config: dict[str, object]
    secret_configured: bool
    channel_revision: int
    credential_revision: int
    sync_state: Literal["pending", "applied", "failed"]
    observed: dict[str, object] | None
    updated_at: str


@dataclass(frozen=True, slots=True)
class ManifestChannel:
    """Complete internal desired item delivered only to its bound Gateway node."""

    channel_id: str
    agent_id: str
    node_id: str
    provider: str
    enabled: bool
    config: dict[str, object]
    provider_identity_fingerprint: str
    provider_identity_revision: int
    provider_runtime: dict[str, object]
    credential_envelope: dict[str, object]
    credential_key_id: str
    credential_revision: int
    channel_revision: int


@dataclass(frozen=True, slots=True)
class ChannelManifest:
    """Atomic full desired snapshot for one owner-bound node."""

    owner_id: str
    node_id: str
    manifest_revision: int
    channels: tuple[ManifestChannel, ...]


@dataclass(frozen=True, slots=True)
class ChannelMutationResult:
    """Return the user projection and same-transaction manifest snapshot."""

    channel: ChannelView
    manifest: ChannelManifest


class ChannelControlStore:
    """Serialize channel commands using short independent SQLite connections."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path.expanduser().resolve(strict=False)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self._db_path),
            timeout=5,
            isolation_level=None,
            check_same_thread=False,
            cached_statements=0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def register_node_public_key(
        self,
        *,
        owner_id: str,
        node_id: str,
        key_id: str,
        algorithm: str,
        public_key: str,
    ) -> None:
        """Persist the public half advertised by an already owner-bound node."""
        now = _utc_now()
        with self._connect() as connection:
            node = connection.execute(
                "SELECT owner_id FROM nodes WHERE node_id = ?", (node_id,)
            ).fetchone()
            if node is None or str(node["owner_id"] or "") != owner_id:
                raise ChannelControlError("channel_not_found", status_code=404)
            connection.execute(
                """
                INSERT INTO node_credential_keys(
                    node_id, owner_id, key_id, algorithm, public_key, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    key_id = excluded.key_id,
                    algorithm = excluded.algorithm,
                    public_key = excluded.public_key,
                    updated_at = excluded.updated_at
                """,
                (node_id, owner_id, key_id, algorithm, public_key, now),
            )

    def agent_exists_for_owner(self, *, owner_id: str, agent_id: str) -> bool:
        """Return whether one active agent belongs to an authenticated owner."""
        with self._connect() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM agent_profiles WHERE agent_id = ? AND owner_id = ?",
                    (agent_id, owner_id),
                ).fetchone()
                is not None
            )

    def list_channels(self, *, owner_id: str, agent_id: str) -> list[ChannelView]:
        """List secret-free channel views within one owner and agent scope."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT ac.*, s.observed_revision, s.connection_state,
                       s.diagnostics_state, s.status_code, s.status_message,
                       s.checks_json, s.received_at, n.status AS node_status
                FROM agent_channels ac
                LEFT JOIN agent_channel_status s ON s.channel_id = ac.channel_id
                LEFT JOIN nodes n ON n.node_id = ac.node_id
                WHERE ac.owner_id = ? AND ac.agent_id = ?
                ORDER BY ac.created_at, ac.channel_id
                """,
                (owner_id, agent_id),
            ).fetchall()
            return [self._view_from_row(row) for row in rows]

    def create_channel(
        self,
        *,
        owner_id: str,
        agent_id: str,
        provider: str,
        enabled: bool,
        config: Mapping[str, object],
        secret: Mapping[str, str],
    ) -> ChannelMutationResult:
        """Create a unique provider instance and its first complete manifest."""
        channel_id = f"ch_{uuid4().hex}"
        now = _utc_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            node_id = self._require_agent_node(
                connection, owner_id=owner_id, agent_id=agent_id
            )
            key = self._require_node_key(
                connection, owner_id=owner_id, node_id=node_id
            )
            normalized = self._normalize_config(provider=provider, config=config)
            self._validate_secret(secret)
            identity = self._identity_fingerprint(
                provider=provider, config=normalized
            )
            envelope = seal_channel_secret(
                public_key=str(key["public_key"]),
                secret=secret,
                aad=ChannelEnvelopeAad(
                    owner_id=owner_id,
                    node_id=node_id,
                    agent_id=agent_id,
                    channel_id=channel_id,
                    provider=provider,
                    credential_revision=1,
                ),
            )
            try:
                connection.execute(
                    """
                    INSERT INTO agent_channels(
                        channel_id, owner_id, agent_id, node_id, provider, enabled,
                        config_json, provider_identity_fingerprint,
                        provider_identity_revision, provider_runtime_json,
                        credential_envelope_json, credential_key_id,
                        credential_revision, channel_revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, '{}', ?, ?, 1, 1, ?, ?)
                    """,
                    (
                        channel_id,
                        owner_id,
                        agent_id,
                        node_id,
                        provider,
                        int(enabled),
                        _json(normalized),
                        identity,
                        _json(envelope),
                        str(key["key_id"]),
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ChannelControlError(
                    "channel_provider_already_exists", status_code=409
                ) from exc
            manifest_revision = self._advance_manifest(
                connection, owner_id=owner_id, node_id=node_id, now=now
            )
            channel_row = self._channel_row(connection, channel_id=channel_id)
            manifest = self._manifest_snapshot(
                connection,
                owner_id=owner_id,
                node_id=node_id,
                manifest_revision=manifest_revision,
            )
            connection.commit()
            return ChannelMutationResult(
                channel=self._view_from_row(channel_row), manifest=manifest
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def update_channel(
        self,
        *,
        owner_id: str,
        agent_id: str,
        channel_id: str,
        expected_revision: int,
        enabled: bool,
        config: Mapping[str, object],
        credential_mode: Literal["keep", "replace"],
        secret: Mapping[str, str] | None = None,
    ) -> ChannelMutationResult:
        """Update desired state under an optimistic channel revision token."""
        now = _utc_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM agent_channels
                WHERE channel_id = ? AND owner_id = ? AND agent_id = ?
                """,
                (channel_id, owner_id, agent_id),
            ).fetchone()
            if row is None:
                raise ChannelControlError("channel_not_found", status_code=404)
            if int(row["channel_revision"]) != expected_revision:
                raise ChannelControlError(
                    "channel_revision_conflict",
                    status_code=409,
                    current=self._view_from_row(row),
                )
            provider = str(row["provider"])
            normalized = self._normalize_config(provider=provider, config=config)
            old_config = json.loads(str(row["config_json"]))
            identity_changed = normalized.get("app_id") != old_config.get("app_id")
            if identity_changed and credential_mode != "replace":
                raise ChannelControlError(
                    "channel_credentials_required", status_code=422
                )
            if credential_mode not in {"keep", "replace"}:
                raise ChannelControlError(
                    "channel_credentials_required", status_code=422
                )
            credential_revision = int(row["credential_revision"])
            envelope_json = str(row["credential_envelope_json"])
            credential_key_id = str(row["credential_key_id"])
            if credential_mode == "replace":
                if secret is None:
                    raise ChannelControlError(
                        "channel_credentials_required", status_code=422
                    )
                self._validate_secret(secret)
                key = self._require_node_key(
                    connection, owner_id=owner_id, node_id=str(row["node_id"])
                )
                credential_revision += 1
                envelope_json = _json(
                    seal_channel_secret(
                        public_key=str(key["public_key"]),
                        secret=secret,
                        aad=ChannelEnvelopeAad(
                            owner_id=owner_id,
                            node_id=str(row["node_id"]),
                            agent_id=agent_id,
                            channel_id=channel_id,
                            provider=provider,
                            credential_revision=credential_revision,
                        ),
                    )
                )
                credential_key_id = str(key["key_id"])
            identity_revision = int(row["provider_identity_revision"])
            provider_runtime_json = str(row["provider_runtime_json"])
            identity_fingerprint = str(row["provider_identity_fingerprint"])
            if identity_changed:
                identity_revision += 1
                provider_runtime_json = "{}"
                identity_fingerprint = self._identity_fingerprint(
                    provider=provider, config=normalized
                )
            channel_revision = expected_revision + 1
            connection.execute(
                """
                UPDATE agent_channels SET
                    enabled = ?, config_json = ?, provider_identity_fingerprint = ?,
                    provider_identity_revision = ?, provider_runtime_json = ?,
                    credential_envelope_json = ?, credential_key_id = ?,
                    credential_revision = ?, channel_revision = ?, updated_at = ?
                WHERE channel_id = ?
                """,
                (
                    int(enabled),
                    _json(normalized),
                    identity_fingerprint,
                    identity_revision,
                    provider_runtime_json,
                    envelope_json,
                    credential_key_id,
                    credential_revision,
                    channel_revision,
                    now,
                    channel_id,
                ),
            )
            manifest_revision = self._advance_manifest(
                connection, owner_id=owner_id, node_id=str(row["node_id"]), now=now
            )
            channel_row = self._channel_row(connection, channel_id=channel_id)
            manifest = self._manifest_snapshot(
                connection,
                owner_id=owner_id,
                node_id=str(row["node_id"]),
                manifest_revision=manifest_revision,
            )
            connection.commit()
            return ChannelMutationResult(
                channel=self._view_from_row(channel_row), manifest=manifest
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _require_agent_node(
        connection: sqlite3.Connection, *, owner_id: str, agent_id: str
    ) -> str:
        row = connection.execute(
            "SELECT node_id FROM agent_profiles WHERE agent_id = ? AND owner_id = ?",
            (agent_id, owner_id),
        ).fetchone()
        if row is None or not str(row["node_id"] or ""):
            raise ChannelControlError("channel_not_found", status_code=404)
        return str(row["node_id"])

    @staticmethod
    def _require_node_key(
        connection: sqlite3.Connection, *, owner_id: str, node_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT key_id, public_key FROM node_credential_keys
            WHERE node_id = ? AND owner_id = ?
            """,
            (node_id, owner_id),
        ).fetchone()
        if row is None:
            raise ChannelControlError(
                "channel_credential_key_unavailable", status_code=409
            )
        return row

    @staticmethod
    def _normalize_config(
        *, provider: str, config: Mapping[str, object]
    ) -> dict[str, object]:
        if provider != "feishu":
            raise ChannelControlError("channel_provider_unsupported", status_code=422)
        app_id = config.get("app_id")
        if not isinstance(app_id, str) or not app_id.strip():
            raise ChannelControlError("channel_config_invalid", status_code=422)
        return {"app_id": app_id.strip()}

    @staticmethod
    def _validate_secret(secret: Mapping[str, str]) -> None:
        app_secret = secret.get("app_secret")
        if not isinstance(app_secret, str) or not app_secret.strip():
            raise ChannelControlError("channel_credentials_required", status_code=422)

    @staticmethod
    def _identity_fingerprint(
        *, provider: str, config: Mapping[str, object]
    ) -> str:
        material = f"{provider}\0{config['app_id']}".encode()
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _advance_manifest(
        connection: sqlite3.Connection, *, owner_id: str, node_id: str, now: str
    ) -> int:
        connection.execute(
            """
            INSERT INTO channel_manifest_heads(
                node_id, owner_id, manifest_revision, applied_manifest_revision,
                initialized_at, updated_at
            ) VALUES (?, ?, 0, 0, ?, ?)
            ON CONFLICT(node_id) DO NOTHING
            """,
            (node_id, owner_id, now, now),
        )
        connection.execute(
            """
            UPDATE channel_manifest_heads
            SET manifest_revision = manifest_revision + 1, updated_at = ?
            WHERE node_id = ? AND owner_id = ?
            """,
            (now, node_id, owner_id),
        )
        row = connection.execute(
            "SELECT manifest_revision FROM channel_manifest_heads WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        assert row is not None
        return int(row["manifest_revision"])

    @staticmethod
    def _channel_row(
        connection: sqlite3.Connection, *, channel_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT ac.*, s.observed_revision, s.connection_state,
                   s.diagnostics_state, s.status_code, s.status_message,
                   s.checks_json, s.received_at, n.status AS node_status
            FROM agent_channels ac
            LEFT JOIN agent_channel_status s ON s.channel_id = ac.channel_id
            LEFT JOIN nodes n ON n.node_id = ac.node_id
            WHERE ac.channel_id = ?
            """,
            (channel_id,),
        ).fetchone()
        assert row is not None
        return row

    @staticmethod
    def _view_from_row(row: sqlite3.Row) -> ChannelView:
        observed_revision = row["observed_revision"] if "observed_revision" in row.keys() else None
        observed = None
        sync_state: Literal["pending", "applied", "failed"] = "pending"
        if observed_revision is not None:
            observed = {
                "observed_revision": int(observed_revision),
                "connection_state": str(row["connection_state"]),
                "diagnostics_state": str(row["diagnostics_state"]),
                "status_code": row["status_code"],
                "status_message": row["status_message"],
                "checks": json.loads(str(row["checks_json"])),
                "status_updated_at": str(row["received_at"]),
                "status_stale": str(row["node_status"] or "offline") != "online",
            }
            if int(observed_revision) >= int(row["channel_revision"]):
                sync_state = (
                    "failed" if str(row["connection_state"]) == "failed" else "applied"
                )
        return ChannelView(
            channel_id=str(row["channel_id"]),
            provider=str(row["provider"]),
            enabled=bool(row["enabled"]),
            config=json.loads(str(row["config_json"])),
            secret_configured=bool(row["credential_envelope_json"]),
            channel_revision=int(row["channel_revision"]),
            credential_revision=int(row["credential_revision"]),
            sync_state=sync_state,
            observed=observed,
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _manifest_snapshot(
        connection: sqlite3.Connection,
        *,
        owner_id: str,
        node_id: str,
        manifest_revision: int,
    ) -> ChannelManifest:
        rows = connection.execute(
            """
            SELECT * FROM agent_channels
            WHERE owner_id = ? AND node_id = ?
            ORDER BY created_at, channel_id
            """,
            (owner_id, node_id),
        ).fetchall()
        channels = tuple(
            ManifestChannel(
                channel_id=str(row["channel_id"]),
                agent_id=str(row["agent_id"]),
                node_id=str(row["node_id"]),
                provider=str(row["provider"]),
                enabled=bool(row["enabled"]),
                config=json.loads(str(row["config_json"])),
                provider_identity_fingerprint=str(
                    row["provider_identity_fingerprint"]
                ),
                provider_identity_revision=int(row["provider_identity_revision"]),
                provider_runtime=json.loads(str(row["provider_runtime_json"])),
                credential_envelope=json.loads(str(row["credential_envelope_json"])),
                credential_key_id=str(row["credential_key_id"]),
                credential_revision=int(row["credential_revision"]),
                channel_revision=int(row["channel_revision"]),
            )
            for row in rows
        )
        return ChannelManifest(
            owner_id=owner_id,
            node_id=node_id,
            manifest_revision=manifest_revision,
            channels=channels,
        )
