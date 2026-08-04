"""Persist external-to-IM shadow message recovery facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.runtime_protocol import (
    ShadowConversationRef,
    external_identity_from_message,
    strip_runtime_protocol_metadata,
)
from personal_assistant.gateway.session_keys import (
    build_reply_context,
    build_session_key,
)


@dataclass(frozen=True, slots=True)
class ExternalShadowSaga:
    """Capture the durable source facts for one external inbound event.

    Args:
        saga_id: Deterministic identity of the external event and its routed target.
        owner_id: IM owner whose shadow conversation owns the message.
        agent_id: Routed Agent identity.
        channel_name: External channel adapter identity.
        connector_account_id: Stable external connector/account identity.
        external_chat_id: Provider conversation routing identity.
        thread_id: Optional provider thread routing identity.
        provider_event_id: Stable provider event/message identity.
        session_key: Gateway session association selected before Kernel submit.
        canonical_inbound_json: Replay-safe normalized inbound data.
        reply_context_json: Replay-safe external reply target.
        conversation_id: IM conversation once shadow creation succeeds.
        im_message_id: IM user-message anchor once creation succeeds.
    """

    saga_id: str
    owner_id: str
    agent_id: str
    channel_name: str
    connector_account_id: str
    external_chat_id: str
    thread_id: str | None
    provider_event_id: str
    session_key: str
    canonical_inbound_json: str
    reply_context_json: str
    conversation_id: str | None
    im_message_id: str | None

    @property
    def shadow_user_idempotency_key(self) -> str:
        """Return the caller key that makes IM user-anchor creation replay safe."""

        return f"shadow-user:{self.saga_id}"

    @property
    def shadow_ref(self) -> ShadowConversationRef | None:
        """Return the confirmed IM anchor when both IDs are durable."""

        if self.conversation_id is None or self.im_message_id is None:
            return None
        return ShadowConversationRef(
            conversation_id=self.conversation_id,
            im_message_id=self.im_message_id,
            shadow_saga_id=self.saga_id,
        )


_CREATE_SAGA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS external_shadow_sagas (
    saga_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    connector_account_id TEXT NOT NULL,
    external_chat_id TEXT NOT NULL,
    thread_id TEXT,
    provider_event_id TEXT NOT NULL,
    session_key TEXT NOT NULL,
    canonical_inbound_json TEXT NOT NULL,
    reply_context_json TEXT NOT NULL,
    conversation_id TEXT,
    im_message_id TEXT,
    UNIQUE(
        owner_id, agent_id, channel_name, connector_account_id,
        external_chat_id, thread_id, provider_event_id
    )
)
"""

_CREATE_OUTPUT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS external_shadow_outputs (
    saga_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    output_kind TEXT NOT NULL,
    kernel_message_id TEXT,
    ordinal INTEGER NOT NULL,
    content TEXT NOT NULL,
    im_message_id TEXT,
    PRIMARY KEY (saga_id, run_id, output_kind, ordinal),
    UNIQUE (saga_id, run_id, output_kind, kernel_message_id),
    FOREIGN KEY (saga_id) REFERENCES external_shadow_sagas(saga_id)
)
"""

_CREATE_DIAGNOSTICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS external_shadow_diagnostics (
    diagnostic_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_name TEXT NOT NULL,
    external_chat_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    reason TEXT NOT NULL
)
"""


@dataclass(frozen=True, slots=True)
class ExternalShadowOutput:
    """Persist one Agent-visible shadow output until IM confirms its mirror."""

    saga_id: str
    run_id: str
    output_kind: str
    kernel_message_id: str | None
    ordinal: int
    content: str
    im_message_id: str | None

    @property
    def caller_idempotency_key(self) -> str:
        """Return the stable IM caller key for this logical Agent output."""

        logical_id = self.kernel_message_id or str(self.ordinal)
        return (
            f"shadow-agent:{self.saga_id}:{self.run_id}:{self.output_kind}:{logical_id}"
        )


class ExternalShadowSagaStore:
    """Own crash-safe external shadow recovery data in Gateway-local SQLite.

    The store deliberately commits the canonical inbound record before any IM request.
    A repeated provider delivery or a response-before-local-mark crash can therefore
    reuse the same caller idempotency key and recover the original IM anchor.
    """

    def __init__(self, *, db_path: Path) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_CREATE_SAGA_TABLE_SQL)
        self._conn.execute(_CREATE_OUTPUT_TABLE_SQL)
        self._conn.execute(_CREATE_DIAGNOSTICS_TABLE_SQL)
        self._conn.commit()

    def prepare(
        self, *, message: InboundMessage, agent_id: str, owner_id: str
    ) -> ExternalShadowSaga | None:
        """Persist or return the saga for one normalized external inbound event."""

        external_identity = external_identity_from_message(message)
        event_identity = message.external_event_identity
        if external_identity is None or event_identity is None:
            self._record_identity_unavailable(message=message, agent_id=agent_id)
            return None
        if external_identity.trigger_source == "im":
            return None
        owner = owner_id.strip()
        if not owner:
            raise ValueError("external shadow saga requires an IM owner id")
        saga_id = _saga_id(
            owner_id=owner,
            agent_id=agent_id,
            channel_name=message.channel_name,
            connector_account_id=event_identity.connector_account_id,
            external_chat_id=external_identity.external_chat_id,
            thread_id=message.thread_id,
            provider_event_id=event_identity.provider_event_id,
        )
        saga = ExternalShadowSaga(
            saga_id=saga_id,
            owner_id=owner,
            agent_id=agent_id,
            channel_name=message.channel_name,
            connector_account_id=event_identity.connector_account_id,
            external_chat_id=external_identity.external_chat_id,
            thread_id=message.thread_id,
            provider_event_id=event_identity.provider_event_id,
            session_key=build_session_key(message, agent_id=agent_id),
            canonical_inbound_json=json.dumps(
                {
                    "channel_name": message.channel_name,
                    "text": message.text,
                    "external_user_id": message.external_user_id,
                    "external_chat_id": message.external_chat_id,
                    "is_group": message.is_group,
                    "thread_id": message.thread_id,
                    "metadata": strip_runtime_protocol_metadata(message.metadata),
                    "external_identity": {
                        "external_source": external_identity.external_source,
                        "external_chat_id": external_identity.external_chat_id,
                        "conversation_type": external_identity.conversation_type,
                        "trigger_source": external_identity.trigger_source,
                    },
                    "external_event_identity": asdict(event_identity),
                },
                sort_keys=True,
                ensure_ascii=False,
            ),
            reply_context_json=json.dumps(
                asdict(build_reply_context(message)), sort_keys=True, ensure_ascii=False
            ),
            conversation_id=None,
            im_message_id=None,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO external_shadow_sagas(
                    saga_id, owner_id, agent_id, channel_name, connector_account_id,
                    external_chat_id, thread_id, provider_event_id, session_key,
                    canonical_inbound_json, reply_context_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(saga_id) DO NOTHING
                """,
                (
                    saga.saga_id,
                    saga.owner_id,
                    saga.agent_id,
                    saga.channel_name,
                    saga.connector_account_id,
                    saga.external_chat_id,
                    saga.thread_id,
                    saga.provider_event_id,
                    saga.session_key,
                    saga.canonical_inbound_json,
                    saga.reply_context_json,
                ),
            )
        return self.require(saga.saga_id)

    def record_anchor(
        self, *, saga_id: str, shadow_ref: ShadowConversationRef
    ) -> ExternalShadowSaga:
        """Persist the IM response before allowing the associated run to proceed."""

        if shadow_ref.im_message_id is None:
            raise ValueError("shadow saga anchor requires an IM message id")
        with self._conn:
            updated = self._conn.execute(
                """
                UPDATE external_shadow_sagas
                SET conversation_id = ?, im_message_id = ?
                WHERE saga_id = ?
                """,
                (shadow_ref.conversation_id, shadow_ref.im_message_id, saga_id),
            )
            if updated.rowcount != 1:
                raise LookupError(f"external shadow saga not found: {saga_id}")
        return self.require(saga_id)

    def recover_owner(
        self, *, saga: ExternalShadowSaga, authenticated_owner_id: str
    ) -> ExternalShadowSaga:
        """Correct a stale local owner without changing durable saga identity.

        The saga id stays stable because pending Agent outputs and configuration
        boundaries already refer to it. The authenticated IM identity becomes the
        owner used by subsequent shadow writes, while the diagnostic remains durable.

        Args:
            saga: Existing durable saga whose local owner is stale.
            authenticated_owner_id: Current owner resolved from the IM access token.

        Returns:
            The corrected saga with its original durable identity.

        Raises:
            ValueError: When the authenticated owner is empty.
            LookupError: When the saga no longer exists.

        Side Effects:
            Updates the saga owner and appends one durable recovery diagnostic in the
            same SQLite transaction.
        """

        owner_id = authenticated_owner_id.strip()
        if not owner_id:
            raise ValueError(
                "external shadow saga requires an authenticated IM owner id"
            )
        if saga.owner_id == owner_id:
            return saga
        reason = f"shadow_owner_recovered:{saga.owner_id}->{owner_id}"
        with self._conn:
            updated = self._conn.execute(
                "UPDATE external_shadow_sagas SET owner_id = ? WHERE saga_id = ?",
                (owner_id, saga.saga_id),
            )
            if updated.rowcount != 1:
                raise LookupError(f"external shadow saga not found: {saga.saga_id}")
            self._conn.execute(
                """
                INSERT INTO external_shadow_diagnostics(
                    channel_name, external_chat_id, agent_id, reason
                ) VALUES (?, ?, ?, ?)
                """,
                (saga.channel_name, saga.external_chat_id, saga.agent_id, reason),
            )
        return self.require(saga.saga_id)

    def prepare_output(
        self,
        *,
        saga_id: str,
        run_id: str,
        output_kind: str,
        kernel_message_id: str | None,
        content: str,
    ) -> ExternalShadowOutput:
        """Durably capture one Agent output before external reply delivery.

        A Kernel message id is the stable identity for an intermediate output. Final
        replies are unique by their declared ``final`` kind; when the Kernel supplies
        no message id for another output, SQLite assigns an ordinal once and reuses it
        across every replay.
        """

        if not run_id:
            raise ValueError("shadow output requires run id")
        if output_kind not in {"final", "intermediate"}:
            raise ValueError(f"unsupported shadow output kind: {output_kind}")
        if not content:
            raise ValueError("shadow output requires content")
        with self._conn:
            if output_kind == "final":
                ordinal = 0
            elif kernel_message_id is not None:
                existing = self._conn.execute(
                    """
                    SELECT ordinal FROM external_shadow_outputs
                    WHERE saga_id = ? AND run_id = ? AND output_kind = ?
                      AND kernel_message_id = ?
                    """,
                    (saga_id, run_id, output_kind, kernel_message_id),
                ).fetchone()
                ordinal = (
                    int(existing[0])
                    if existing is not None
                    else self._next_output_ordinal(
                        saga_id=saga_id, run_id=run_id, output_kind=output_kind
                    )
                )
            else:
                ordinal = self._next_output_ordinal(
                    saga_id=saga_id, run_id=run_id, output_kind=output_kind
                )
            self._conn.execute(
                """
                INSERT INTO external_shadow_outputs(
                    saga_id, run_id, output_kind, kernel_message_id, ordinal, content
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(saga_id, run_id, output_kind, ordinal) DO NOTHING
                """,
                (saga_id, run_id, output_kind, kernel_message_id, ordinal, content),
            )
        return self.require_output(
            saga_id=saga_id, run_id=run_id, output_kind=output_kind, ordinal=ordinal
        )

    def require_output(
        self, *, saga_id: str, run_id: str, output_kind: str, ordinal: int
    ) -> ExternalShadowOutput:
        """Return one durable output record or fail when its source fact is absent."""

        row = self._conn.execute(
            """
            SELECT saga_id, run_id, output_kind, kernel_message_id, ordinal, content,
                   im_message_id
            FROM external_shadow_outputs
            WHERE saga_id = ? AND run_id = ? AND output_kind = ? AND ordinal = ?
            """,
            (saga_id, run_id, output_kind, ordinal),
        ).fetchone()
        if row is None:
            raise LookupError("external shadow output not found")
        return ExternalShadowOutput(*row)

    def pending_outputs(self) -> tuple[ExternalShadowOutput, ...]:
        """Return Agent outputs whose IM mirror acknowledgement is still absent."""

        rows = self._conn.execute(
            """
            SELECT saga_id, run_id, output_kind, kernel_message_id, ordinal, content,
                   im_message_id
            FROM external_shadow_outputs
            WHERE im_message_id IS NULL
            ORDER BY rowid ASC
            """
        ).fetchall()
        return tuple(ExternalShadowOutput(*row) for row in rows)

    def record_output_anchor(
        self, *, output: ExternalShadowOutput, im_message_id: str
    ) -> ExternalShadowOutput:
        """Mark one output mirrored only after IM returns its concrete message id."""

        if not im_message_id:
            raise ValueError("shadow output IM anchor requires message id")
        with self._conn:
            updated = self._conn.execute(
                """
                UPDATE external_shadow_outputs SET im_message_id = ?
                WHERE saga_id = ? AND run_id = ? AND output_kind = ? AND ordinal = ?
                """,
                (
                    im_message_id,
                    output.saga_id,
                    output.run_id,
                    output.output_kind,
                    output.ordinal,
                ),
            )
            if updated.rowcount != 1:
                raise LookupError("external shadow output not found")
        return self.require_output(
            saga_id=output.saga_id,
            run_id=output.run_id,
            output_kind=output.output_kind,
            ordinal=output.ordinal,
        )

    def _next_output_ordinal(
        self, *, saga_id: str, run_id: str, output_kind: str
    ) -> int:
        row = self._conn.execute(
            """
            SELECT COALESCE(MAX(ordinal), -1) + 1
            FROM external_shadow_outputs
            WHERE saga_id = ? AND run_id = ? AND output_kind = ?
            """,
            (saga_id, run_id, output_kind),
        ).fetchone()
        return int(row[0])

    def pending(self) -> tuple[ExternalShadowSaga, ...]:
        """Return sagas whose IM user anchor still needs replay."""

        rows = self._conn.execute(
            """
            SELECT saga_id, owner_id, agent_id, channel_name, connector_account_id,
                   external_chat_id, thread_id, provider_event_id, session_key,
                   canonical_inbound_json, reply_context_json, conversation_id,
                   im_message_id
            FROM external_shadow_sagas
            WHERE conversation_id IS NULL OR im_message_id IS NULL
            ORDER BY rowid ASC
            """
        ).fetchall()
        return tuple(ExternalShadowSaga(*row) for row in rows)

    def require(self, saga_id: str) -> ExternalShadowSaga:
        """Return one persisted saga or fail when the durable record is absent."""

        row = self._conn.execute(
            """
            SELECT saga_id, owner_id, agent_id, channel_name, connector_account_id,
                   external_chat_id, thread_id, provider_event_id, session_key,
                   canonical_inbound_json, reply_context_json, conversation_id,
                   im_message_id
            FROM external_shadow_sagas WHERE saga_id = ?
            """,
            (saga_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"external shadow saga not found: {saga_id}")
        return ExternalShadowSaga(*row)

    def diagnostic_reasons(self) -> tuple[str, ...]:
        """Return durable shadow diagnostics for operator inspection."""

        rows = self._conn.execute(
            "SELECT reason FROM external_shadow_diagnostics ORDER BY diagnostic_id ASC"
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def _record_identity_unavailable(
        self, *, message: InboundMessage, agent_id: str
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO external_shadow_diagnostics(
                    channel_name, external_chat_id, agent_id, reason
                ) VALUES (?, ?, ?, 'shadow_identity_unavailable')
                """,
                (message.channel_name, message.external_chat_id, agent_id),
            )


def _saga_id(
    *,
    owner_id: str,
    agent_id: str,
    channel_name: str,
    connector_account_id: str,
    external_chat_id: str,
    thread_id: str | None,
    provider_event_id: str,
) -> str:
    """Derive a compact stable identity from the declared saga natural key."""

    natural_key: tuple[str | None, ...] = (
        owner_id,
        agent_id,
        channel_name,
        connector_account_id,
        external_chat_id,
        thread_id,
        provider_event_id,
    )
    encoded = json.dumps(natural_key, separators=(",", ":"), ensure_ascii=False)
    return sha256(encoded.encode()).hexdigest()
