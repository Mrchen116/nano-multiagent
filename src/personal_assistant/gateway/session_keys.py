"""Session-key generation and local kernel-session binding storage."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.gateway.runtime_protocol import strip_runtime_protocol_metadata
from personal_assistant.gateway.runtime_protocol import external_identity_from_message

# KernelApiClient removed in M3 (refactor-387).


@dataclass(frozen=True, slots=True)
class BoundaryIntent:
    """Represent one actual-applied configuration boundary awaiting IM acknowledgment.

    The Gateway owns this durable fact because only admission knows when a retained
    Kernel session crossed a runtime boundary. The IM-facing payload is deliberately
    complete enough for a retry to be wire-identical.
    """

    boundary_id: str
    node_id: str
    conversation_id: str
    agent_id: str
    before_message_id: str
    runtime_fingerprint: str
    fingerprint_schema: str
    profile_version: int | None
    applied_at: str


@dataclass(frozen=True, slots=True)
class PendingBoundaryIntent:
    """Represent an applied runtime change awaiting a shadow saga anchor.

    External ingress may execute while IM is unavailable.  Its runtime replacement is
    still durable before submit, but it cannot enter the network outbox until the
    saga has confirmed the user-message anchor.
    """

    boundary_id: str
    node_id: str
    agent_id: str
    runtime_fingerprint: str
    fingerprint_schema: str
    profile_version: int | None
    applied_at: str
    shadow_saga_id: str


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
    applied_runtime_fingerprint: str | None = None
    applied_fingerprint_schema: str | None = None
    applied_profile_version: int | None = None


@dataclass(frozen=True, slots=True)
class ControlOperation:
    """Persist the completed result of one replayable Gateway control command."""

    session_key: str
    operation_id: str
    kind: str
    status: str
    kernel_session_id: str
    reply_text: str


@dataclass(frozen=True, slots=True)
class PendingExternalControlDelivery:
    """Represent a committed external control outcome awaiting channel handoff.

    The binding store owns this small handoff record so a process loss after the
    control outcome commits, but before the shadow saga receives its output, cannot
    silently lose the user's confirmation.
    """

    outcome: ControlOperation
    shadow_saga_id: str
    state: str


class SessionBindingStore:
    """Store gateway session bindings in local process memory for v1 pipeline flows."""

    def __init__(self) -> None:
        self._bindings: dict[str, SessionBinding] = {}
        self._boundaries: dict[str, BoundaryIntent] = {}
        self._quarantined_boundaries: dict[str, BoundaryIntent] = {}
        self._boundary_retry_attempts: dict[str, int] = {}
        self._boundary_retry_not_before: dict[str, float] = {}
        self._control_operations: dict[tuple[str, str, str], ControlOperation] = {}
        self._pending_external_controls: dict[
            tuple[str, str, str], PendingExternalControlDelivery
        ] = {}
        self._superseded_runs: dict[str, str] = {}

    def get(self, session_key: str) -> SessionBinding | None:
        """Return one binding by session key."""

        return self._bindings.get(session_key)

    def bind(
        self,
        *,
        session_key: str,
        kernel_session_id: str,
        reply_context: ReplyContext,
        applied_runtime_fingerprint: str | None = None,
        applied_fingerprint_schema: str | None = None,
        applied_profile_version: int | None = None,
    ) -> SessionBinding:
        """Create or refresh one binding without losing known applied identity."""

        previous = self._bindings.get(session_key)
        binding = SessionBinding(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=reply_context,
            applied_runtime_fingerprint=(
                applied_runtime_fingerprint
                if applied_runtime_fingerprint is not None
                else previous.applied_runtime_fingerprint
                if previous
                else None
            ),
            applied_fingerprint_schema=(
                applied_fingerprint_schema
                if applied_fingerprint_schema is not None
                else previous.applied_fingerprint_schema
                if previous
                else None
            ),
            applied_profile_version=(
                applied_profile_version
                if applied_profile_version is not None
                else previous.applied_profile_version
                if previous
                else None
            ),
        )
        self._bindings[session_key] = binding
        return binding

    def apply_runtime(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
    ) -> SessionBinding:
        """Persist one Kernel-confirmed applied runtime for a stable binding."""

        return self.bind(
            session_key=binding.session_key,
            kernel_session_id=binding.kernel_session_id,
            reply_context=binding.reply_context,
            applied_runtime_fingerprint=runtime_fingerprint,
            applied_fingerprint_schema=fingerprint_schema,
            applied_profile_version=profile_version,
        )

    def get_control_operation(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> ControlOperation | None:
        """Return an already completed replayable control outcome."""

        return self._control_operations.get((session_key, operation_id, kind))

    def publish_reset(
        self,
        *,
        binding: SessionBinding,
        operation_id: str | None,
        superseded_run_id: str | None,
        reply_text: str,
        external_saga_id: str | None = None,
    ) -> ControlOperation | None:
        """Publish a replacement binding and its reset outcome as one store action."""

        if operation_id is not None:
            existing = self.get_control_operation(
                session_key=binding.session_key, operation_id=operation_id, kind="new"
            )
            if existing is not None:
                return existing
        published = self.bind(
            session_key=binding.session_key,
            kernel_session_id=binding.kernel_session_id,
            reply_context=binding.reply_context,
            applied_runtime_fingerprint=binding.applied_runtime_fingerprint,
            applied_fingerprint_schema=binding.applied_fingerprint_schema,
            applied_profile_version=binding.applied_profile_version,
        )
        if superseded_run_id:
            self._superseded_runs[superseded_run_id] = published.kernel_session_id
        if operation_id is None:
            return None
        outcome = ControlOperation(
            session_key=published.session_key,
            operation_id=operation_id,
            kind="new",
            status="completed",
            kernel_session_id=published.kernel_session_id,
            reply_text=reply_text,
        )
        self._control_operations.setdefault(
            (published.session_key, operation_id, "new"), outcome
        )
        committed = self._control_operations[
            (published.session_key, operation_id, "new")
        ]
        self._record_external_control_delivery(
            committed, shadow_saga_id=external_saga_id
        )
        return committed

    def record_control_operation(
        self,
        outcome: ControlOperation,
        *,
        external_saga_id: str | None = None,
    ) -> ControlOperation:
        """Persist a non-reset control outcome for later replay."""

        key = (outcome.session_key, outcome.operation_id, outcome.kind)
        self._control_operations.setdefault(key, outcome)
        committed = self._control_operations[key]
        self._record_external_control_delivery(
            committed, shadow_saga_id=external_saga_id
        )
        return committed

    def pending_external_controls(self) -> tuple[PendingExternalControlDelivery, ...]:
        """Return committed external controls not yet handed to the provider."""

        return tuple(
            delivery
            for delivery in self._pending_external_controls.values()
            if delivery.state != "outbound_handed_off"
        )

    def mark_external_control_handed_off(
        self,
        *,
        session_key: str,
        operation_id: str,
        kind: str,
    ) -> None:
        """Mark an external confirmation handed to its original channel."""

        key = (session_key, operation_id, kind)
        delivery = self._pending_external_controls.get(key)
        if delivery is not None:
            self._pending_external_controls[key] = PendingExternalControlDelivery(
                outcome=delivery.outcome,
                shadow_saga_id=delivery.shadow_saga_id,
                state="outbound_handed_off",
            )

    def mark_external_control_materialized(
        self,
        *,
        session_key: str,
        operation_id: str,
        kind: str,
    ) -> None:
        """Record that the saga output exists before provider handoff."""

        key = (session_key, operation_id, kind)
        delivery = self._pending_external_controls.get(key)
        if delivery is not None and delivery.state == "pending_materialization":
            self._pending_external_controls[key] = PendingExternalControlDelivery(
                outcome=delivery.outcome,
                shadow_saga_id=delivery.shadow_saga_id,
                state="materialized",
            )

    def _record_external_control_delivery(
        self, outcome: ControlOperation, *, shadow_saga_id: str | None
    ) -> None:
        if not shadow_saga_id:
            return
        key = (outcome.session_key, outcome.operation_id, outcome.kind)
        self._pending_external_controls.setdefault(
            key,
            PendingExternalControlDelivery(
                outcome=outcome,
                shadow_saga_id=shadow_saga_id,
                state="pending_materialization",
            ),
        )

    def is_run_superseded(self, run_id: str) -> bool:
        """Return whether reset made a run permanently invisible."""

        return run_id in self._superseded_runs

    def apply_runtime_with_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: BoundaryIntent,
    ) -> SessionBinding:
        """Persist the in-memory counterpart of one applied boundary fact."""

        if (
            boundary.runtime_fingerprint != runtime_fingerprint
            or boundary.fingerprint_schema != fingerprint_schema
            or boundary.profile_version != profile_version
        ):
            raise ValueError("boundary must describe the applied runtime")
        updated = self.apply_runtime(
            binding,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
        )
        self._boundaries.setdefault(boundary.boundary_id, boundary)
        return updated

    def apply_runtime_with_pending_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: PendingBoundaryIntent,
    ) -> SessionBinding:
        """Persist an external runtime replacement before its IM anchor exists."""

        if (
            boundary.runtime_fingerprint != runtime_fingerprint
            or boundary.fingerprint_schema != fingerprint_schema
            or boundary.profile_version != profile_version
        ):
            raise ValueError("pending boundary must describe the applied runtime")
        return self.apply_runtime(
            binding,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
        )

    def promote_pending_boundary(
        self, *, shadow_saga_id: str, shadow_ref: object
    ) -> BoundaryIntent | None:
        """Return None because the in-memory store has no cross-process recovery path."""

        del shadow_saga_id, shadow_ref
        return None

    def pending_boundaries(self) -> tuple[BoundaryIntent, ...]:
        """Return delivery-eligible in-memory boundary intents."""

        return tuple(self._boundaries.values())

    def quarantined_boundaries(self) -> tuple[BoundaryIntent, ...]:
        """Return in-memory boundary intents rejected by IM."""

        return tuple(self._quarantined_boundaries.values())

    def acknowledge_boundary(self, boundary_id: str) -> None:
        """Remove one acknowledged in-memory boundary intent."""

        self._boundaries.pop(boundary_id, None)
        self._boundary_retry_attempts.pop(boundary_id, None)
        self._boundary_retry_not_before.pop(boundary_id, None)

    def record_boundary_error(self, boundary_id: str, *, reason: str) -> None:
        """Preserve one rejected in-memory intent for diagnosis."""

        del reason
        boundary = self._boundaries.pop(boundary_id, None)
        self._boundary_retry_attempts.pop(boundary_id, None)
        self._boundary_retry_not_before.pop(boundary_id, None)
        if boundary is not None:
            self._quarantined_boundaries[boundary_id] = boundary

    def delivery_ready_boundaries(self) -> tuple[BoundaryIntent, ...]:
        """Return in-memory intents whose retry deadline has elapsed."""

        now = time.time()
        return tuple(
            intent
            for boundary_id, intent in self._boundaries.items()
            if self._boundary_retry_not_before.get(boundary_id, 0.0) <= now
        )

    def defer_boundary_retry(
        self,
        boundary_id: str,
        *,
        reason: str,
        retry_initial_seconds: float,
        retry_max_seconds: float,
    ) -> None:
        """Apply the same bounded retry semantics used by the durable store."""

        del reason
        if boundary_id not in self._boundaries:
            return
        attempts = self._boundary_retry_attempts.get(boundary_id, 0) + 1
        delay = min(retry_initial_seconds * (2 ** (attempts - 1)), retry_max_seconds)
        self._boundary_retry_attempts[boundary_id] = attempts
        self._boundary_retry_not_before[boundary_id] = time.time() + delay

    def next_boundary_retry_delay(self) -> float | None:
        """Return seconds until the next delayed in-memory intent becomes ready."""

        if not self._boundary_retry_not_before:
            return None
        return max(0.0, min(self._boundary_retry_not_before.values()) - time.time())

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

    def drop(self, session_key: str) -> None:
        """Remove one binding by its exact Gateway session key."""

        self._bindings.pop(session_key, None)

    def bindings_for_agent(self, agent_id: str) -> tuple[SessionBinding, ...]:
        """Return a stable snapshot of all bindings routed to one Agent."""

        suffix = f":{agent_id}"
        return tuple(
            binding for key, binding in self._bindings.items() if key.endswith(suffix)
        )

    def find_direct_by_agent(
        self, *, channel_name: str, agent_id: str
    ) -> SessionBinding | None:
        """Return the oldest in-memory direct-chat binding for one Agent."""

        prefix = f"{channel_name}:"
        suffix = f":{agent_id}"
        return next(
            (
                binding
                for key, binding in self._bindings.items()
                if key.startswith(prefix) and key.endswith(suffix)
            ),
            None,
        )


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
    created_at         TEXT NOT NULL DEFAULT '',
    applied_runtime_fingerprint TEXT,
    applied_fingerprint_schema  TEXT,
    applied_profile_version     INTEGER
)
"""

_MIGRATE_ADD_CREATED_AT_SQL = """
ALTER TABLE session_bindings ADD COLUMN created_at TEXT NOT NULL DEFAULT ''
"""
_MIGRATE_ADD_APPLIED_RUNTIME_FINGERPRINT_SQL = """
ALTER TABLE session_bindings ADD COLUMN applied_runtime_fingerprint TEXT
"""
_MIGRATE_ADD_APPLIED_FINGERPRINT_SCHEMA_SQL = """
ALTER TABLE session_bindings ADD COLUMN applied_fingerprint_schema TEXT
"""
_MIGRATE_ADD_APPLIED_PROFILE_VERSION_SQL = """
ALTER TABLE session_bindings ADD COLUMN applied_profile_version INTEGER
"""
_MIGRATE_ADD_BOUNDARY_RETRY_ATTEMPTS_SQL = """
ALTER TABLE agent_config_boundary_outbox
ADD COLUMN retry_attempts INTEGER NOT NULL DEFAULT 0
"""
_MIGRATE_ADD_BOUNDARY_RETRY_NOT_BEFORE_SQL = """
ALTER TABLE agent_config_boundary_outbox ADD COLUMN retry_not_before REAL
"""

_CREATE_BOUNDARY_OUTBOX_SQL = """
CREATE TABLE IF NOT EXISTS agent_config_boundary_outbox (
    boundary_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    before_message_id TEXT NOT NULL,
    runtime_fingerprint TEXT NOT NULL,
    fingerprint_schema TEXT NOT NULL,
    profile_version INTEGER,
    applied_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    error_reason TEXT,
    retry_attempts INTEGER NOT NULL DEFAULT 0,
    retry_not_before REAL
)
"""

_CREATE_PENDING_BOUNDARY_SQL = """
CREATE TABLE IF NOT EXISTS agent_config_pending_shadow_boundaries (
    boundary_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    runtime_fingerprint TEXT NOT NULL,
    fingerprint_schema TEXT NOT NULL,
    profile_version INTEGER,
    applied_at TEXT NOT NULL,
    shadow_saga_id TEXT NOT NULL UNIQUE
)
"""

_CREATE_CONTROL_OPERATIONS_SQL = """
CREATE TABLE IF NOT EXISTS gateway_control_operations (
    session_key TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    kernel_session_id TEXT NOT NULL,
    reply_text TEXT NOT NULL,
    PRIMARY KEY (session_key, operation_id, kind)
)
"""

_CREATE_SUPERSEDED_RUNS_SQL = """
CREATE TABLE IF NOT EXISTS gateway_superseded_runs (
    run_id TEXT PRIMARY KEY,
    session_key TEXT NOT NULL,
    replacement_kernel_session_id TEXT NOT NULL
)
"""

_CREATE_PENDING_EXTERNAL_CONTROL_DELIVERIES_SQL = """
CREATE TABLE IF NOT EXISTS gateway_pending_external_control_deliveries (
    session_key TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    shadow_saga_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending_materialization',
    PRIMARY KEY (session_key, operation_id, kind)
)
"""

_SQLITE_LIKE_ESCAPE = "!"


def _literal_like_pattern(value: str) -> str:
    """Escape one literal value embedded in a SQLite LIKE pattern."""

    return (
        value.replace(_SQLITE_LIKE_ESCAPE, _SQLITE_LIKE_ESCAPE * 2)
        .replace("%", f"{_SQLITE_LIKE_ESCAPE}%")
        .replace("_", f"{_SQLITE_LIKE_ESCAPE}_")
    )


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
        self._conn.execute(_CREATE_BOUNDARY_OUTBOX_SQL)
        self._conn.execute(_CREATE_PENDING_BOUNDARY_SQL)
        self._conn.execute(_CREATE_CONTROL_OPERATIONS_SQL)
        self._conn.execute(_CREATE_SUPERSEDED_RUNS_SQL)
        self._conn.execute(_CREATE_PENDING_EXTERNAL_CONTROL_DELIVERIES_SQL)
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
        if "applied_runtime_fingerprint" not in existing_cols:
            self._conn.execute(_MIGRATE_ADD_APPLIED_RUNTIME_FINGERPRINT_SQL)
        if "applied_fingerprint_schema" not in existing_cols:
            self._conn.execute(_MIGRATE_ADD_APPLIED_FINGERPRINT_SCHEMA_SQL)
        if "applied_profile_version" not in existing_cols:
            self._conn.execute(_MIGRATE_ADD_APPLIED_PROFILE_VERSION_SQL)
        boundary_cols = {
            row[1]
            for row in self._conn.execute(
                "PRAGMA table_info(agent_config_boundary_outbox)"
            ).fetchall()
        }
        if "retry_attempts" not in boundary_cols:
            self._conn.execute(_MIGRATE_ADD_BOUNDARY_RETRY_ATTEMPTS_SQL)
        if "retry_not_before" not in boundary_cols:
            self._conn.execute(_MIGRATE_ADD_BOUNDARY_RETRY_NOT_BEFORE_SQL)
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
            authoritative check lives in :class:`GatewaySessionBinder`, which already
            knows the agent's ``workspace_root`` and refreshes a stale binding by
            creating a fresh kernel session.  Probing here
            (without ``workspace_root``) would always 404 against the stateless
            kernel and wrongly evict every binding after a gateway restart.
        """

        row = self._conn.execute(
            """
            SELECT kernel_session_id, reply_context_json, applied_runtime_fingerprint,
                   applied_fingerprint_schema, applied_profile_version
            FROM session_bindings WHERE session_key = ?
            """,
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
            applied_runtime_fingerprint=row[2],
            applied_fingerprint_schema=row[3],
            applied_profile_version=row[4],
        )

    def bind(
        self,
        *,
        session_key: str,
        kernel_session_id: str,
        reply_context: ReplyContext,
        applied_runtime_fingerprint: str | None = None,
        applied_fingerprint_schema: str | None = None,
        applied_profile_version: int | None = None,
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
                (session_key, kernel_session_id, reply_context_json, updated_at, created_at,
                 applied_runtime_fingerprint, applied_fingerprint_schema,
                 applied_profile_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                kernel_session_id  = excluded.kernel_session_id,
                reply_context_json = excluded.reply_context_json,
                updated_at         = excluded.updated_at,
                applied_runtime_fingerprint = COALESCE(
                    excluded.applied_runtime_fingerprint,
                    session_bindings.applied_runtime_fingerprint
                ),
                applied_fingerprint_schema = COALESCE(
                    excluded.applied_fingerprint_schema,
                    session_bindings.applied_fingerprint_schema
                ),
                applied_profile_version = COALESCE(
                    excluded.applied_profile_version,
                    session_bindings.applied_profile_version
                )
            """,
            (
                session_key,
                kernel_session_id,
                rc_json,
                now_iso,
                now_iso,
                applied_runtime_fingerprint,
                applied_fingerprint_schema,
                applied_profile_version,
            ),
        )
        self._conn.commit()
        binding = self.get(session_key)
        if binding is None:  # pragma: no cover - SQLite commit invariant.
            raise RuntimeError("binding disappeared after persistence")
        return binding

    def get_control_operation(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> ControlOperation | None:
        """Return a completed control outcome recorded before a channel replay."""

        row = self._conn.execute(
            """
            SELECT status, kernel_session_id, reply_text
            FROM gateway_control_operations
            WHERE session_key = ? AND operation_id = ? AND kind = ?
            """,
            (session_key, operation_id, kind),
        ).fetchone()
        if row is None:
            return None
        return ControlOperation(
            session_key=session_key,
            operation_id=operation_id,
            kind=kind,
            status=row[0],
            kernel_session_id=row[1],
            reply_text=row[2],
        )

    def publish_reset(
        self,
        *,
        binding: SessionBinding,
        operation_id: str | None,
        superseded_run_id: str | None,
        reply_text: str,
        external_saga_id: str | None = None,
    ) -> ControlOperation | None:
        """Atomically publish the new binding, replay outcome, and old-run fence."""

        import datetime

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            if operation_id is not None:
                existing = self._conn.execute(
                    """
                    SELECT status, kernel_session_id, reply_text
                    FROM gateway_control_operations
                    WHERE session_key = ? AND operation_id = ? AND kind = 'new'
                    """,
                    (binding.session_key, operation_id),
                ).fetchone()
                if existing is not None:
                    self._conn.commit()
                    return ControlOperation(
                        session_key=binding.session_key,
                        operation_id=operation_id,
                        kind="new",
                        status=existing[0],
                        kernel_session_id=existing[1],
                        reply_text=existing[2],
                    )
            self._conn.execute(
                """
                INSERT INTO session_bindings
                    (session_key, kernel_session_id, reply_context_json, updated_at, created_at,
                     applied_runtime_fingerprint, applied_fingerprint_schema,
                     applied_profile_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_key) DO UPDATE SET
                    kernel_session_id = excluded.kernel_session_id,
                    reply_context_json = excluded.reply_context_json,
                    updated_at = excluded.updated_at,
                    applied_runtime_fingerprint = excluded.applied_runtime_fingerprint,
                    applied_fingerprint_schema = excluded.applied_fingerprint_schema,
                    applied_profile_version = excluded.applied_profile_version
                """,
                (
                    binding.session_key,
                    binding.kernel_session_id,
                    _serialize_reply_context(binding.reply_context),
                    now_iso,
                    now_iso,
                    binding.applied_runtime_fingerprint,
                    binding.applied_fingerprint_schema,
                    binding.applied_profile_version,
                ),
            )
            if superseded_run_id:
                self._conn.execute(
                    """
                    INSERT INTO gateway_superseded_runs
                        (run_id, session_key, replacement_kernel_session_id)
                    VALUES (?, ?, ?)
                    ON CONFLICT(run_id) DO NOTHING
                    """,
                    (
                        superseded_run_id,
                        binding.session_key,
                        binding.kernel_session_id,
                    ),
                )
            if operation_id is not None:
                self._conn.execute(
                    """
                    INSERT INTO gateway_control_operations
                        (session_key, operation_id, kind, status, kernel_session_id, reply_text)
                    VALUES (?, ?, 'new', 'completed', ?, ?)
                    ON CONFLICT(session_key, operation_id, kind) DO NOTHING
                    """,
                    (
                        binding.session_key,
                        operation_id,
                        binding.kernel_session_id,
                        reply_text,
                    ),
                )
                if external_saga_id:
                    self._conn.execute(
                        """
                        INSERT INTO gateway_pending_external_control_deliveries
                            (session_key, operation_id, kind, shadow_saga_id)
                        VALUES (?, ?, 'new', ?)
                        ON CONFLICT(session_key, operation_id, kind) DO NOTHING
                        """,
                        (binding.session_key, operation_id, external_saga_id),
                    )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        if operation_id is None:
            return None
        outcome = self.get_control_operation(
            session_key=binding.session_key, operation_id=operation_id, kind="new"
        )
        if outcome is None:  # pragma: no cover - transaction invariant.
            raise RuntimeError("reset outcome disappeared after publication")
        return outcome

    def record_control_operation(
        self,
        outcome: ControlOperation,
        *,
        external_saga_id: str | None = None,
    ) -> ControlOperation:
        """Persist a replayable non-reset control outcome."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                """
                INSERT INTO gateway_control_operations
                    (session_key, operation_id, kind, status, kernel_session_id, reply_text)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_key, operation_id, kind) DO NOTHING
                """,
                (
                    outcome.session_key,
                    outcome.operation_id,
                    outcome.kind,
                    outcome.status,
                    outcome.kernel_session_id,
                    outcome.reply_text,
                ),
            )
            if external_saga_id:
                self._conn.execute(
                    """
                    INSERT INTO gateway_pending_external_control_deliveries
                        (session_key, operation_id, kind, shadow_saga_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_key, operation_id, kind) DO NOTHING
                    """,
                    (
                        outcome.session_key,
                        outcome.operation_id,
                        outcome.kind,
                        external_saga_id,
                    ),
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return (
            self.get_control_operation(
                session_key=outcome.session_key,
                operation_id=outcome.operation_id,
                kind=outcome.kind,
            )
            or outcome
        )

    def pending_external_controls(self) -> tuple[PendingExternalControlDelivery, ...]:
        """Return external outcomes whose provider handoff is recoverable and pending."""

        rows = self._conn.execute(
            """
            SELECT operations.session_key, operations.operation_id, operations.kind,
                   operations.status, operations.kernel_session_id, operations.reply_text,
                   pending.shadow_saga_id, pending.state
            FROM gateway_pending_external_control_deliveries AS pending
            JOIN gateway_control_operations AS operations
              ON operations.session_key = pending.session_key
             AND operations.operation_id = pending.operation_id
             AND operations.kind = pending.kind
            WHERE pending.state != 'outbound_handed_off'
            ORDER BY pending.rowid ASC
            """
        ).fetchall()
        return tuple(
            PendingExternalControlDelivery(
                outcome=ControlOperation(
                    session_key=str(row[0]),
                    operation_id=str(row[1]),
                    kind=str(row[2]),
                    status=str(row[3]),
                    kernel_session_id=str(row[4]),
                    reply_text=str(row[5]),
                ),
                shadow_saga_id=str(row[6]),
                state=str(row[7]),
            )
            for row in rows
        )

    def mark_external_control_handed_off(
        self,
        *,
        session_key: str,
        operation_id: str,
        kind: str,
    ) -> None:
        """Mark an external confirmation after its router handoff returns."""

        self._conn.execute(
            """
            UPDATE gateway_pending_external_control_deliveries
            SET state = 'outbound_handed_off'
            WHERE session_key = ? AND operation_id = ? AND kind = ?
            """,
            (session_key, operation_id, kind),
        )
        self._conn.commit()

    def mark_external_control_materialized(
        self,
        *,
        session_key: str,
        operation_id: str,
        kind: str,
    ) -> None:
        """Record durable saga materialization before external router handoff."""

        self._conn.execute(
            """
            UPDATE gateway_pending_external_control_deliveries
            SET state = 'materialized'
            WHERE session_key = ? AND operation_id = ? AND kind = ?
              AND state = 'pending_materialization'
            """,
            (session_key, operation_id, kind),
        )
        self._conn.commit()

    def is_run_superseded(self, run_id: str) -> bool:
        """Return whether a durable reset made this run invisible."""

        row = self._conn.execute(
            "SELECT 1 FROM gateway_superseded_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return row is not None

    def apply_runtime(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
    ) -> SessionBinding:
        """Persist one Kernel-confirmed applied runtime for a stable binding."""

        return self.bind(
            session_key=binding.session_key,
            kernel_session_id=binding.kernel_session_id,
            reply_context=binding.reply_context,
            applied_runtime_fingerprint=runtime_fingerprint,
            applied_fingerprint_schema=fingerprint_schema,
            applied_profile_version=profile_version,
        )

    def apply_runtime_with_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: BoundaryIntent,
    ) -> SessionBinding:
        """Atomically record an applied identity and its anchored delivery intent.

        The session's effective runtime and the boundary are one admission fact. A
        crash between separate commits would either create a false divider or lose
        the explanation for a real runtime replacement, so this method owns both
        writes under one SQLite transaction.
        """

        if boundary.runtime_fingerprint != runtime_fingerprint:
            raise ValueError("boundary fingerprint must match applied runtime")
        if boundary.fingerprint_schema != fingerprint_schema:
            raise ValueError("boundary schema must match applied runtime")
        if boundary.profile_version != profile_version:
            raise ValueError("boundary profile version must match applied runtime")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            updated = self._conn.execute(
                """
                UPDATE session_bindings
                SET applied_runtime_fingerprint = ?, applied_fingerprint_schema = ?,
                    applied_profile_version = ?
                WHERE session_key = ?
                """,
                (
                    runtime_fingerprint,
                    fingerprint_schema,
                    profile_version,
                    binding.session_key,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("binding disappeared before runtime application")
            self._conn.execute(
                """
                INSERT INTO agent_config_boundary_outbox
                    (boundary_id, node_id, conversation_id, agent_id, before_message_id,
                     runtime_fingerprint, fingerprint_schema, profile_version, applied_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(boundary_id) DO NOTHING
                """,
                (
                    boundary.boundary_id,
                    boundary.node_id,
                    boundary.conversation_id,
                    boundary.agent_id,
                    boundary.before_message_id,
                    boundary.runtime_fingerprint,
                    boundary.fingerprint_schema,
                    boundary.profile_version,
                    boundary.applied_at,
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        updated_binding = self.get(binding.session_key)
        if updated_binding is None:  # pragma: no cover - SQLite commit invariant.
            raise RuntimeError("binding disappeared after runtime application")
        return updated_binding

    def apply_runtime_with_pending_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: PendingBoundaryIntent,
    ) -> SessionBinding:
        """Atomically retain an applied external runtime until its saga has an anchor."""

        if (
            boundary.runtime_fingerprint != runtime_fingerprint
            or boundary.fingerprint_schema != fingerprint_schema
            or boundary.profile_version != profile_version
        ):
            raise ValueError("pending boundary must describe the applied runtime")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            updated = self._conn.execute(
                """
                UPDATE session_bindings
                SET applied_runtime_fingerprint = ?, applied_fingerprint_schema = ?,
                    applied_profile_version = ?
                WHERE session_key = ?
                """,
                (
                    runtime_fingerprint,
                    fingerprint_schema,
                    profile_version,
                    binding.session_key,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("binding disappeared before runtime application")
            self._conn.execute(
                """
                INSERT INTO agent_config_pending_shadow_boundaries(
                    boundary_id, node_id, agent_id, runtime_fingerprint,
                    fingerprint_schema, profile_version, applied_at, shadow_saga_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(shadow_saga_id) DO NOTHING
                """,
                (
                    boundary.boundary_id,
                    boundary.node_id,
                    boundary.agent_id,
                    boundary.runtime_fingerprint,
                    boundary.fingerprint_schema,
                    boundary.profile_version,
                    boundary.applied_at,
                    boundary.shadow_saga_id,
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        updated_binding = self.get(binding.session_key)
        if updated_binding is None:  # pragma: no cover - SQLite commit invariant.
            raise RuntimeError("binding disappeared after runtime application")
        return updated_binding

    def promote_pending_boundary(
        self, *, shadow_saga_id: str, shadow_ref: object
    ) -> BoundaryIntent | None:
        """Make the saga's confirmed user anchor eligible for IM boundary delivery."""

        conversation_id = getattr(shadow_ref, "conversation_id", None)
        im_message_id = getattr(shadow_ref, "im_message_id", None)
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError("shadow boundary promotion requires conversation id")
        if not isinstance(im_message_id, str) or not im_message_id:
            raise ValueError("shadow boundary promotion requires IM message id")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                """
                SELECT boundary_id, node_id, agent_id, runtime_fingerprint,
                       fingerprint_schema, profile_version, applied_at
                FROM agent_config_pending_shadow_boundaries
                WHERE shadow_saga_id = ?
                """,
                (shadow_saga_id,),
            ).fetchone()
            if row is None:
                self._conn.commit()
                return None
            intent = BoundaryIntent(
                boundary_id=row[0],
                node_id=row[1],
                conversation_id=conversation_id,
                agent_id=row[2],
                before_message_id=im_message_id,
                runtime_fingerprint=row[3],
                fingerprint_schema=row[4],
                profile_version=row[5],
                applied_at=row[6],
            )
            self._conn.execute(
                """
                INSERT INTO agent_config_boundary_outbox(
                    boundary_id, node_id, conversation_id, agent_id, before_message_id,
                    runtime_fingerprint, fingerprint_schema, profile_version, applied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(boundary_id) DO NOTHING
                """,
                (
                    intent.boundary_id,
                    intent.node_id,
                    intent.conversation_id,
                    intent.agent_id,
                    intent.before_message_id,
                    intent.runtime_fingerprint,
                    intent.fingerprint_schema,
                    intent.profile_version,
                    intent.applied_at,
                ),
            )
            self._conn.execute(
                "DELETE FROM agent_config_pending_shadow_boundaries WHERE shadow_saga_id = ?",
                (shadow_saga_id,),
            )
            self._conn.commit()
            return intent
        except Exception:
            self._conn.rollback()
            raise

    def pending_boundaries(self) -> tuple[BoundaryIntent, ...]:
        """Return durable intents eligible for upstream delivery in insertion order."""

        return self._list_boundaries(state="pending")

    def quarantined_boundaries(self) -> tuple[BoundaryIntent, ...]:
        """Return terminally rejected intents for explicit operator diagnosis."""

        return self._list_boundaries(state="quarantined")

    def acknowledge_boundary(self, boundary_id: str) -> None:
        """Delete a boundary only after IM durably acknowledges that exact id."""

        self._conn.execute(
            "DELETE FROM agent_config_boundary_outbox WHERE boundary_id = ?",
            (boundary_id,),
        )
        self._conn.commit()

    def record_boundary_error(self, boundary_id: str, *, reason: str) -> None:
        """Quarantine a deterministically rejected boundary without erasing it."""

        self._conn.execute(
            """
            UPDATE agent_config_boundary_outbox
            SET state = 'quarantined', error_reason = ?
            WHERE boundary_id = ?
            """,
            (reason, boundary_id),
        )
        self._conn.commit()

    def delivery_ready_boundaries(self) -> tuple[BoundaryIntent, ...]:
        """Return pending intents whose durable retry deadline has elapsed."""

        return self._list_boundaries(state="pending", ready_at=time.time())

    def defer_boundary_retry(
        self,
        boundary_id: str,
        *,
        reason: str,
        retry_initial_seconds: float,
        retry_max_seconds: float,
    ) -> None:
        """Persist one bounded exponential retry deadline before returning to the loop."""

        if retry_initial_seconds < 0:
            raise ValueError("boundary retry initial delay must not be negative")
        if retry_max_seconds < retry_initial_seconds:
            raise ValueError("boundary retry maximum delay must cover initial delay")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                """
                SELECT retry_attempts FROM agent_config_boundary_outbox
                WHERE boundary_id = ? AND state = 'pending'
                """,
                (boundary_id,),
            ).fetchone()
            if row is None:
                self._conn.commit()
                return
            attempts = int(row[0]) + 1
            delay = min(
                retry_initial_seconds * (2 ** (attempts - 1)), retry_max_seconds
            )
            self._conn.execute(
                """
                UPDATE agent_config_boundary_outbox
                SET retry_attempts = ?, retry_not_before = ?, error_reason = ?
                WHERE boundary_id = ?
                """,
                (attempts, time.time() + delay, reason, boundary_id),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def next_boundary_retry_delay(self) -> float | None:
        """Return seconds until the earliest deferred pending boundary is due."""

        row = self._conn.execute(
            """
            SELECT MIN(retry_not_before)
            FROM agent_config_boundary_outbox
            WHERE state = 'pending' AND retry_not_before IS NOT NULL
            """
        ).fetchone()
        retry_not_before = row[0] if row is not None else None
        if retry_not_before is None:
            return None
        return max(0.0, float(retry_not_before) - time.time())

    def _list_boundaries(
        self, *, state: str, ready_at: float | None = None
    ) -> tuple[BoundaryIntent, ...]:
        clauses = ["state = ?"]
        parameters: list[object] = [state]
        if ready_at is not None:
            clauses.append("(retry_not_before IS NULL OR retry_not_before <= ?)")
            parameters.append(ready_at)
        rows = self._conn.execute(
            f"""
            SELECT boundary_id, node_id, conversation_id, agent_id, before_message_id,
                   runtime_fingerprint, fingerprint_schema, profile_version, applied_at
            FROM agent_config_boundary_outbox
            WHERE {" AND ".join(clauses)}
            ORDER BY rowid ASC
            """,
            parameters,
        ).fetchall()
        return tuple(BoundaryIntent(*row) for row in rows)

    def drop_agent(self, agent_id: str) -> None:
        """Remove all bindings whose session_key ends with ``:{agent_id}``.

        Args:
            agent_id: Routed agent id whose bindings should be dropped.

        Side Effects:
            Deletes matching rows from the SQLite table.
        """

        suffix = f":{_literal_like_pattern(agent_id)}"
        self._conn.execute(
            "DELETE FROM session_bindings WHERE session_key LIKE ? ESCAPE '!'",
            (f"%{suffix}",),
        )
        self._conn.commit()

    def drop(self, session_key: str) -> None:
        """Remove one persisted binding by its exact Gateway session key."""

        self._conn.execute(
            "DELETE FROM session_bindings WHERE session_key = ?",
            (session_key,),
        )
        self._conn.commit()

    def bindings_for_agent(self, agent_id: str) -> tuple[SessionBinding, ...]:
        """Return all persisted bindings routed to one Agent."""

        rows = self._conn.execute(
            """
            SELECT session_key, kernel_session_id, reply_context_json,
                   applied_runtime_fingerprint, applied_fingerprint_schema,
                   applied_profile_version
            FROM session_bindings
            WHERE session_key LIKE ? ESCAPE '!'
            ORDER BY created_at ASC, rowid ASC
            """,
            (f"%:{_literal_like_pattern(agent_id)}",),
        ).fetchall()
        return tuple(
            SessionBinding(
                session_key=row[0],
                kernel_session_id=row[1],
                reply_context=_deserialize_reply_context(row[2]),
                applied_runtime_fingerprint=row[3],
                applied_fingerprint_schema=row[4],
                applied_profile_version=row[5],
            )
            for row in rows
        )

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
            SELECT session_key, kernel_session_id, reply_context_json,
                   applied_runtime_fingerprint, applied_fingerprint_schema,
                   applied_profile_version
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
            applied_runtime_fingerprint=row[3],
            applied_fingerprint_schema=row[4],
            applied_profile_version=row[5],
        )

    def find_direct_by_agent(
        self, *, channel_name: str, agent_id: str
    ) -> SessionBinding | None:
        """Return the oldest direct-chat binding for one agent on one channel.

        Searches for all session keys matching the literal channel/Agent boundary
        ``{channel_name}:*:{agent_id}`` and returns the binding with the smallest
        ``created_at`` timestamp — the oldest (canonical) direct chat,
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

        # Only the conversation-id segment is a wildcard. Channel and Agent ids
        # are business identifiers, so SQLite pattern metacharacters stay literal.
        pattern = (
            f"{_literal_like_pattern(channel_name)}:%:{_literal_like_pattern(agent_id)}"
        )
        # feat-394: ORDER BY created_at ASC (not updated_at) so the result matches
        # IM's _find_canonical_direct_conversation(sorted(key=created_at)[0]).
        # created_at is written once at first INSERT and never updated on upsert,
        # so it reliably reflects when the binding (and therefore the direct chat)
        # was first established — independent of subsequent message activity.
        row = self._conn.execute(
            """
            SELECT session_key, kernel_session_id, reply_context_json,
                   applied_runtime_fingerprint, applied_fingerprint_schema,
                   applied_profile_version
            FROM session_bindings
            WHERE session_key LIKE ? ESCAPE '!'
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
            applied_runtime_fingerprint=row[3],
            applied_fingerprint_schema=row[4],
            applied_profile_version=row[5],
        )


def _serialize_reply_context(rc: ReplyContext) -> str:
    """Encode a ReplyContext to a JSON string for SQLite storage."""

    payload: dict[str, Any] = {
        "channel_name": rc.channel_name,
        "target_chat_id": rc.target_chat_id,
        "thread_id": rc.thread_id,
        "metadata": strip_runtime_protocol_metadata(rc.metadata),
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

    external_identity = external_identity_from_message(message)
    if external_identity is not None:
        return build_external_session_key(
            external_source=external_identity.external_source,
            external_chat_id=external_identity.external_chat_id,
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

    metadata = strip_runtime_protocol_metadata(message.metadata)
    for input_only_key in (
        "attachments",
        "kernel_input_parts",
        "image_resolution_failure",
    ):
        metadata.pop(input_only_key, None)
    return ReplyContext(
        channel_name=message.channel_name,
        target_chat_id=message.external_chat_id,
        thread_id=message.thread_id,
        metadata=metadata,
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
