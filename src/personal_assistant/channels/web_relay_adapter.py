"""Web IM relay channel adapter fed by IM websocket downstream frames."""
from __future__ import annotations

import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from personal_assistant.channels.base import InboundHandler, InboundMessage, OutboundMessage

_SEEN_KEYS_MAX = 1000
_DEDUP_TTL_SECONDS = 7 * 24 * 60 * 60
_DEDUP_SCHEMA = """
CREATE TABLE IF NOT EXISTS relay_deduplication_keys (
    idempotency_key TEXT PRIMARY KEY,
    expires_at REAL NOT NULL,
    seen_at REAL NOT NULL
)
"""


class RelayDeduplicationStore:
    """Persist and restore seen relay idempotency keys with TTL."""

    def __init__(
        self,
        *,
        db_path: Path,
        ttl_seconds: int = _DEDUP_TTL_SECONDS,
        seen_keys: deque[str] | None = None,
        now: callable | None = None,
    ) -> None:
        self._db_path = db_path
        self._ttl_seconds = ttl_seconds
        self._seen_idempotency_keys = seen_keys if seen_keys is not None else deque()
        self._lock = threading.Lock()
        self._now = now or time.time
        self._init_db()

    def contains(self, key: str) -> bool:
        return key in self._seen_idempotency_keys

    def add(self, key: str) -> None:
        now = self._now()
        expires_at = now + self._ttl_seconds
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO relay_deduplication_keys (idempotency_key, expires_at, seen_at) VALUES (?, ?, ?)",
                    (key, expires_at, now),
                )
                conn.commit()
            finally:
                conn.close()
            self._append_seen_key(key)

    def load_from_db(self) -> None:
        now = self._now()
        with self._lock:
            self._purge_expired_locked(now)
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT idempotency_key FROM relay_deduplication_keys WHERE expires_at > ? ORDER BY seen_at ASC",
                    (now,),
                ).fetchall()
            finally:
                conn.close()
            self._seen_idempotency_keys.clear()
            for row in rows:
                self._append_seen_key(row[0])

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_expired_locked(self._now())

    def _append_seen_key(self, key: str) -> None:
        try:
            self._seen_idempotency_keys.remove(key)
        except ValueError:
            pass
        self._seen_idempotency_keys.append(key)
        if len(self._seen_idempotency_keys) > _SEEN_KEYS_MAX:
            self._seen_idempotency_keys.popleft()

    def _purge_expired_locked(self, now: float) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM relay_deduplication_keys WHERE expires_at <= ?",
                (now,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
        finally:
            conn.close()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(_DEDUP_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))



@dataclass(frozen=True, slots=True)
class RelayEnvelope:
    """Represent one downstream relay.message payload from IM.

    Args:
        relay_task_id: Relay task identifier created by IM service.
        idempotency_key: Upstream idempotency key for this relay delivery.
        sender_user_id: User id that authored the Web IM message.
        conversation_id: IM conversation id used as the external chat id.
        content: Plain-text message content.
        agent_id: Optional explicit target agent.
        metadata: Opaque remaining relay metadata.
    """

    relay_task_id: str
    idempotency_key: str
    sender_user_id: str
    conversation_id: str
    content: str
    agent_id: str | None
    metadata: Mapping[str, Any]


class WebRelayAdapter:
    """Adapt IM relay.message pushes into the gateway channel contract.

    Notes:
        This adapter is process-local and only receives inbound relay frames from the
        IM websocket connection. Outbound sends are normalized and recorded so the
        gateway can inspect what would be delivered back to Web IM.
    """

    name = "web_relay"

    def __init__(self) -> None:
        self._on_inbound: InboundHandler | None = None
        self.sent: list[OutboundMessage] = []
        self._seen_idempotency_keys: deque[str] = deque()

    def start(self, on_inbound: InboundHandler) -> None:
        """Store the gateway inbound callback used for relay pushes."""

        self._on_inbound = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        """Record normalized outbound traffic destined for Web IM."""

        self.sent.append(outbound)

    def stop(self) -> None:
        """Detach the current inbound callback."""

        self._on_inbound = None

    def accept_relay(self, payload: Mapping[str, object]) -> InboundMessage:
        """Convert one ``relay.message`` payload into an inbound gateway message.

        Raises:
            RuntimeError: When the adapter has not been started yet.
            ValueError: When required relay fields are missing or malformed.
        """

        callback = self._on_inbound
        if callback is None:
            raise RuntimeError("web relay adapter is not started")
        envelope = _parse_relay_payload(payload)
        if envelope.idempotency_key in self._seen_idempotency_keys:
            return _build_inbound(envelope, payload)
        self._seen_idempotency_keys.append(envelope.idempotency_key)
        if len(self._seen_idempotency_keys) > _SEEN_KEYS_MAX:
            self._seen_idempotency_keys.popleft()
        inbound = _build_inbound(envelope, payload)
        callback(inbound)
        return inbound


def _build_inbound(envelope: RelayEnvelope, payload: Mapping[str, object]) -> InboundMessage:
    conversation_type = envelope.metadata.get("conversation_type")
    message_id = _optional_text(payload.get("message_id"))
    if message_id is None:
        message = payload.get("message")
        if isinstance(message, Mapping):
            message_id = _optional_text(message.get("id"))
    return InboundMessage(
        channel_name="web_relay",
        text=envelope.content,
        external_user_id=envelope.sender_user_id,
        external_chat_id=envelope.conversation_id,
        is_group=conversation_type == "group",
        agent_id=envelope.agent_id,
        thread_id=_optional_text(envelope.metadata.get("thread_id")),
        metadata={
            "relay_task_id": envelope.relay_task_id,
            "idempotency_key": envelope.idempotency_key,
            "message_id": message_id,
            **dict(envelope.metadata),
        },
    )


def _parse_relay_payload(payload: Mapping[str, object]) -> RelayEnvelope:
    relay_task_id = _require_text(payload.get("relay_task_id"), field_name="relay_task_id")
    idempotency_key = _require_text(payload.get("idempotency_key"), field_name="idempotency_key")
    message = payload.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("message must be an object")
    sender_user_id = _require_text(message.get("sender_user_id"), field_name="message.sender_user_id")
    conversation_id = _require_text(message.get("conversation_id"), field_name="message.conversation_id")
    content = _require_text(message.get("content"), field_name="message.content")
    metadata = payload.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be an object")
    return RelayEnvelope(
        relay_task_id=relay_task_id,
        idempotency_key=idempotency_key,
        sender_user_id=sender_user_id,
        conversation_id=conversation_id,
        content=content,
        agent_id=_optional_text(payload.get("agent_id")),
        metadata=dict(metadata),
    )


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text fields must be strings when provided")
    stripped = value.strip()
    return stripped or None
