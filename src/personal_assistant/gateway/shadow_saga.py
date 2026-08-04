"""Persist external-to-IM shadow message recovery facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Literal, Mapping
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

_CREATE_BUBBLE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS external_shadow_bubbles (
    shadow_message_id TEXT PRIMARY KEY,
    saga_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    bubble_ordinal INTEGER NOT NULL,
    state TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    thinking_json TEXT NOT NULL DEFAULT '[]',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    token_usage_json TEXT,
    started_at_ms INTEGER NOT NULL,
    finished_at_ms INTEGER,
    elapsed_ms INTEGER,
    delivery_status TEXT,
    kernel_message_id TEXT,
    im_message_id TEXT,
    UNIQUE (saga_id, run_id, bubble_ordinal),
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


@dataclass(frozen=True, slots=True)
class ExternalShadowBubbleEvent:
    """One normalized runtime fact applied to the current external shadow bubble."""

    kind: Literal["begin", "text", "thinking", "tool", "terminal", "discard"]
    saga_id: str
    run_id: str
    content: str | None = None
    thinking_text: str | None = None
    tool_call: Mapping[str, Any] | None = None
    token_usage: Mapping[str, Any] | None = None
    elapsed_ms: int | None = None
    delivery_status: str | None = None
    kernel_message_id: str | None = None
    source_time_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ExternalShadowBubble:
    """Durable presentation-ready projection for one logical Agent bubble."""

    shadow_message_id: str
    saga_id: str
    run_id: str
    bubble_ordinal: int
    state: str
    content: str
    thinking: tuple[dict[str, Any], ...]
    tool_calls: tuple[dict[str, Any], ...]
    token_usage: dict[str, Any] | None
    started_at_ms: int
    finished_at_ms: int | None
    elapsed_ms: int | None
    delivery_status: str | None
    kernel_message_id: str | None
    im_message_id: str | None


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
        self._conn.execute(_CREATE_BUBBLE_TABLE_SQL)
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

    def record(self, event: ExternalShadowBubbleEvent) -> ExternalShadowBubble:
        """Apply one normalized event to a durable logical-bubble projection."""

        if not event.saga_id or not event.run_id:
            raise ValueError("shadow bubble event requires saga_id and run_id")
        if event.kind not in {
            "begin",
            "text",
            "thinking",
            "tool",
            "terminal",
            "discard",
        }:
            raise ValueError(f"unsupported shadow bubble event: {event.kind}")
        with self._conn:
            row = self._recording_bubble_row(saga_id=event.saga_id, run_id=event.run_id)
            if row is None:
                if event.kind in {"terminal", "discard"}:
                    latest = self._latest_bubble_row(
                        saga_id=event.saga_id, run_id=event.run_id
                    )
                    if latest is not None and str(latest[4]) in {
                        "ready",
                        "reconciled",
                        "discarded",
                    }:
                        return self._bubble_from_row(latest)
                row = self._insert_bubble(
                    saga_id=event.saga_id,
                    run_id=event.run_id,
                    started_at_ms=event.source_time_ms,
                )
            shadow_message_id = str(row[0])
            if event.kind == "begin":
                return self._bubble_from_row(row)

            content = str(row[5])
            thinking = _decode_json_list(row[6])
            tool_calls = _decode_json_list(row[7])
            token_usage = _decode_json_object(row[8])
            started_at_ms = int(row[9])
            finished_at_ms = int(row[10]) if row[10] is not None else None
            elapsed_ms = int(row[11]) if row[11] is not None else None
            delivery_status = str(row[12]) if row[12] is not None else None
            kernel_message_id = str(row[13]) if row[13] is not None else None
            state = str(row[4])

            if event.kind == "text":
                content = event.content or ""
                if event.kernel_message_id:
                    kernel_message_id = event.kernel_message_id
            elif event.kind == "thinking":
                text = (event.thinking_text or "").strip()
                if text:
                    thinking.append(
                        {"seq": _next_process_seq(thinking, tool_calls), "text": text}
                    )
            elif event.kind == "tool":
                if event.tool_call is None:
                    raise ValueError("tool shadow event requires tool_call")
                incoming = dict(event.tool_call)
                call_id = str(incoming.get("id") or "").strip()
                if not call_id:
                    raise ValueError("tool shadow event requires tool_call.id")
                existing_index = next(
                    (
                        index
                        for index, item in enumerate(tool_calls)
                        if str(item.get("id") or "") == call_id
                    ),
                    None,
                )
                if existing_index is None:
                    incoming["seq"] = _next_process_seq(thinking, tool_calls)
                    tool_calls.append(incoming)
                else:
                    prior = tool_calls[existing_index]
                    incoming["seq"] = prior.get("seq")
                    tool_calls[existing_index] = incoming
            elif event.kind in {"terminal", "discard"}:
                finished_at_ms = event.source_time_ms or _now_ms()
                elapsed_ms = (
                    event.elapsed_ms
                    if event.elapsed_ms is not None
                    else max(0, finished_at_ms - started_at_ms)
                )
                if event.kind == "discard":
                    state = "discarded"
                    delivery_status = None
                    token_usage = None
                else:
                    if event.delivery_status not in {"completed", "failed"}:
                        raise ValueError(
                            "terminal shadow event requires completed or failed status"
                        )
                    state = "ready"
                    delivery_status = event.delivery_status
                    token_usage = (
                        dict(event.token_usage)
                        if event.token_usage is not None
                        else None
                    )
                    if event.content is not None:
                        content = event.content
                    if event.kernel_message_id:
                        kernel_message_id = event.kernel_message_id

            self._conn.execute(
                """
                UPDATE external_shadow_bubbles
                SET state = ?, content = ?, thinking_json = ?, tool_calls_json = ?,
                    token_usage_json = ?, finished_at_ms = ?, elapsed_ms = ?,
                    delivery_status = ?, kernel_message_id = ?
                WHERE shadow_message_id = ?
                """,
                (
                    state,
                    content,
                    _encode_json(thinking),
                    _encode_json(tool_calls),
                    _encode_json(token_usage) if token_usage is not None else None,
                    finished_at_ms,
                    elapsed_ms,
                    delivery_status,
                    kernel_message_id,
                    shadow_message_id,
                ),
            )
        return self.require_snapshot(shadow_message_id)

    def pending_snapshots(self) -> tuple[ExternalShadowBubble, ...]:
        """Return terminal rich snapshots waiting for IM acknowledgement."""

        rows = self._conn.execute(
            f"""
            SELECT {_BUBBLE_COLUMNS}
            FROM external_shadow_bubbles
            WHERE state = 'ready'
            ORDER BY rowid ASC
            """
        ).fetchall()
        return tuple(self._bubble_from_row(row) for row in rows)

    def require_snapshot(self, shadow_message_id: str) -> ExternalShadowBubble:
        """Return one durable bubble projection by stable source identity."""

        row = self._conn.execute(
            f"SELECT {_BUBBLE_COLUMNS} FROM external_shadow_bubbles "
            "WHERE shadow_message_id = ?",
            (shadow_message_id,),
        ).fetchone()
        if row is None:
            raise LookupError("external shadow bubble not found")
        return self._bubble_from_row(row)

    def acknowledge(
        self, *, shadow_message_id: str, im_message_id: str
    ) -> ExternalShadowBubble:
        """Mark a rich snapshot reconciled only after IM returns its message id."""

        if not im_message_id:
            raise ValueError("shadow bubble IM acknowledgement requires message id")
        with self._conn:
            updated = self._conn.execute(
                """
                UPDATE external_shadow_bubbles
                SET state = 'reconciled', im_message_id = ?
                WHERE shadow_message_id = ? AND state IN ('ready', 'reconciled')
                """,
                (im_message_id, shadow_message_id),
            )
            if updated.rowcount != 1:
                raise LookupError("ready external shadow bubble not found")
        return self.require_snapshot(shadow_message_id)

    def _recording_bubble_row(
        self, *, saga_id: str, run_id: str
    ) -> sqlite3.Row | tuple[Any, ...] | None:
        return self._conn.execute(
            f"""
            SELECT {_BUBBLE_COLUMNS}
            FROM external_shadow_bubbles
            WHERE saga_id = ? AND run_id = ? AND state = 'recording'
            ORDER BY bubble_ordinal DESC
            LIMIT 1
            """,
            (saga_id, run_id),
        ).fetchone()

    def _latest_bubble_row(
        self, *, saga_id: str, run_id: str
    ) -> sqlite3.Row | tuple[Any, ...] | None:
        return self._conn.execute(
            f"""
            SELECT {_BUBBLE_COLUMNS}
            FROM external_shadow_bubbles
            WHERE saga_id = ? AND run_id = ?
            ORDER BY bubble_ordinal DESC
            LIMIT 1
            """,
            (saga_id, run_id),
        ).fetchone()

    def _insert_bubble(
        self, *, saga_id: str, run_id: str, started_at_ms: int | None
    ) -> tuple[Any, ...]:
        ordinal_row = self._conn.execute(
            """
            SELECT COALESCE(MAX(bubble_ordinal), -1) + 1
            FROM external_shadow_bubbles
            WHERE saga_id = ? AND run_id = ?
            """,
            (saga_id, run_id),
        ).fetchone()
        ordinal = int(ordinal_row[0])
        shadow_message_id = _shadow_message_id(
            saga_id=saga_id, run_id=run_id, bubble_ordinal=ordinal
        )
        self._conn.execute(
            """
            INSERT INTO external_shadow_bubbles(
                shadow_message_id, saga_id, run_id, bubble_ordinal, state, started_at_ms
            ) VALUES (?, ?, ?, ?, 'recording', ?)
            """,
            (
                shadow_message_id,
                saga_id,
                run_id,
                ordinal,
                started_at_ms or _now_ms(),
            ),
        )
        row = self._recording_bubble_row(saga_id=saga_id, run_id=run_id)
        assert row is not None
        return row

    @staticmethod
    def _bubble_from_row(row: sqlite3.Row | tuple[Any, ...]) -> ExternalShadowBubble:
        return ExternalShadowBubble(
            shadow_message_id=str(row[0]),
            saga_id=str(row[1]),
            run_id=str(row[2]),
            bubble_ordinal=int(row[3]),
            state=str(row[4]),
            content=str(row[5]),
            thinking=tuple(_decode_json_list(row[6])),
            tool_calls=tuple(_decode_json_list(row[7])),
            token_usage=_decode_json_object(row[8]),
            started_at_ms=int(row[9]),
            finished_at_ms=int(row[10]) if row[10] is not None else None,
            elapsed_ms=int(row[11]) if row[11] is not None else None,
            delivery_status=str(row[12]) if row[12] is not None else None,
            kernel_message_id=str(row[13]) if row[13] is not None else None,
            im_message_id=str(row[14]) if row[14] is not None else None,
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

    def recovery_sagas(self) -> tuple[ExternalShadowSaga, ...]:
        """Return sagas with a missing user anchor or a ready rich Agent snapshot."""

        rows = self._conn.execute(
            """
            SELECT saga_id, owner_id, agent_id, channel_name, connector_account_id,
                   external_chat_id, thread_id, provider_event_id, session_key,
                   canonical_inbound_json, reply_context_json, conversation_id,
                   im_message_id
            FROM external_shadow_sagas AS saga
            WHERE conversation_id IS NULL OR im_message_id IS NULL OR EXISTS (
                SELECT 1 FROM external_shadow_bubbles AS bubble
                WHERE bubble.saga_id = saga.saga_id AND bubble.state = 'ready'
            )
            ORDER BY saga.rowid ASC
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


_BUBBLE_COLUMNS = """
shadow_message_id, saga_id, run_id, bubble_ordinal, state, content,
thinking_json, tool_calls_json, token_usage_json, started_at_ms,
finished_at_ms, elapsed_ms, delivery_status, kernel_message_id, im_message_id
"""


def _shadow_message_id(*, saga_id: str, run_id: str, bubble_ordinal: int) -> str:
    encoded = json.dumps(
        (saga_id, run_id, bubble_ordinal), separators=(",", ":"), ensure_ascii=False
    )
    return sha256(encoded.encode()).hexdigest()


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _encode_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _decode_json_list(value: object) -> list[dict[str, Any]]:
    parsed = json.loads(str(value)) if value is not None else []
    if not isinstance(parsed, list):
        raise ValueError("external shadow bubble JSON must be a list")
    return [dict(item) for item in parsed if isinstance(item, Mapping)]


def _decode_json_object(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    parsed = json.loads(str(value))
    if not isinstance(parsed, Mapping):
        raise ValueError("external shadow bubble token usage must be an object")
    return dict(parsed)


def _next_process_seq(
    thinking: list[dict[str, Any]], tool_calls: list[dict[str, Any]]
) -> int:
    seqs = [item.get("seq") for item in [*thinking, *tool_calls]]
    numeric = [int(value) for value in seqs if isinstance(value, int)]
    return max(numeric, default=-1) + 1
