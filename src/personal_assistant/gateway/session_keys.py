"""Session-key generation and local kernel-session binding storage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

from personal_assistant.channels.base import InboundMessage, ReplyContext

if TYPE_CHECKING:
    from personal_assistant.client.kernel_api_client import KernelApiClient


@dataclass(frozen=True, slots=True)
class SessionBinding:
    """Persist the kernel session id and reply target for one gateway session key.

    Args:
        session_key: Stable gateway-local session key.
        kernel_session_id: Kernel session id created for this binding.
        reply_context: Original reply target used for outbound routing.
    """

    session_key: str
    kernel_session_id: str
    reply_context: ReplyContext


class SessionBindingStore:
    """Store gateway session bindings in local process memory for v1 pipeline flows."""

    def __init__(self) -> None:
        self._bindings: dict[str, SessionBinding] = {}

    def get(self, session_key: str) -> SessionBinding | None:
        """Return one binding by session key."""

        return self._bindings.get(session_key)

    def bind(self, *, session_key: str, kernel_session_id: str, reply_context: ReplyContext) -> SessionBinding:
        """Create or replace the binding for one session key."""

        binding = SessionBinding(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=reply_context,
        )
        self._bindings[session_key] = binding
        return binding

    def find_by_kernel_session_id(self, kernel_session_id: str) -> SessionBinding | None:
        """Return the first binding whose kernel_session_id matches, or None.

        Used by background event subscribers to reverse-resolve conversation routing
        context (target_chat_id) from a kernel session without knowing the session key.

        Args:
            kernel_session_id: Kernel session identifier to search for.

        Returns:
            First matching binding, or ``None`` when no binding is found.
        """
        for binding in self._bindings.values():
            if binding.kernel_session_id == kernel_session_id:
                return binding
        return None

    def drop_agent(self, agent_id: str) -> None:
        """Remove all session bindings that belong to one routed agent id."""

        suffix = f":{agent_id}"
        for session_key in tuple(self._bindings):
            if session_key.endswith(suffix):
                self._bindings.pop(session_key, None)


session_binding_store = SessionBindingStore()

# ---------------------------------------------------------------------------
# SQLite-backed persistent binding store (NodeGateway-SPEC §4.2)
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_bindings (
    session_key       TEXT PRIMARY KEY,
    kernel_session_id TEXT NOT NULL,
    reply_context_json TEXT NOT NULL,
    updated_at        TEXT NOT NULL
)
"""


class PersistentSessionBindingStore:
    """Persist gateway session bindings in SQLite for crash-safe recovery.

    Stores one row per gateway session key so that after a gateway restart the
    original kernel session id can be looked up and the conversation context
    continues without interruption.  Implements the same ``bind``/``get``/
    ``drop_agent`` interface as :class:`SessionBindingStore`.

    The optional ``kernel_client`` injected via :meth:`set_kernel_client`
    enables live validation: when ``get`` finds a stored binding it calls
    ``GET /v1/sessions/{id}`` to confirm the kernel session still exists.  If
    the session has been evicted (404 / any RuntimeError) the stale record is
    deleted and ``None`` is returned so the caller recreates a fresh session.

    Args:
        db_path: Absolute path for the SQLite database file.  Parent directories
            are created automatically.  Defaults to
            ``~/.nano-assistant/session_bindings.sqlite3`` when omitted.

    Notes:
        Thread safety: SQLite ``check_same_thread=False`` is used; the WAL
        journal mode is enabled so concurrent readers do not block writers.
        All writes use explicit ``BEGIN IMMEDIATE`` semantics via Python's
        ``isolation_level=None`` (auto-commit) plus explicit transactions.
    """

    def __init__(self, *, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path("~/.nano-assistant/session_bindings.sqlite3").expanduser()
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        # WAL mode reduces write contention; safe for single-process gateway.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()
        self._kernel_client: KernelApiClient | None = None

    def set_kernel_client(self, client: KernelApiClient) -> None:
        """Inject the kernel HTTP client used for live session validation.

        Args:
            client: Initialized kernel API client.  Pass ``None`` to disable
                validation (useful in tests or when kernel has not started yet).

        Side Effects:
            Subsequent ``get`` calls will invoke ``GET /v1/sessions/{id}``
            before returning the binding.
        """

        self._kernel_client = client

    def get(self, session_key: str) -> SessionBinding | None:
        """Return one binding by session key, optionally validating with kernel.

        When a ``kernel_client`` is set, verifies the stored ``kernel_session_id``
        still exists via ``GET /v1/sessions/{id}``.  On any failure (404, network
        error, etc.) the stale record is silently deleted and ``None`` is returned
        so the caller can recreate a fresh session.

        Args:
            session_key: Gateway-local session key generated by
                :func:`build_session_key`.

        Returns:
            The stored :class:`SessionBinding`, or ``None`` when the key is
            unknown, the stored binding is stale, or kernel validation fails.
        """

        row = self._conn.execute(
            "SELECT kernel_session_id, reply_context_json FROM session_bindings WHERE session_key = ?",
            (session_key,),
        ).fetchone()
        if row is None:
            return None

        kernel_session_id: str = row[0]
        reply_context = _deserialize_reply_context(row[1])

        # Validate that the kernel session still exists when a client is available.
        if self._kernel_client is not None:
            try:
                self._kernel_client.get_session(session_id=kernel_session_id)
            except Exception:  # noqa: BLE001 — any error means session is gone
                # Stale record: delete and signal caller to recreate.
                self._conn.execute(
                    "DELETE FROM session_bindings WHERE session_key = ?",
                    (session_key,),
                )
                self._conn.commit()
                return None

        return SessionBinding(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=reply_context,
        )

    def bind(
        self,
        *,
        session_key: str,
        kernel_session_id: str,
        reply_context: ReplyContext,
    ) -> SessionBinding:
        """Upsert a session binding into the SQLite store.

        Creates a new row or replaces the existing row for ``session_key`` with
        the new ``kernel_session_id`` and ``reply_context``.

        Args:
            session_key: Gateway-local session key.
            kernel_session_id: Kernel session id to persist.
            reply_context: Original outbound reply target to persist.

        Returns:
            The newly persisted :class:`SessionBinding`.

        Side Effects:
            Writes one row to the ``session_bindings`` SQLite table.
        """

        import datetime

        rc_json = _serialize_reply_context(reply_context)
        updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO session_bindings (session_key, kernel_session_id, reply_context_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                kernel_session_id = excluded.kernel_session_id,
                reply_context_json = excluded.reply_context_json,
                updated_at = excluded.updated_at
            """,
            (session_key, kernel_session_id, rc_json, updated_at),
        )
        self._conn.commit()
        return SessionBinding(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=reply_context,
        )

    def drop_agent(self, agent_id: str) -> None:
        """Remove all bindings whose session_key ends with ``:{agent_id}``.

        Args:
            agent_id: Routed agent id whose bindings should be dropped.

        Side Effects:
            Deletes matching rows from the SQLite table.
        """

        suffix = f":{agent_id}"
        self._conn.execute(
            "DELETE FROM session_bindings WHERE session_key LIKE ?",
            (f"%{suffix}",),
        )
        self._conn.commit()


def _serialize_reply_context(rc: ReplyContext) -> str:
    """Encode a ReplyContext to a JSON string for SQLite storage."""

    payload: dict[str, Any] = {
        "channel_name": rc.channel_name,
        "target_chat_id": rc.target_chat_id,
        "thread_id": rc.thread_id,
        "metadata": dict(rc.metadata),
    }
    return json.dumps(payload)


def _deserialize_reply_context(raw: str) -> ReplyContext:
    """Decode a JSON string back into a ReplyContext."""

    payload = json.loads(raw)
    return ReplyContext(
        channel_name=payload["channel_name"],
        target_chat_id=payload["target_chat_id"],
        thread_id=payload.get("thread_id"),
        metadata=payload.get("metadata", {}),
    )


def build_session_key(message: InboundMessage, *, agent_id: str) -> str:
    """Build the canonical gateway session key for one inbound message.

    Args:
        message: Normalized inbound message produced by a channel adapter.
        agent_id: Routed agent id chosen in pipeline step 1.

    Returns:
        Conversation-scoped key ``{channel}:{external_chat_id}:{agent_id}`` for both
        group and direct chats so already-started direct conversations keep their
        original kernel session after later agent config updates.
    """

    return f"{message.channel_name}:{message.external_chat_id}:{agent_id}"


def build_reply_context(message: InboundMessage) -> ReplyContext:
    """Capture the outbound reply target from one inbound message."""

    return ReplyContext(
        channel_name=message.channel_name,
        target_chat_id=message.external_chat_id,
        thread_id=message.thread_id,
        metadata=dict(message.metadata),
    )


def build_conversation_session_key(*, channel_name: str, conversation_id: str, agent_id: str) -> str:
    """Build one gateway session key from a canonical conversation id."""

    return f"{channel_name}:{conversation_id}:{agent_id}"


def build_conversation_reply_context(*, channel_name: str, conversation_id: str) -> ReplyContext:
    """Build a reply context that routes back to one canonical IM conversation."""

    return ReplyContext(
        channel_name=channel_name,
        target_chat_id=conversation_id,
        thread_id=None,
        metadata={"conversation_id": conversation_id},
    )


def bind_conversation_session(
    *,
    store: SessionBindingStore,
    channel_name: str,
    conversation_id: str,
    agent_id: str,
    kernel_session_id: str,
) -> SessionBinding:
    """Bind one canonical conversation id to an existing kernel session."""

    return store.bind(
        session_key=build_conversation_session_key(
            channel_name=channel_name,
            conversation_id=conversation_id,
            agent_id=agent_id,
        ),
        kernel_session_id=kernel_session_id,
        reply_context=build_conversation_reply_context(
            channel_name=channel_name,
            conversation_id=conversation_id,
        ),
    )
