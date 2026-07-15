"""Atomic encrypted-manifest cache and reconciliation-result outbox."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
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


@dataclass(frozen=True, slots=True)
class ChannelStatusAck:
    """Describe one correlated status result and any newly unblocked snapshot."""

    request_id: str
    outcome: str
    channel_id: str
    channel_revision: int
    payload: dict[str, object]
    next_payload: dict[str, object] | None = None


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
    _STATUS_SUCCESS_ACKS = {"accepted", "already_current"}
    _STATUS_TERMINAL_ACKS = {
        "terminal_stale_revision",
        "terminal_channel_removed",
    }

    def __init__(self, path: Path, *, node_id: str, key_id: str) -> None:
        self._path = path.expanduser().resolve(strict=False)
        self._node_id = node_id
        self._key_id = key_id
        self._state_lock = threading.RLock()

    @property
    def path(self) -> Path:
        """Return the resolved cache location."""
        return self._path

    def load_manifest(self) -> CachedChannelManifest | None:
        """Load and validate the current encrypted desired manifest."""
        with self._state_lock:
            state = self._read_state()
        return self._decode_manifest(state)

    def quarantine_key_mismatch(self) -> CachedChannelManifest | None:
        """Move a foreign-key cache aside and return its non-secret desired metadata.

        The ciphertext is never opened or overwritten. Removing it from the active
        path lets the current key create a fresh status/result outbox so Gateway can
        reconnect to IM and request credential re-entry.
        """
        with self._state_lock:
            state = self._read_state(allow_foreign_key=True)
            if state.get("key_id") == self._key_id:
                return self._decode_manifest(state)
            manifest = self._decode_manifest(state)
            quarantine_path = self._path.with_name(
                f"{self._path.name}.credential-reentry.{uuid4().hex}"
            )
            try:
                os.replace(self._path, quarantine_path)
                os.chmod(quarantine_path, 0o600)
                directory_fd = os.open(self._path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError as exc:
                raise ChannelManifestStoreError(
                    "channel manifest cache quarantine failed"
                ) from exc
            return manifest

    def _decode_manifest(
        self, state: Mapping[str, object]
    ) -> CachedChannelManifest | None:
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
        with self._state_lock:
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
        with self._state_lock:
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

    def update_provider_metadata(
        self,
        *,
        channel_id: str,
        provider_identity_fingerprint: str,
        provider_identity_revision: int,
        channel_revision: int,
        credential_revision: int,
        patch: Mapping[str, str],
    ) -> bool:
        """Persist a metadata patch only for the exact cached runtime generation."""
        with self._state_lock:
            state = self._read_state()
            raw_manifest = state.get("manifest")
            if not isinstance(raw_manifest, dict):
                return False
            raw_channels = raw_manifest.get("channels")
            if not isinstance(raw_channels, list):
                return False
            for item in raw_channels:
                if not isinstance(item, dict) or item.get("channel_id") != channel_id:
                    continue
                expected = (
                    provider_identity_fingerprint,
                    provider_identity_revision,
                    channel_revision,
                    credential_revision,
                )
                actual = (
                    str(item.get("provider_identity_fingerprint") or ""),
                    int(item.get("provider_identity_revision") or 0),
                    int(item.get("channel_revision") or 0),
                    int(item.get("credential_revision") or 0),
                )
                if actual != expected:
                    return False
                runtime = item.get("provider_runtime")
                values = runtime if isinstance(runtime, dict) else {}
                for key, value in patch.items():
                    if key in {"owner_open_id", "bot_open_id"} and not values.get(key):
                        values[key] = value
                item["provider_runtime"] = values
                self._write_state(state)
                return True
            return False

    def pending_reconcile_result(self) -> dict[str, object] | None:
        """Compose the newest head with every independently unacknowledged token."""
        with self._state_lock:
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
        manifest_revision: int | None = None,
    ) -> None:
        """Delete only head/token entries that received a terminal IM outcome."""
        with self._state_lock:
            state = self._read_state()
            outbox = self._outbox(state)
            current_head = outbox.get("head")
            head_revision_matches = manifest_revision is None or (
                isinstance(current_head, Mapping)
                and int(current_head.get("manifest_revision") or 0)
                == manifest_revision
            )
            if head_outcome in self._TERMINAL_ACKS and head_revision_matches:
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

    def record_channel_status(
        self, payload: Mapping[str, object]
    ) -> dict[str, object] | None:
        """Persist one status and return it only when no older barrier is in flight."""
        encoded = dict(payload)
        request_id = self._text(encoded, "request_id")
        channel_id = self._text(encoded, "channel_id")
        revision = self._integer(encoded, "channel_revision")
        incarnation = self._text(encoded, "runtime_incarnation")
        sequence = self._integer(encoded, "status_sequence")
        if revision < 1 or sequence < 1:
            raise ChannelManifestStoreError("channel status identity is invalid")
        generation = (revision, incarnation)
        with self._state_lock:
            state = self._read_state()
            outbox = self._status_outbox(state)
            current = outbox.get(channel_id)
            entry = current if isinstance(current, dict) else None
            current_generation = self._status_generation(entry)
            if sequence == 1 and encoded.get("instance_started") is True:
                retired = self._retired_statuses(entry)
                for slot in ("barrier", "inflight"):
                    previous = entry.get(slot) if entry is not None else None
                    if isinstance(previous, Mapping):
                        retired[str(previous.get("request_id") or "")] = dict(previous)
                entry = {
                    "channel_revision": revision,
                    "runtime_incarnation": incarnation,
                    "barrier": encoded,
                    "inflight": None,
                    "latest": None,
                    "retired": retired,
                }
                outbox[channel_id] = entry
                sendable = encoded
            else:
                if entry is None or current_generation != generation:
                    entry = {
                        "channel_revision": revision,
                        "runtime_incarnation": incarnation,
                        "barrier": None,
                        "inflight": encoded,
                        "latest": None,
                        "retired": {},
                    }
                    outbox[channel_id] = entry
                    sendable = encoded
                elif isinstance(entry.get("barrier"), Mapping) or isinstance(
                    entry.get("inflight"), Mapping
                ):
                    entry["latest"] = encoded
                    sendable = None
                else:
                    entry["inflight"] = encoded
                    sendable = encoded
            if request_id != encoded["request_id"]:  # pragma: no cover - defensive
                raise ChannelManifestStoreError("request_id is invalid")
            self._write_state(state)
            return dict(sendable) if sendable is not None else None

    def pending_channel_statuses(self) -> tuple[dict[str, object], ...]:
        """Return only each channel's current barrier or unacknowledged in-flight state."""
        with self._state_lock:
            state = self._read_state()
            outbox = self._status_outbox(state)
            pending: list[dict[str, object]] = []
            for channel_id in sorted(outbox):
                entry = outbox[channel_id]
                if not isinstance(entry, Mapping):
                    continue
                candidate = entry.get("barrier") or entry.get("inflight")
                if isinstance(candidate, Mapping):
                    pending.append(dict(candidate))
            return tuple(pending)

    def apply_channel_status_result(
        self, *, request_id: str, outcome: str
    ) -> ChannelStatusAck | None:
        """Apply a correlated result without letting terminal frames block the FIFO."""
        with self._state_lock:
            state = self._read_state()
            outbox = self._status_outbox(state)
            located = self._locate_status_request(outbox, request_id)
            if located is None:
                return None
            channel_id, entry, slot, payload = located
            revision = int(payload.get("channel_revision") or 0)
            next_payload: dict[str, object] | None = None
            if outcome in self._STATUS_SUCCESS_ACKS:
                if slot == "retired":
                    self._retired_statuses(entry).pop(request_id, None)
                else:
                    entry[slot] = None
                    latest = entry.get("latest")
                    if isinstance(latest, Mapping):
                        next_payload = dict(latest)
                        entry["inflight"] = next_payload
                        entry["latest"] = None
            elif outcome in self._STATUS_TERMINAL_ACKS:
                current_revision = int(entry.get("channel_revision") or 0)
                if current_revision == revision:
                    outbox.pop(channel_id, None)
                else:
                    self._retired_statuses(entry).pop(request_id, None)
            elif outcome == "retryable_store_busy":
                next_payload = dict(payload)
            elif outcome != "fatal_owner_mismatch":
                raise ChannelManifestStoreError("channel status outcome is invalid")
            self._write_state(state)
            return ChannelStatusAck(
                request_id=request_id,
                outcome=outcome,
                channel_id=channel_id,
                channel_revision=revision,
                payload=dict(payload),
                next_payload=next_payload,
            )

    @property
    def last_seen_manifest_revision(self) -> int:
        """Return the highest received manifest revision."""
        with self._state_lock:
            return int(self._read_state().get("last_seen_manifest_revision") or 0)

    @property
    def last_applied_manifest_revision(self) -> int:
        """Return the highest locally completed manifest revision."""
        with self._state_lock:
            return int(self._read_state().get("last_applied_manifest_revision") or 0)

    def _read_state(self, *, allow_foreign_key: bool = False) -> dict[str, object]:
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
        if not allow_foreign_key and decoded.get("key_id") != self._key_id:
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
            "status_outbox": {},
        }

    @staticmethod
    def _outbox(state: dict[str, object]) -> dict[str, object]:
        outbox = state.get("outbox")
        if not isinstance(outbox, dict):
            outbox = {"head": None, "removal_outcomes": {}}
            state["outbox"] = outbox
        return outbox

    @staticmethod
    def _status_outbox(state: dict[str, object]) -> dict[str, object]:
        outbox = state.get("status_outbox")
        if not isinstance(outbox, dict):
            outbox = {}
            state["status_outbox"] = outbox
        return outbox

    @staticmethod
    def _status_generation(entry: Mapping[str, object] | None) -> tuple[int, str] | None:
        if entry is None:
            return None
        return (
            int(entry.get("channel_revision") or 0),
            str(entry.get("runtime_incarnation") or ""),
        )

    @staticmethod
    def _retired_statuses(entry: Mapping[str, object] | None) -> dict[str, object]:
        if not isinstance(entry, dict):
            return {}
        retired = entry.get("retired")
        if not isinstance(retired, dict):
            retired = {}
            entry["retired"] = retired
        return retired

    @classmethod
    def _locate_status_request(
        cls, outbox: Mapping[str, object], request_id: str
    ) -> tuple[str, dict[str, object], str, Mapping[str, object]] | None:
        for channel_id, raw_entry in outbox.items():
            if not isinstance(channel_id, str) or not isinstance(raw_entry, dict):
                continue
            for slot in ("barrier", "inflight"):
                payload = raw_entry.get(slot)
                if isinstance(payload, Mapping) and payload.get("request_id") == request_id:
                    return channel_id, raw_entry, slot, payload
            retired = cls._retired_statuses(raw_entry)
            payload = retired.get(request_id)
            if isinstance(payload, Mapping):
                return channel_id, raw_entry, "retired", payload
        return None

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
