"""Atomic encrypted-manifest cache and reconciliation-result outbox."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Mapping
from uuid import uuid4

if TYPE_CHECKING:
    from personal_assistant.gateway.channel_manager import ChannelManifest


class ChannelManifestStoreError(RuntimeError):
    """Report an invalid, foreign, or unreadable local channel manifest."""


@dataclass(frozen=True, slots=True)
class CachedChannelSpec:
    """Persist one managed channel without decrypted credential material."""

    channel_id: str
    agent_id: str
    provider: str
    enabled: bool
    config: dict[str, object]
    credential_envelope: dict[str, object]
    credential_key_id: str
    provider_runtime: dict[str, str]
    provider_identity_fingerprint: str
    provider_identity_revision: int
    channel_revision: int
    credential_revision: int


@dataclass(frozen=True, slots=True)
class CachedRemovalIntent:
    """Persist one credential-free deletion identity until IM acknowledges it."""

    removal_token: str
    channel_id: str
    agent_id: str
    provider: str
    deletion_manifest_revision: int


@dataclass(frozen=True, slots=True)
class CachedChannelManifest:
    """Represent the last atomically committed full desired manifest."""

    owner_id: str
    node_id: str
    manifest_revision: int
    channels: tuple[CachedChannelSpec, ...]
    removals: tuple[CachedRemovalIntent, ...]


class ChannelManifestStore:
    """Persist encrypted desired state and per-token result ACK state atomically.

    Args:
        path: Cache file beside the Gateway config and node private key.
        node_id: Current configured node identity; foreign caches fail closed.
        key_id: Current credential key identity; undecryptable caches fail closed.

    Side Effects:
        Writes a mode-0600 JSON file using fsync plus atomic rename.
    """

    _VERSION = 1
    _TERMINAL_ACKS = {
        "accepted",
        "already_applied",
        "already_applied_by_head",
    }

    def __init__(self, path: Path, *, node_id: str, key_id: str) -> None:
        self._path = path.expanduser().resolve(strict=False)
        self._node_id = node_id
        self._key_id = key_id

    @property
    def path(self) -> Path:
        """Return the resolved cache location."""
        return self._path

    def load_manifest(self) -> CachedChannelManifest | None:
        """Load and validate the current encrypted desired manifest."""
        state = self._read_state()
        raw_manifest = state.get("manifest")
        if not isinstance(raw_manifest, Mapping):
            return None
        raw_channels = raw_manifest.get("channels")
        raw_removals = raw_manifest.get("removals")
        channels = tuple(
            self._decode_channel(item)
            for item in raw_channels
            if isinstance(item, Mapping)
        ) if isinstance(raw_channels, list) else ()
        removals = tuple(
            self._decode_removal(item)
            for item in raw_removals
            if isinstance(item, Mapping)
        ) if isinstance(raw_removals, list) else ()
        return CachedChannelManifest(
            owner_id=self._text(raw_manifest, "owner_id"),
            node_id=self._node_id,
            manifest_revision=self._integer(raw_manifest, "manifest_revision"),
            channels=channels,
            removals=removals,
        )

    def commit_manifest(self, manifest: ChannelManifest) -> None:
        """Atomically replace desired state without persisting opened credentials."""
        if manifest.node_id and manifest.node_id != self._node_id:
            raise ChannelManifestStoreError("node_id mismatch")
        state = self._read_state()
        state["manifest"] = {
            "owner_id": manifest.owner_id,
            "node_id": self._node_id,
            "manifest_revision": manifest.manifest_revision,
            "channels": [self._encode_channel(item) for item in manifest.channels],
            "removals": [self._encode_removal(item) for item in manifest.removals],
        }
        state["last_seen_manifest_revision"] = max(
            int(state.get("last_seen_manifest_revision") or 0),
            manifest.manifest_revision,
        )
        self._write_state(state)

    def record_reconcile_result(
        self,
        *,
        manifest_revision: int,
        outcome: str,
        applied_channel_ids: tuple[str, ...],
        removal_outcomes: tuple[Mapping[str, object], ...],
        failures: tuple[Mapping[str, object], ...],
    ) -> None:
        """Merge one head result and token outcomes into the persistent outbox."""
        state = self._read_state()
        outbox = self._outbox(state)
        head = {
            "manifest_revision": manifest_revision,
            "outcome": outcome,
            "applied_channel_ids": list(applied_channel_ids),
            "failures": [dict(item) for item in failures],
        }
        current_head = outbox.get("head")
        if not isinstance(current_head, Mapping) or manifest_revision >= int(
            current_head.get("manifest_revision") or 0
        ):
            outbox["head"] = head
        token_outcomes = outbox.setdefault("removal_outcomes", {})
        if not isinstance(token_outcomes, dict):
            token_outcomes = {}
            outbox["removal_outcomes"] = token_outcomes
        for item in removal_outcomes:
            token = item.get("removal_token")
            if isinstance(token, str) and token:
                token_outcomes[token] = dict(item)
        if outcome == "applied":
            state["last_applied_manifest_revision"] = max(
                int(state.get("last_applied_manifest_revision") or 0),
                manifest_revision,
            )
        self._write_state(state)

    def pending_reconcile_result(self) -> dict[str, object] | None:
        """Compose the newest head with every independently unacknowledged token."""
        state = self._read_state()
        outbox = self._outbox(state)
        head = outbox.get("head")
        token_map = outbox.get("removal_outcomes")
        tokens = list(token_map.values()) if isinstance(token_map, Mapping) else []
        if not isinstance(head, Mapping) and not tokens:
            return None
        payload = dict(head) if isinstance(head, Mapping) else {
            "manifest_revision": int(state.get("last_applied_manifest_revision") or 0),
            "outcome": "applied",
            "applied_channel_ids": [],
            "failures": [],
        }
        payload["removal_outcomes"] = tokens
        return payload

    def ack_reconcile_result(
        self,
        *,
        head_outcome: str,
        removal_token_outcomes: list[Mapping[str, object]],
    ) -> None:
        """Delete only head/token entries that received a terminal IM outcome."""
        state = self._read_state()
        outbox = self._outbox(state)
        if head_outcome in self._TERMINAL_ACKS:
            outbox["head"] = None
        token_map = outbox.get("removal_outcomes")
        if isinstance(token_map, dict):
            for item in removal_token_outcomes:
                token = item.get("removal_token")
                outcome = item.get("outcome")
                if (
                    isinstance(token, str)
                    and isinstance(outcome, str)
                    and outcome in self._TERMINAL_ACKS
                ):
                    token_map.pop(token, None)
        self._write_state(state)

    @property
    def last_seen_manifest_revision(self) -> int:
        """Return the highest received manifest revision."""
        return int(self._read_state().get("last_seen_manifest_revision") or 0)

    @property
    def last_applied_manifest_revision(self) -> int:
        """Return the highest locally completed manifest revision."""
        return int(self._read_state().get("last_applied_manifest_revision") or 0)

    def _read_state(self) -> dict[str, object]:
        if not self._path.exists():
            return self._empty_state()
        try:
            decoded = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChannelManifestStoreError("channel manifest cache is unreadable") from exc
        if not isinstance(decoded, dict) or decoded.get("version") != self._VERSION:
            raise ChannelManifestStoreError("channel manifest cache version mismatch")
        if decoded.get("node_id") != self._node_id:
            raise ChannelManifestStoreError("node_id mismatch")
        if decoded.get("key_id") != self._key_id:
            raise ChannelManifestStoreError("key_id mismatch")
        return decoded

    def _empty_state(self) -> dict[str, object]:
        return {
            "version": self._VERSION,
            "node_id": self._node_id,
            "key_id": self._key_id,
            "manifest": None,
            "last_seen_manifest_revision": 0,
            "last_applied_manifest_revision": 0,
            "outbox": {"head": None, "removal_outcomes": {}},
        }

    @staticmethod
    def _outbox(state: dict[str, object]) -> dict[str, object]:
        outbox = state.get("outbox")
        if not isinstance(outbox, dict):
            outbox = {"head": None, "removal_outcomes": {}}
            state["outbox"] = outbox
        return outbox

    def _write_state(self, state: Mapping[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_name(f".{self._path.name}.{uuid4().hex}.tmp")
        serialized = json.dumps(
            state,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temp_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
            os.chmod(self._path, 0o600)
            directory_fd = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            raise ChannelManifestStoreError("channel manifest cache write failed") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _encode_channel(item: object) -> dict[str, object]:
        envelope = getattr(item, "credential_envelope", None)
        key_id = getattr(item, "credential_key_id", None)
        if not isinstance(envelope, Mapping) or not envelope:
            raise ChannelManifestStoreError("credential envelope missing")
        if not isinstance(key_id, str) or not key_id:
            raise ChannelManifestStoreError("credential key id missing")
        generation = getattr(item, "generation")
        return {
            "channel_id": getattr(item, "channel_id"),
            "agent_id": getattr(item, "agent_id"),
            "provider": getattr(item, "provider"),
            "enabled": getattr(item, "enabled"),
            "config": dict(getattr(item, "config")),
            "credential_envelope": dict(envelope),
            "credential_key_id": key_id,
            "provider_runtime": dict(getattr(item, "provider_runtime")),
            "provider_identity_fingerprint": generation.provider_identity_fingerprint,
            "provider_identity_revision": generation.provider_identity_revision,
            "channel_revision": generation.channel_revision,
            "credential_revision": generation.credential_revision,
        }

    @staticmethod
    def _encode_removal(item: object) -> dict[str, object]:
        return {
            "removal_token": getattr(item, "removal_token"),
            "channel_id": getattr(item, "channel_id"),
            "agent_id": getattr(item, "agent_id"),
            "provider": getattr(item, "provider"),
            "deletion_manifest_revision": getattr(
                item, "deletion_manifest_revision"
            ),
        }

    @classmethod
    def _decode_channel(cls, item: Mapping[str, object]) -> CachedChannelSpec:
        config = item.get("config")
        envelope = item.get("credential_envelope")
        runtime = item.get("provider_runtime")
        if not isinstance(config, Mapping) or not isinstance(envelope, Mapping):
            raise ChannelManifestStoreError("cached channel payload is invalid")
        return CachedChannelSpec(
            channel_id=cls._text(item, "channel_id"),
            agent_id=cls._text(item, "agent_id"),
            provider=cls._text(item, "provider"),
            enabled=item.get("enabled") is True,
            config=dict(config),
            credential_envelope=dict(envelope),
            credential_key_id=cls._text(item, "credential_key_id"),
            provider_runtime={
                str(key): str(value)
                for key, value in runtime.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            if isinstance(runtime, Mapping)
            else {},
            provider_identity_fingerprint=cls._text(
                item, "provider_identity_fingerprint"
            ),
            provider_identity_revision=cls._integer(
                item, "provider_identity_revision"
            ),
            channel_revision=cls._integer(item, "channel_revision"),
            credential_revision=cls._integer(item, "credential_revision"),
        )

    @classmethod
    def _decode_removal(cls, item: Mapping[str, object]) -> CachedRemovalIntent:
        return CachedRemovalIntent(
            removal_token=cls._text(item, "removal_token"),
            channel_id=cls._text(item, "channel_id"),
            agent_id=cls._text(item, "agent_id"),
            provider=cls._text(item, "provider"),
            deletion_manifest_revision=cls._integer(
                item, "deletion_manifest_revision"
            ),
        )

    @staticmethod
    def _text(item: Mapping[str, object], field: str) -> str:
        value = item.get(field)
        if not isinstance(value, str) or not value:
            raise ChannelManifestStoreError(f"{field} is required")
        return value

    @staticmethod
    def _integer(item: Mapping[str, object], field: str) -> int:
        value = item.get(field)
        if not isinstance(value, int) or value < 0:
            raise ChannelManifestStoreError(f"{field} is invalid")
        return value
