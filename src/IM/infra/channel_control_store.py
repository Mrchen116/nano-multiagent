"""Independent SQLite transaction owner for external channel control state."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
class ChannelRemovalView:
    """Secret-free persistent projection while runtime deletion is unconfirmed."""

    channel_id: str
    provider: str
    display_config: dict[str, object]
    deletion_manifest_revision: int
    apply_state: Literal["pending", "failed"]
    apply_error: dict[str, str] | None
    created_at: str


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

    def as_payload(self) -> dict[str, object]:
        """Serialize one internal desired item for its authenticated node only."""
        return {
            "channel_id": self.channel_id,
            "agent_id": self.agent_id,
            "node_id": self.node_id,
            "provider": self.provider,
            "enabled": self.enabled,
            "config": self.config,
            "provider_identity_fingerprint": self.provider_identity_fingerprint,
            "provider_identity_revision": self.provider_identity_revision,
            "provider_runtime": self.provider_runtime,
            "credential_envelope": self.credential_envelope,
            "credential_key_id": self.credential_key_id,
            "credential_revision": self.credential_revision,
            "channel_revision": self.channel_revision,
        }


@dataclass(frozen=True, slots=True)
class ManifestRemoval:
    """Credential-free removal intent delivered until its token is confirmed."""

    removal_token: str
    channel_id: str
    agent_id: str
    provider: str
    deletion_manifest_revision: int

    def as_payload(self) -> dict[str, object]:
        """Serialize the stable deletion identity for Gateway reconciliation."""
        return {
            "removal_token": self.removal_token,
            "channel_id": self.channel_id,
            "agent_id": self.agent_id,
            "provider": self.provider,
            "deletion_manifest_revision": self.deletion_manifest_revision,
        }


@dataclass(frozen=True, slots=True)
class ChannelManifest:
    """Atomic full desired snapshot for one owner-bound node."""

    owner_id: str
    node_id: str
    manifest_revision: int
    channels: tuple[ManifestChannel, ...]
    removals: tuple[ManifestRemoval, ...] = ()

    def as_payload(self, *, request_id: str) -> dict[str, object]:
        """Serialize a complete reconcile frame without exposing plaintext secret."""
        return {
            "request_id": request_id,
            "owner_id": self.owner_id,
            "node_id": self.node_id,
            "manifest_revision": self.manifest_revision,
            "channels": [item.as_payload() for item in self.channels],
            "removals": [item.as_payload() for item in self.removals],
        }


@dataclass(frozen=True, slots=True)
class ChannelMutationResult:
    """Return the user projection and same-transaction manifest snapshot."""

    channel: ChannelView
    manifest: ChannelManifest


@dataclass(frozen=True, slots=True)
class ChannelRemovalMutationResult:
    """Return a deletion receipt and its same-transaction full manifest."""

    removal: ChannelRemovalView
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
        with closing(self._connect()) as connection:
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
        with closing(self._connect()) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM agent_profiles WHERE agent_id = ? AND owner_id = ?",
                    (agent_id, owner_id),
                ).fetchone()
                is not None
            )

    def register_bound_node_public_key(
        self,
        *,
        node_id: str,
        key_id: str,
        algorithm: str,
        public_key: str,
    ) -> bool:
        """Cache a registered node key only after ownership is established."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT owner_id FROM nodes WHERE node_id = ?", (node_id,)
            ).fetchone()
        owner_id = str(row["owner_id"] or "") if row is not None else ""
        if not owner_id:
            return False
        self.register_node_public_key(
            owner_id=owner_id,
            node_id=node_id,
            key_id=key_id,
            algorithm=algorithm,
            public_key=public_key,
        )
        return True

    def current_manifest_for_node(self, *, node_id: str) -> ChannelManifest | None:
        """Read the current complete desired snapshot for an owner-bound node."""
        with closing(self._connect()) as connection:
            head = connection.execute(
                """
                SELECT owner_id, manifest_revision FROM channel_manifest_heads
                WHERE node_id = ?
                """,
                (node_id,),
            ).fetchone()
            if head is None:
                return None
            return self._manifest_snapshot(
                connection,
                owner_id=str(head["owner_id"]),
                node_id=node_id,
                manifest_revision=int(head["manifest_revision"]),
            )

    def record_reconcile_result(
        self,
        *,
        node_id: str,
        manifest_revision: int,
        outcome: str,
        applied_channel_ids: object,
        removal_outcomes: object,
        failures: object,
    ) -> dict[str, object]:
        """Apply one node-head result and ACK each removal token independently."""
        now = _utc_now()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            head = connection.execute(
                """
                SELECT owner_id, manifest_revision, applied_manifest_revision
                FROM channel_manifest_heads WHERE node_id = ?
                """,
                (node_id,),
            ).fetchone()
            if head is None:
                raise ChannelControlError("channel_not_found", status_code=404)
            current_revision = int(head["manifest_revision"])
            if manifest_revision > current_revision:
                raise ChannelControlError("channel_manifest_future", status_code=409)
            normalized_failures = failures if isinstance(failures, list | tuple) else []
            head_outcome = "accepted"
            if outcome == "applied":
                connection.execute(
                    """
                    UPDATE channel_manifest_heads SET
                        applied_manifest_revision = MAX(applied_manifest_revision, ?),
                        last_apply_error_json = CASE
                            WHEN manifest_revision = ? THEN NULL
                            ELSE last_apply_error_json
                        END,
                        applied_at = ?, updated_at = ?
                    WHERE node_id = ?
                    """,
                    (manifest_revision, current_revision, now, now, node_id),
                )
            elif outcome == "retryable_failed":
                connection.execute(
                    """
                    UPDATE channel_manifest_heads SET
                        last_apply_error_json = CASE
                            WHEN manifest_revision = ? THEN ?
                            ELSE last_apply_error_json
                        END,
                        updated_at = ?
                    WHERE node_id = ?
                    """,
                    (
                        current_revision,
                        _json(normalized_failures),
                        now,
                        node_id,
                    ),
                )
                head_outcome = "accepted"
            elif outcome == "stale":
                head_outcome = "already_applied"
            else:
                raise ChannelControlError("channel_reconcile_result_invalid", status_code=422)

            token_acks: list[dict[str, str]] = []
            normalized_removals = (
                removal_outcomes
                if isinstance(removal_outcomes, list | tuple)
                else []
            )
            for item in normalized_removals:
                if not isinstance(item, Mapping):
                    continue
                token = str(item.get("removal_token") or "")
                channel_id = str(item.get("channel_id") or "")
                removal_outcome = str(item.get("outcome") or "")
                if not token or not channel_id:
                    continue
                receipt = connection.execute(
                    """
                    SELECT * FROM agent_channel_removals
                    WHERE removal_token = ? AND channel_id = ? AND node_id = ?
                    """,
                    (token, channel_id, node_id),
                ).fetchone()
                if receipt is None:
                    deletion_revision = int(
                        item.get("deletion_manifest_revision") or 0
                    )
                    active = connection.execute(
                        "SELECT 1 FROM agent_channels WHERE channel_id = ? AND node_id = ?",
                        (channel_id, node_id),
                    ).fetchone()
                    applied_head = max(
                        int(head["applied_manifest_revision"]),
                        manifest_revision if outcome == "applied" else 0,
                    )
                    terminal = (
                        active is None
                        and deletion_revision > 0
                        and applied_head >= deletion_revision
                    )
                    token_acks.append(
                        {
                            "removal_token": token,
                            "outcome": (
                                "already_applied_by_head" if terminal else "fatal_unknown"
                            ),
                        }
                    )
                    continue
                deletion_revision = int(receipt["deletion_manifest_revision"])
                if manifest_revision < deletion_revision:
                    token_acks.append(
                        {"removal_token": token, "outcome": "fatal_unknown"}
                    )
                    continue
                if str(receipt["apply_state"]) == "applied":
                    token_acks.append(
                        {"removal_token": token, "outcome": "already_applied"}
                    )
                    continue
                if removal_outcome in {"applied", "already_absent"}:
                    connection.execute(
                        """
                        UPDATE agent_channel_removals SET
                            apply_state = 'applied', apply_error_code = NULL,
                            apply_error_message = NULL, applied_at = ?, updated_at = ?
                        WHERE removal_token = ?
                        """,
                        (now, now, token),
                    )
                    connection.execute(
                        "DELETE FROM agent_channel_status WHERE channel_id = ?",
                        (channel_id,),
                    )
                    token_acks.append(
                        {"removal_token": token, "outcome": "accepted"}
                    )
                    continue
                if removal_outcome == "failed":
                    connection.execute(
                        """
                        UPDATE agent_channel_removals SET
                            apply_state = 'failed', apply_error_code = ?,
                            apply_error_message = ?, updated_at = ?
                        WHERE removal_token = ?
                        """,
                        (
                            item.get("error_code"),
                            item.get("error_message"),
                            now,
                            token,
                        ),
                    )
                    token_acks.append(
                        {"removal_token": token, "outcome": "accepted"}
                    )
                    continue
                token_acks.append(
                    {"removal_token": token, "outcome": "fatal_unknown"}
                )
            connection.execute(
                "UPDATE channel_manifest_heads SET updated_at = ? WHERE node_id = ?",
                (now, node_id),
            )
            connection.commit()
            return {
                "head_outcome": head_outcome,
                "removal_token_outcomes": token_acks,
            }

    def record_status(self, payload: Mapping[str, object]) -> str:
        """Apply incarnation/sequence CAS and return a correlated status outcome."""
        node_id = str(payload.get("node_id") or "")
        channel_id = str(payload.get("channel_id") or "")
        channel_revision = int(payload.get("channel_revision") or 0)
        incarnation = str(payload.get("runtime_incarnation") or "")
        sequence = int(payload.get("status_sequence") or 0)
        instance_started = payload.get("instance_started") is True
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            channel = connection.execute(
                """
                SELECT channel_revision FROM agent_channels
                WHERE channel_id = ? AND node_id = ?
                """,
                (channel_id, node_id),
            ).fetchone()
            if channel is None:
                connection.rollback()
                return "terminal_channel_removed"
            if int(channel["channel_revision"]) != channel_revision:
                connection.rollback()
                return "terminal_stale_revision"
            current = connection.execute(
                "SELECT runtime_incarnation, status_sequence FROM agent_channel_status WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()
            if current is None:
                if not instance_started or sequence != 1:
                    connection.rollback()
                    return "already_current"
            elif str(current["runtime_incarnation"]) != incarnation:
                if not instance_started or sequence != 1:
                    connection.rollback()
                    return "already_current"
            elif sequence <= int(current["status_sequence"]):
                connection.rollback()
                return "already_current"
            now = _utc_now()
            connection.execute(
                """
                INSERT INTO agent_channel_status(
                    channel_id, node_id, observed_revision, runtime_incarnation,
                    status_sequence, connection_state, diagnostics_state,
                    status_code, status_message, checks_json, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    node_id = excluded.node_id,
                    observed_revision = excluded.observed_revision,
                    runtime_incarnation = excluded.runtime_incarnation,
                    status_sequence = excluded.status_sequence,
                    connection_state = excluded.connection_state,
                    diagnostics_state = excluded.diagnostics_state,
                    status_code = excluded.status_code,
                    status_message = excluded.status_message,
                    checks_json = excluded.checks_json,
                    received_at = excluded.received_at
                """,
                (
                    channel_id,
                    node_id,
                    channel_revision,
                    incarnation,
                    sequence,
                    str(payload.get("connection_state") or "failed"),
                    str(payload.get("diagnostics_state") or "unknown"),
                    payload.get("status_code"),
                    payload.get("status_message"),
                    _json(payload.get("checks") if isinstance(payload.get("checks"), list) else []),
                    now,
                ),
            )
            connection.commit()
            return "accepted"
        finally:
            connection.close()

    def record_provider_metadata(self, payload: Mapping[str, object]) -> str:
        """Apply current-generation owner/bot metadata with first-wins semantics."""
        node_id = str(payload.get("node_id") or "")
        channel_id = str(payload.get("channel_id") or "")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM agent_channels WHERE channel_id = ? AND node_id = ?",
                (channel_id, node_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return "terminal_channel_removed"
            generation_matches = (
                str(row["provider_identity_fingerprint"])
                == str(payload.get("provider_identity_fingerprint") or "")
                and int(row["provider_identity_revision"])
                == int(payload.get("provider_identity_revision") or 0)
                and int(row["channel_revision"])
                == int(payload.get("channel_revision") or 0)
                and int(row["credential_revision"])
                == int(payload.get("credential_revision") or 0)
            )
            if not generation_matches:
                connection.rollback()
                return "terminal_stale_revision"
            metadata = json.loads(str(row["provider_runtime_json"]))
            patch = payload.get("provider_runtime_patch")
            if not isinstance(patch, Mapping):
                connection.rollback()
                return "already_current"
            changed = False
            for key in ("owner_open_id", "bot_open_id"):
                value = patch.get(key)
                if isinstance(value, str) and value.strip() and not metadata.get(key):
                    metadata[key] = value.strip()
                    changed = True
            if changed:
                connection.execute(
                    "UPDATE agent_channels SET provider_runtime_json = ? WHERE channel_id = ?",
                    (_json(metadata), channel_id),
                )
            connection.commit()
            return "accepted" if changed else "already_current"
        finally:
            connection.close()

    def list_channels(
        self, *, owner_id: str, agent_id: str
    ) -> list[ChannelView | ChannelRemovalView]:
        """List active channels plus pending/failed removal receipts."""
        with closing(self._connect()) as connection:
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
            removals = connection.execute(
                """
                SELECT * FROM agent_channel_removals
                WHERE owner_id = ? AND agent_id = ? AND apply_state != 'applied'
                ORDER BY created_at, channel_id
                """,
                (owner_id, agent_id),
            ).fetchall()
            return [
                *[self._view_from_row(row) for row in rows],
                *[self._removal_view_from_row(row) for row in removals],
            ]

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
            pending_removal = connection.execute(
                """
                SELECT 1 FROM agent_channel_removals
                WHERE owner_id = ? AND agent_id = ? AND provider = ?
                  AND apply_state != 'applied'
                """,
                (owner_id, agent_id, provider),
            ).fetchone()
            if pending_removal is not None:
                raise ChannelControlError("channel_deletion_pending", status_code=409)
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

    def delete_channel(
        self,
        *,
        owner_id: str,
        agent_id: str,
        channel_id: str,
        expected_revision: int,
    ) -> ChannelRemovalMutationResult:
        """Delete desired credentials and create a durable runtime-removal receipt."""
        now = _utc_now()
        expires_at = (datetime.now(UTC) + timedelta(days=7)).isoformat().replace(
            "+00:00", "Z"
        )
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
            node_id = str(row["node_id"])
            provider = str(row["provider"])
            config = json.loads(str(row["config_json"]))
            app_id = str(config.get("app_id") or "")
            display_config = {"app_id_suffix": app_id[-5:]}
            token = f"rm_{uuid4().hex}"
            connection.execute(
                "DELETE FROM agent_channels WHERE channel_id = ?",
                (channel_id,),
            )
            manifest_revision = self._advance_manifest(
                connection, owner_id=owner_id, node_id=node_id, now=now
            )
            connection.execute(
                """
                INSERT INTO agent_channel_removals(
                    channel_id, removal_token, owner_id, agent_id, node_id,
                    provider, display_config_json, deleted_channel_revision,
                    deletion_manifest_revision, apply_state, expires_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    channel_id,
                    token,
                    owner_id,
                    agent_id,
                    node_id,
                    provider,
                    _json(display_config),
                    expected_revision,
                    manifest_revision,
                    expires_at,
                    now,
                    now,
                ),
            )
            receipt = connection.execute(
                "SELECT * FROM agent_channel_removals WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()
            assert receipt is not None
            manifest = self._manifest_snapshot(
                connection,
                owner_id=owner_id,
                node_id=node_id,
                manifest_revision=manifest_revision,
            )
            connection.commit()
            return ChannelRemovalMutationResult(
                removal=self._removal_view_from_row(receipt),
                manifest=manifest,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def retry_removal(
        self, *, owner_id: str, agent_id: str, channel_id: str
    ) -> ChannelManifest:
        """Return the unchanged current manifest for one retryable receipt."""
        with closing(self._connect()) as connection:
            receipt = connection.execute(
                """
                SELECT * FROM agent_channel_removals
                WHERE channel_id = ? AND owner_id = ? AND agent_id = ?
                  AND apply_state != 'applied'
                """,
                (channel_id, owner_id, agent_id),
            ).fetchone()
            if receipt is None:
                raise ChannelControlError("channel_not_found", status_code=404)
            head = connection.execute(
                """
                SELECT manifest_revision FROM channel_manifest_heads
                WHERE node_id = ? AND owner_id = ?
                """,
                (str(receipt["node_id"]), owner_id),
            ).fetchone()
            if head is None:
                raise ChannelControlError("channel_not_found", status_code=404)
            return self._manifest_snapshot(
                connection,
                owner_id=owner_id,
                node_id=str(receipt["node_id"]),
                manifest_revision=int(head["manifest_revision"]),
            )

    def channel_for_reconnect(
        self, *, owner_id: str, agent_id: str, channel_id: str
    ) -> tuple[ChannelView, str]:
        """Return the current desired view and node identity for a live action."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT ac.*, s.observed_revision, s.connection_state,
                       s.diagnostics_state, s.status_code, s.status_message,
                       s.checks_json, s.received_at, n.status AS node_status
                FROM agent_channels ac
                LEFT JOIN agent_channel_status s ON s.channel_id = ac.channel_id
                LEFT JOIN nodes n ON n.node_id = ac.node_id
                WHERE ac.channel_id = ? AND ac.owner_id = ? AND ac.agent_id = ?
                """,
                (channel_id, owner_id, agent_id),
            ).fetchone()
            if row is None:
                raise ChannelControlError("channel_not_found", status_code=404)
            return self._view_from_row(row), str(row["node_id"])

    def prune_applied_removals(self) -> int:
        """Delete expired hidden receipts only after the node head covers them."""
        now = _utc_now()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                DELETE FROM agent_channel_removals
                WHERE apply_state = 'applied' AND expires_at <= ?
                  AND EXISTS (
                    SELECT 1 FROM channel_manifest_heads h
                    WHERE h.node_id = agent_channel_removals.node_id
                      AND h.owner_id = agent_channel_removals.owner_id
                      AND h.applied_manifest_revision >=
                          agent_channel_removals.deletion_manifest_revision
                  )
                """,
                (now,),
            )
            connection.commit()
            return cursor.rowcount

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
        observed_revision = (
            row["observed_revision"]
            if "observed_revision" in row.keys()
            else None
        )
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
    def _removal_view_from_row(row: sqlite3.Row) -> ChannelRemovalView:
        error_code = row["apply_error_code"]
        error_message = row["apply_error_message"]
        apply_error = None
        if error_code or error_message:
            apply_error = {
                "code": str(error_code or "channel_removal_failed"),
                "message": str(error_message or "Removal could not be applied"),
            }
        return ChannelRemovalView(
            channel_id=str(row["channel_id"]),
            provider=str(row["provider"]),
            display_config=json.loads(str(row["display_config_json"])),
            deletion_manifest_revision=int(row["deletion_manifest_revision"]),
            apply_state=str(row["apply_state"]),  # type: ignore[arg-type]
            apply_error=apply_error,
            created_at=str(row["created_at"]),
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
        removal_rows = connection.execute(
            """
            SELECT * FROM agent_channel_removals
            WHERE owner_id = ? AND node_id = ? AND apply_state != 'applied'
            ORDER BY created_at, channel_id
            """,
            (owner_id, node_id),
        ).fetchall()
        removals = tuple(
            ManifestRemoval(
                removal_token=str(row["removal_token"]),
                channel_id=str(row["channel_id"]),
                agent_id=str(row["agent_id"]),
                provider=str(row["provider"]),
                deletion_manifest_revision=int(row["deletion_manifest_revision"]),
            )
            for row in removal_rows
        )
        return ChannelManifest(
            owner_id=owner_id,
            node_id=node_id,
            manifest_revision=manifest_revision,
            channels=channels,
            removals=removals,
        )
