"""Session-key generation and local kernel-session binding storage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from personal_assistant.channels.base import InboundMessage, ReplyContext

# KernelApiClient removed in M3 (refactor-387).


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

    def bind(
        self, *, session_key: str, kernel_session_id: str, reply_context: ReplyContext
    ) -> SessionBinding:
        """Create or replace the binding for one session key."""

        binding = SessionBinding(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=reply_context,
        )
        self._bindings[session_key] = binding
        return binding

    def find_by_kernel_session_id(
        self, kernel_session_id: str
    ) -> SessionBinding | None:
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
# SQLite-backed persistent binding store (see docs/specs/gateway/spec.md)
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_bindings (
    session_key        TEXT PRIMARY KEY,
    kernel_session_id  TEXT NOT NULL,
    reply_context_json TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT ''
)
"""

_MIGRATE_ADD_CREATED_AT_SQL = """
ALTER TABLE session_bindings ADD COLUMN created_at TEXT NOT NULL DEFAULT ''
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
        # feat-394 migration: add created_at column if absent (existing databases).
        # created_at records when the binding was first established (proxy for the
        # direct chat's creation time, used by find_direct_by_agent to select the
        # oldest / canonical conversation consistent with IM's sorted-by-created_at policy).
        existing_cols = {
            row[1]
            for row in self._conn.execute(
                "PRAGMA table_info(session_bindings)"
            ).fetchall()
        }
        if "created_at" not in existing_cols:
            self._conn.execute(_MIGRATE_ADD_CREATED_AT_SQL)
        self._conn.commit()
        self._kernel_client: Any | None = None  # KernelApiClient removed in M3

    def set_kernel_client(self, client: Any) -> None:
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
        """Return one binding by session key.

        Args:
            session_key: Gateway-local session key generated by
                :func:`build_session_key`.

        Returns:
            The stored :class:`SessionBinding`, or ``None`` when the key is unknown.

        Notes:
            Liveness/workspace validation of the kernel session is **not** done
            here.  The stateless kernel locates a session JSONL by its
            ``workspace_root``, which this binding row does not carry.  The
            authoritative check lives one layer up in
            ``InboundPipeline._ensure_binding`` -> ``_binding_matches_workspace_root``,
            which already knows the agent's ``workspace_root`` and refreshes a
            stale binding by creating a fresh kernel session.  Probing here
            (without ``workspace_root``) would always 404 against the stateless
            kernel and wrongly evict every binding after a gateway restart.
        """

        row = self._conn.execute(
            "SELECT kernel_session_id, reply_context_json FROM session_bindings WHERE session_key = ?",
            (session_key,),
        ).fetchone()
        if row is None:
            return None

        kernel_session_id: str = row[0]
        reply_context = _deserialize_reply_context(row[1])
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
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # feat-394: created_at is written once on first INSERT and never overwritten.
        # It acts as a proxy for the direct-chat conversation creation time so that
        # find_direct_by_agent can select the canonical (oldest) binding consistent
        # with IM's _find_canonical_direct_conversation (sorted by created_at[0]).
        self._conn.execute(
            """
            INSERT INTO session_bindings
                (session_key, kernel_session_id, reply_context_json, updated_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                kernel_session_id  = excluded.kernel_session_id,
                reply_context_json = excluded.reply_context_json,
                updated_at         = excluded.updated_at
            """,
            (session_key, kernel_session_id, rc_json, now_iso, now_iso),
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

    def find_by_kernel_session_id(
        self, kernel_session_id: str
    ) -> SessionBinding | None:
        """Return the first binding whose kernel_session_id matches, or None.

        feat-394-M4 R2-1 fix: mirrors the in-memory SessionBindingStore contract
        so that callers (e.g. main.py:_callback for self_evolution_review events
        and cron tool chain lookups) work correctly with the production SQLite
        store used at runtime, not just the in-memory test double.

        Args:
            kernel_session_id: Kernel session identifier to search for.

        Returns:
            First matching :class:`SessionBinding`, or ``None`` when no row
            is found with the given kernel_session_id.
        """

        row = self._conn.execute(
            """
            SELECT session_key, kernel_session_id, reply_context_json
            FROM session_bindings
            WHERE kernel_session_id = ?
            LIMIT 1
            """,
            (kernel_session_id,),
        ).fetchone()
        if row is None:
            return None
        session_key_val: str = row[0]
        kernel_session_id_val: str = row[1]
        reply_context = _deserialize_reply_context(row[2])
        return SessionBinding(
            session_key=session_key_val,
            kernel_session_id=kernel_session_id_val,
            reply_context=reply_context,
        )

    def find_direct_by_agent(
        self, *, channel_name: str, agent_id: str
    ) -> SessionBinding | None:
        """Return the oldest direct-chat binding for one agent on one channel.

        Searches for all session keys matching ``{channel_name}:%:{agent_id}``
        (same LIKE pattern as :meth:`drop_agent`) and returns the binding with
        the smallest ``updated_at`` timestamp — the oldest (canonical) direct chat,
        consistent with IM's ``_find_canonical_direct_conversation`` which takes
        ``sorted(key=created_at)[0]``.

        feat-394 decision 3: called by :class:`PollingHeartbeatRunner` **before**
        submitting each heartbeat run, so the scheduler always has the most recent
        canonical session from a gateway-only read — no IM HTTP call needed, no
        dependency on a prior turn_start ack.

        Args:
            channel_name: Gateway channel name (e.g. ``"web_relay"``).
            agent_id: Agent whose direct-chat binding to look up.

        Returns:
            The oldest :class:`SessionBinding` for this agent on this channel,
            or ``None`` when no binding exists yet (first heartbeat before any
            direct chat has taken place).

        Notes:
            ``created_at`` is the sort key.  It is written once when the binding is
            first inserted (see :meth:`bind`) and never overwritten on subsequent
            upserts — it records the moment the direct chat's kernel session was
            first established, which serves as a reliable proxy for the IM
            conversation's own ``created_at``.  Sorting by ``created_at ASC``
            therefore produces the same "oldest conversation" selection as IM's
            ``_find_canonical_direct_conversation(sorted(key=created_at)[0])``,
            keeping the heartbeat run session and the IM delivery target consistent.
            When multiple direct chats exist both sides use the oldest-by-creation
            heuristic, so run context and delivery target always refer to the same
            conversation.
        """

        # Session key format: ``{channel_name}:{conversation_id}:{agent_id}``
        # LIKE pattern mirrors drop_agent's ``%:{agent_id}`` suffix but further
        # constrains to the correct channel prefix.
        pattern = f"{channel_name}:%:{agent_id}"
        # feat-394: ORDER BY created_at ASC (not updated_at) so the result matches
        # IM's _find_canonical_direct_conversation(sorted(key=created_at)[0]).
        # created_at is written once at first INSERT and never updated on upsert,
        # so it reliably reflects when the binding (and therefore the direct chat)
        # was first established — independent of subsequent message activity.
        row = self._conn.execute(
            """
            SELECT session_key, kernel_session_id, reply_context_json
            FROM session_bindings
            WHERE session_key LIKE ?
            ORDER BY created_at ASC, rowid ASC
            LIMIT 1
            """,
            (pattern,),
        ).fetchone()
        if row is None:
            return None
        # Use positional indices: PersistentSessionBindingStore._conn has no row_factory.
        session_key_val: str = row[0]
        kernel_session_id_val: str = row[1]
        reply_context_json_val: str = row[2]
        reply_context = _deserialize_reply_context(reply_context_json_val)
        return SessionBinding(
            session_key=session_key_val,
            kernel_session_id=kernel_session_id_val,
            reply_context=reply_context,
        )


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
        External-channel messages use ``metadata.external_source`` and
        ``metadata.external_chat_id`` so Feishu and IM shadow entries share the
        same kernel session. Ordinary channels keep the legacy
        ``{channel}:{external_chat_id}:{agent_id}`` key.
    """

    metadata = dict(message.metadata)
    external_source = metadata.get("external_source")
    external_chat_id = metadata.get("external_chat_id")
    if (
        isinstance(external_source, str)
        and external_source.strip()
        and isinstance(external_chat_id, str)
        and external_chat_id.strip()
    ):
        return build_external_session_key(
            external_source=external_source.strip(),
            external_chat_id=external_chat_id.strip(),
            agent_id=agent_id,
        )
    return f"{message.channel_name}:{message.external_chat_id}:{agent_id}"


def build_external_session_key(
    *, external_source: str, external_chat_id: str, agent_id: str
) -> str:
    """Build a gateway key from a channel-neutral external conversation identity."""

    return f"{external_source}:{external_chat_id}:{agent_id}"


def build_reply_context(message: InboundMessage) -> ReplyContext:
    """Capture the outbound reply target from one inbound message."""

    return ReplyContext(
        channel_name=message.channel_name,
        target_chat_id=message.external_chat_id,
        thread_id=message.thread_id,
        metadata=dict(message.metadata),
    )


def build_conversation_session_key(
    *, channel_name: str, conversation_id: str, agent_id: str
) -> str:
    """Build one gateway session key from a canonical conversation id."""

    return f"{channel_name}:{conversation_id}:{agent_id}"


def build_conversation_reply_context(
    *, channel_name: str, conversation_id: str
) -> ReplyContext:
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
