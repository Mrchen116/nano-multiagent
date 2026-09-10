"""Persist global Agent input, exact consumption and the shared work journal."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from personal_assistant.tools.inbox_result import source_summary

from personal_assistant.tools.inbox import (
    content_digest,
    serialize_inbox_page,
    validate_arguments,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


class GlobalInboxStore:
    """Own the node's single SQLite Inbox, binding and work-event database.

    Args:
        db_path: File under this Gateway's isolated runtime directory.
    """

    def __init__(self, db_path: Path) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS global_sessions (
                agent_id TEXT PRIMARY KEY, session_id TEXT UNIQUE NOT NULL,
                workspace_root TEXT NOT NULL, runtime_fingerprint TEXT, profile_version INTEGER);
            CREATE TABLE IF NOT EXISTS inbox_targets (
                agent_id TEXT, target TEXT, data TEXT NOT NULL, PRIMARY KEY(agent_id,target));
            CREATE TABLE IF NOT EXISTS inbox_entries (
                agent_id TEXT, seq INTEGER, ingress_key TEXT, target TEXT,
                data TEXT NOT NULL, requires_attention INTEGER NOT NULL, consumed_at TEXT,
                PRIMARY KEY(agent_id,seq), UNIQUE(agent_id,ingress_key));
            CREATE TABLE IF NOT EXISTS inbox_read_receipts (
                agent_id TEXT, session_id TEXT, tool_call_id TEXT, receipt_id TEXT UNIQUE,
                entries_and_parts TEXT, content_digest TEXT, page TEXT, committed_at TEXT,
                PRIMARY KEY(agent_id,session_id,tool_call_id));
            CREATE TABLE IF NOT EXISTS inbox_page_cursors (
                cursor_id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inbox_consumed_parts (
                agent_id TEXT, entry_seq INTEGER, part_key TEXT,
                PRIMARY KEY(agent_id,entry_seq,part_key));
            CREATE TABLE IF NOT EXISTS inbox_wake_state (
                agent_id TEXT PRIMARY KEY, latest_signal_seq INTEGER DEFAULT 0,
                signaled_through_seq INTEGER DEFAULT 0, stop_through_seq INTEGER DEFAULT 0,
                pending_submission_id TEXT, pending_through_seq INTEGER DEFAULT 0,
                retry_at TEXT, last_error TEXT);
            CREATE TABLE IF NOT EXISTS work_sessions (
                session_id TEXT PRIMARY KEY, root_agent_id TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS work_events (
                journal_seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                root_agent_id TEXT NOT NULL, session_id TEXT NOT NULL, turn_id TEXT,
                event_type TEXT NOT NULL, source_event_id TEXT, payload TEXT NOT NULL, observed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS work_relay_progress (
                journal_id TEXT PRIMARY KEY, through_seq INTEGER NOT NULL DEFAULT 0);
        """)
        with self._db:
            if self._db.execute("SELECT 1 FROM work_relay_progress").fetchone() is None:
                self._db.execute(
                    "INSERT INTO work_relay_progress VALUES (?,0)", (uuid4().hex,)
                )
        self.journal_id = self._db.execute(
            "SELECT journal_id FROM work_relay_progress"
        ).fetchone()[0]

    def close(self) -> None:
        """Close the database after Gateway input and observers have stopped."""
        with self._lock:
            self._db.close()

    def get_global_session(self, agent_id: str) -> dict[str, Any] | None:
        """Return the persistent main binding, or None before first creation."""
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM global_sessions WHERE agent_id=?", (agent_id,)
            ).fetchone()
            return dict(row) if row else None

    def save_global_session(
        self,
        agent_id: str,
        session_id: str,
        workspace_root: str,
        runtime_fingerprint: str = "",
        profile_version: int = 0,
    ) -> None:
        """Save runtime revisions without allowing an existing binding to move."""
        with self._lock, self._db:
            existing = self.get_global_session(agent_id)
            if existing and (
                existing["session_id"] != session_id
                or existing["workspace_root"] != str(workspace_root)
            ):
                raise ValueError("global Session identity and workspace are immutable")
            self._db.execute(
                """INSERT INTO global_sessions VALUES (?,?,?,?,?) ON CONFLICT(agent_id)
                DO UPDATE SET runtime_fingerprint=excluded.runtime_fingerprint, profile_version=excluded.profile_version""",
                (
                    agent_id,
                    session_id,
                    str(workspace_root),
                    runtime_fingerprint,
                    profile_version,
                ),
            )

    def get_signal_state(self, agent_id: str) -> dict[str, Any]:
        """Return durable effective attention, stop and pending-submission state."""
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO inbox_wake_state(agent_id) VALUES (?)",
                (agent_id,),
            )
            return dict(
                self._db.execute(
                    "SELECT * FROM inbox_wake_state WHERE agent_id=?", (agent_id,)
                ).fetchone()
            )

    def update_signal_state(self, agent_id: str, **fields: Any) -> dict[str, Any]:
        """Persist coordinator state; callers serialize admission and stop changes."""
        allowed = {
            "latest_signal_seq",
            "signaled_through_seq",
            "stop_through_seq",
            "pending_submission_id",
            "pending_through_seq",
            "retry_at",
            "last_error",
        }
        if set(fields) - allowed:
            raise ValueError("Unknown signal state field")
        with self._lock, self._db:
            self.get_signal_state(agent_id)
            if fields:
                self._db.execute(
                    "UPDATE inbox_wake_state SET "
                    + ",".join(f"{key}=?" for key in fields)
                    + " WHERE agent_id=?",
                    (*fields.values(), agent_id),
                )
            return self.get_signal_state(agent_id)

    def register_work_session(
        self,
        session_id: str,
        root_agent_id: str,
        scope: str,
        parent_session_id: str | None = None,
        **identity: Any,
    ) -> None:
        """Register observed execution ancestry before its first runtime event."""
        with self._lock, self._db:
            old = self.get_work_session(session_id)
            if old and (old["root_agent_id"] != root_agent_id or old["scope"] != scope):
                raise ValueError("work Session ownership is immutable")
            data = {
                **(old or {}),
                **identity,
                "session_id": session_id,
                "root_agent_id": root_agent_id,
                "scope": scope,
                "parent_session_id": parent_session_id,
            }
            self._db.execute(
                "INSERT INTO work_sessions VALUES (?,?,?) ON CONFLICT(session_id) DO UPDATE SET data=excluded.data",
                (session_id, root_agent_id, _json(data)),
            )

    def get_work_session(self, session_id: str) -> dict[str, Any] | None:
        """Return the registered root/scope ancestry of an execution Session."""
        with self._lock:
            row = self._db.execute(
                "SELECT data FROM work_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def list_work_sessions(
        self, root_agent_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return stored execution identities, optionally limited to one root."""
        with self._lock:
            rows = self._db.execute(
                "SELECT data FROM work_sessions"
                + (" WHERE root_agent_id=?" if root_agent_id else ""),
                (root_agent_id,) if root_agent_id else (),
            ).fetchall()
            return [json.loads(row[0]) for row in rows]

    def get_work_event(self, event_id: str) -> dict[str, Any] | None:
        """Return a durable event by its stable business identity, or None."""
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM work_events WHERE event_id=?", (event_id,)
            ).fetchone()
            return self._event(row) if row is not None else None

    def append_work_event(
        self,
        *,
        event_id: str,
        root_agent_id: str,
        session_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        turn_id: str | None = None,
        source_event_id: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Durably append one event, deduplicating retries by stable identity."""
        with self._lock, self._db:
            return self._append_event(
                event_id=event_id,
                root_agent_id=root_agent_id,
                session_id=session_id,
                event_type=event_type,
                payload=payload,
                turn_id=turn_id,
                source_event_id=source_event_id,
                observed_at=observed_at,
            )

    def _append_event(
        self,
        *,
        event_id: str,
        root_agent_id: str,
        session_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        turn_id: str | None = None,
        source_event_id: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        existing = self._db.execute(
            "SELECT * FROM work_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if existing:
            return self._event(existing)
        self._db.execute(
            """INSERT INTO work_events
            (event_id,root_agent_id,session_id,turn_id,event_type,source_event_id,payload,observed_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                event_id,
                root_agent_id,
                session_id,
                turn_id,
                event_type,
                source_event_id,
                _json(payload),
                observed_at or _now(),
            ),
        )
        return self._event(
            self._db.execute(
                "SELECT * FROM work_events WHERE event_id=?", (event_id,)
            ).fetchone()
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["seq"] = data.pop("journal_seq")
        data["type"] = data.pop("event_type")
        data["payload"] = json.loads(data["payload"])
        return data

    def read_unacked_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the oldest unacknowledged contiguous journal batch."""
        with self._lock:
            rows = self._db.execute(
                """SELECT * FROM work_events WHERE journal_seq >
                (SELECT through_seq FROM work_relay_progress WHERE journal_id=?) ORDER BY journal_seq LIMIT ?""",
                (self.journal_id, limit),
            ).fetchall()
            return [self._event(row) for row in rows]

    def read_work_events(
        self, *, from_seq: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Read a retained journal prefix for IM gap recovery, including ACKed rows."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM work_events WHERE journal_seq >= ? ORDER BY journal_seq LIMIT ?",
                (from_seq, limit),
            ).fetchall()
            return [self._event(row) for row in rows]

    def acknowledge_events(self, through_seq: int) -> None:
        """Advance only an IM-confirmed journal prefix, preserving all records."""
        with self._lock, self._db:
            maximum = self._db.execute(
                "SELECT COALESCE(MAX(journal_seq),0) FROM work_events"
            ).fetchone()[0]
            if through_seq > maximum:
                raise ValueError("Cannot acknowledge beyond the local journal")
            self._db.execute(
                "UPDATE work_relay_progress SET through_seq=MAX(through_seq,?) WHERE journal_id=?",
                (through_seq, self.journal_id),
            )


class GlobalInboxService:
    """Admit input, serve bounded pages, and consume only durable SDK proofs.

    Args:
        store: This Gateway's shared persistent store.
        conversation_reader: Authorized IM query callback; None uses received cache.
        image_materializer: Existing approved attachment resolver. Receives the original
            image descriptor and returns actual SDK image content, or None to retry later.
    """

    def __init__(
        self,
        store: GlobalInboxStore,
        *,
        conversation_reader: Callable[
            [str, str, Mapping[str, Any]], Awaitable[dict[str, Any]]
        ]
        | None = None,
        image_materializer: Callable[
            [Mapping[str, Any]], Awaitable[Mapping[str, Any] | None]
        ]
        | None = None,
    ) -> None:
        self.store = store
        self._conversation_reader = conversation_reader
        self._image_materializer = image_materializer
        self._target_locks: dict[tuple[str, str], asyncio.Lock] = {}

    def target_lock(self, agent_id: str, target: str) -> asyncio.Lock:
        """Return the admission lock shared by target receive and send enqueue."""
        return self._target_locks.setdefault((agent_id, target), asyncio.Lock())

    def get_target(self, agent_id: str, target: str) -> dict[str, Any] | None:
        """Resolve an opaque target to its native or external routing identity."""
        with self.store._lock:
            row = self.store._db.execute(
                "SELECT data FROM inbox_targets WHERE agent_id=? AND target=?",
                (agent_id, target),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def update_target(
        self, agent_id: str, target: str, **fields: Any
    ) -> dict[str, Any]:
        """Update authorized routing/permission facts after shadow materialization."""
        with self.store._lock, self.store._db:
            data = self.get_target(agent_id, target)
            if data is None:
                raise ValueError("target_not_accessible")
            data.update(fields)
            self.store._db.execute(
                "UPDATE inbox_targets SET data=? WHERE agent_id=? AND target=?",
                (_json(data), agent_id, target),
            )
            return data

    def receive(
        self,
        *,
        agent_id: str,
        target: str,
        ingress_key: str,
        source_message_id: str | None,
        sender: Mapping[str, Any],
        content: Sequence[Mapping[str, Any]],
        channel: str = "web",
        kind: str = "group",
        name: str = "",
        conversation_id: str | None = None,
        reply_context: Mapping[str, Any] | None = None,
        source_time: str | None = None,
        attention_reasons: Sequence[str] = (),
        should_process: bool = True,
        normal_live_input: bool = True,
        self_echo: bool = False,
    ) -> dict[str, Any] | None:
        """Persist one ingress identity and effective attention atomically.

        Caller holds target_lock when racing with a target's send admission.
        Self echoes produce no entry; replay cannot promote background attention.
        """
        if self_echo:
            return None
        with self.store._lock, self.store._db:
            db = self.store._db
            duplicate = db.execute(
                "SELECT data FROM inbox_entries WHERE agent_id=? AND ingress_key=?",
                (agent_id, ingress_key),
            ).fetchone()
            if duplicate:
                return json.loads(duplicate[0])
            seq = db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM inbox_entries WHERE agent_id=?",
                (agent_id,),
            ).fetchone()[0]
            now = _now()
            old = self.get_target(agent_id, target) or {}
            target_data = {
                **old,
                "target": target,
                "name": name or old.get("name", target),
                "channel": channel,
                "kind": kind,
                "conversation_id": conversation_id or old.get("conversation_id"),
                "reply_context": reply_context or old.get("reply_context"),
                "permission_status": "allowed",
                "permission_confirmed_at": now,
                "latest_message_at": source_time or now,
            }
            db.execute(
                "INSERT INTO inbox_targets VALUES (?,?,?) ON CONFLICT(agent_id,target) DO UPDATE SET data=excluded.data",
                (agent_id, target, _json(target_data)),
            )
            parts = []
            for index, block in enumerate(content):
                if block.get("type") == "text":
                    text = str(block.get("text", ""))
                    for start in range(0, max(1, len(text)), 24000):
                        parts.append(
                            {
                                "part_key": f"{index}:text:{start}",
                                "content": [
                                    {**block, "text": text[start : start + 24000]}
                                ],
                            }
                        )
                else:
                    parts.append(
                        {
                            "part_key": f"{index}:{block.get('type', 'attachment')}",
                            "content": [dict(block)],
                        }
                    )
            if not parts:
                parts = [
                    {"part_key": "0:text:0", "content": [{"type": "text", "text": ""}]}
                ]
            attention = bool(should_process and normal_live_input)
            data = {
                "seq": seq,
                "target": target,
                "message_id": source_message_id,
                "sender": dict(sender),
                "source_time": source_time,
                "received_at": now,
                "parts": parts,
                "attention_reasons": list(attention_reasons),
                "requires_attention": attention,
                "source": {
                    "channel": channel,
                    "conversation_id": conversation_id,
                    "reply_target": target,
                },
            }
            db.execute(
                "INSERT INTO inbox_entries VALUES (?,?,?,?,?,?,NULL)",
                (agent_id, seq, ingress_key, target, _json(data), int(attention)),
            )
            db.execute(
                "INSERT OR IGNORE INTO inbox_wake_state(agent_id) VALUES (?)",
                (agent_id,),
            )
            if attention:
                db.execute(
                    "UPDATE inbox_wake_state SET latest_signal_seq=? WHERE agent_id=?",
                    (seq, agent_id),
                )
            return data

    def blocking_entries(self, agent_id: str, target: str) -> list[dict[str, Any]]:
        """Return only applicable target messages whose parts are not all read."""
        with self.store._lock:
            rows = self.store._db.execute(
                """SELECT data FROM inbox_entries WHERE agent_id=? AND target=?
                AND requires_attention=1 AND consumed_at IS NULL ORDER BY seq""",
                (agent_id, target),
            ).fetchall()
            return [json.loads(row[0]) for row in rows]

    async def _refresh_source_names(
        self, agent_id: str, targets: Sequence[str]
    ) -> None:
        if self._conversation_reader is None or not targets:
            return
        native = {}
        for target in targets:
            entry = self.get_target(agent_id, target)
            if entry and entry.get("conversation_id"):
                native[entry["conversation_id"]] = target
        if not native:
            return
        try:
            page = await self._conversation_reader(
                agent_id, "describe", {"targets": list(native)}
            )
        except (ConnectionError, TimeoutError):
            return  # Offline received messages retain their last known names.
        for row in page.get("conversations", []):
            if row.get("target") in native:
                self.update_target(
                    agent_id,
                    native[row["target"]],
                    name=row["name"],
                    participants=row["participants"],
                )

    async def execute(
        self,
        tool_name: str,
        *,
        agent_id: str,
        session_id: str,
        tool_call_id: str,
        args: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Execute an authenticated root-only query; reject unrelated identities."""
        binding = self.store.get_global_session(agent_id)
        if not binding or binding["session_id"] != session_id:
            raise ValueError("scope_not_allowed")
        validate_arguments(tool_name, args)
        if tool_name == "inbox":
            with self.store._lock:
                targets = (
                    [
                        row[0]
                        for row in self.store._db.execute(
                            "SELECT DISTINCT target FROM inbox_entries WHERE agent_id=? AND consumed_at IS NULL",
                            (agent_id,),
                        )
                    ]
                    if args["action"] == "check"
                    else [args["target"]]
                )
            await self._refresh_source_names(agent_id, targets)
        if tool_name == "conversations" and self._conversation_reader is not None:
            if args["action"] == "list":
                return await self._combined_list(agent_id, args)
            target = self.get_target(agent_id, str(args.get("target", "")))
            if not target or target.get("conversation_id"):
                try:
                    page = await self._conversation_reader(
                        agent_id,
                        str(args["action"]),
                        {**args, "target": target["conversation_id"]}
                        if target
                        else args,
                    )
                    return await self._materialize_history_page(page)
                except (ConnectionError, TimeoutError):
                    pass
                except ValueError as exc:
                    if "target_not_accessible" in str(exc) and target:
                        self.update_target(
                            agent_id,
                            target["target"],
                            permission_status="revoked",
                            permission_confirmed_at=_now(),
                        )
                    raise
        with self.store._lock, self.store._db:
            action = args["action"]
            if action in ("check", "list"):
                return self._list(agent_id, tool_name, args)
            if args.get("cursor"):
                self._decode_cursor(
                    args["cursor"], agent_id, tool_name, args["target"], "read"
                )
            target = self.get_target(agent_id, args["target"])
            if not target or target.get("permission_status") != "allowed":
                raise ValueError("target_not_accessible")
            if tool_name == "inbox":
                if not tool_call_id:
                    raise ValueError("invalid_arguments: missing tool call identity")
                existing = self._read_receipt_page(agent_id, session_id, tool_call_id)
                if existing is not None:
                    return existing
            high, candidates = self._read_candidates(agent_id, tool_name, args)
            candidates, _ = self._bounded_candidates(candidates, args.get("limit", 20))
        await self._materialize_received_parts(agent_id, candidates)
        with self.store._lock, self.store._db:
            target = self.get_target(agent_id, args["target"])
            if not target or target.get("permission_status") != "allowed":
                raise ValueError("target_not_accessible")
            return self._read(
                agent_id, session_id, tool_call_id, tool_name, args, high=high
            )

    async def _combined_list(
        self, agent: str, args: Mapping[str, Any]
    ) -> dict[str, Any]:
        limit = args.get("limit", 20)
        query = str(args.get("query", ""))
        high = 0
        if args.get("cursor"):
            high, state = self._decode_cursor(
                args["cursor"], agent, "conversations", query, "list"
            )
            if isinstance(state, int):
                with self.store._lock, self.store._db:
                    return self._list(agent, "conversations", args)
            if not isinstance(state, dict):
                raise ValueError("invalid_cursor")
        else:
            with self.store._lock, self.store._db:
                local_args = {**args, "limit": 50}
                local_page = self._list(agent, "conversations", local_args)
                local = local_page["conversations"]
                while local_page["has_more"]:
                    local_page = self._list(
                        agent,
                        "conversations",
                        {**local_args, "cursor": local_page["next_cursor"]},
                    )
                    local.extend(local_page["conversations"])
            state = {
                "local": [
                    item for item in local if item["target"].startswith("local:")
                ],
                "remote": [],
                "remote_cursor": None,
                "remote_more": True,
            }
        if state["remote_more"] and len(state["remote"]) < limit:
            remote_args = {key: value for key, value in args.items() if key != "cursor"}
            remote_args["limit"] = limit
            if state["remote_cursor"]:
                remote_args["cursor"] = state["remote_cursor"]
            try:
                page = await self._conversation_reader(agent, "list", remote_args)
            except (ConnectionError, TimeoutError):
                with self.store._lock, self.store._db:
                    return self._list(
                        agent,
                        "conversations",
                        {key: value for key, value in args.items() if key != "cursor"},
                    )
            state["remote"].extend(page["conversations"])
            state["remote_cursor"] = page.get("next_cursor")
            state["remote_more"] = bool(page.get("has_more"))
        merged = {item["target"]: item for item in [*state["local"], *state["remote"]]}
        ordered = sorted(merged.values(), key=lambda item: item["target"])
        ordered.sort(key=lambda item: item.get("latest_message_at") or "", reverse=True)
        selected = ordered[:limit]
        targets = {item["target"] for item in selected}
        state["local"] = [
            item for item in state["local"] if item["target"] not in targets
        ]
        state["remote"] = [
            item for item in state["remote"] if item["target"] not in targets
        ]
        more = bool(state["local"] or state["remote"] or state["remote_more"])
        with self.store._lock, self.store._db:
            return {
                "conversations": selected,
                "has_more": more,
                "next_cursor": self._cursor(
                    agent, "conversations", query, "list", high, state
                )
                if more
                else None,
            }

    def _cursor(
        self, agent: str, tool: str, target: str, action: str, high: int, position: Any
    ) -> str:
        # Persist opaque cursor state: caller input cannot forge a returned page
        # or extend its original snapshot to messages that arrived afterwards.
        cursor = "v1:" + uuid4().hex
        with self.store._lock:
            self.store._db.execute(
                "INSERT INTO inbox_page_cursors VALUES (?,?)",
                (cursor, _json([1, agent, tool, target, action, high, position])),
            )
        return cursor

    def _decode_cursor(
        self, cursor: str, agent: str, tool: str, target: str, action: str
    ) -> tuple[int, Any]:
        with self.store._lock:
            row = self.store._db.execute(
                "SELECT data FROM inbox_page_cursors WHERE cursor_id=?", (cursor,)
            ).fetchone()
        if row is None:
            raise ValueError("invalid_cursor")
        value = json.loads(row[0])
        if value[:5] != [1, agent, tool, target, action]:
            raise ValueError("invalid_cursor")
        return value[5], value[6]

    def _list(self, agent: str, tool: str, args: Mapping[str, Any]) -> dict[str, Any]:
        db = self.store._db
        high = db.execute(
            "SELECT COALESCE(MAX(seq),0) FROM inbox_entries WHERE agent_id=?", (agent,)
        ).fetchone()[0]
        position = None
        if args.get("cursor"):
            high, position = self._decode_cursor(
                args["cursor"], agent, tool, str(args.get("query", "")), args["action"]
            )
        if position is not None and not isinstance(position, dict):
            raise ValueError("invalid_cursor")
        rows = db.execute(
            "SELECT data FROM inbox_targets WHERE agent_id=?", (agent,)
        ).fetchall()
        results = []
        for row in rows:
            target = json.loads(row[0])
            if target.get("permission_status") != "allowed":
                continue
            entries = [
                json.loads(r[0])
                for r in db.execute(
                    """SELECT data FROM inbox_entries WHERE agent_id=?
                AND target=? AND seq<=?"""
                    + (" AND consumed_at IS NULL" if tool == "inbox" else "")
                    + " ORDER BY seq",
                    (agent, target["target"], high),
                ).fetchall()
            ]
            if not entries:
                continue
            item = {key: target[key] for key in ("target", "name", "kind", "channel")}
            if tool == "inbox":
                item.update(
                    pending_count=len(entries),
                    latest_message_at=entries[-1]["source_time"]
                    or entries[-1]["received_at"],
                    attention_reasons=sorted(
                        {r for e in entries for r in e["attention_reasons"]}
                    ),
                    oldest_received_at=entries[0]["received_at"],
                    latest_received_at=entries[-1]["received_at"],
                )
            else:
                item.update(
                    participants=target.get("participants", []),
                    latest_message_at=entries[-1]["source_time"]
                    or entries[-1]["received_at"],
                    history_availability="received_only",
                    permission_confirmed_at=target["permission_confirmed_at"],
                )
                query = str(args.get("query", "")).casefold()
                if (
                    query
                    and query
                    not in (item["name"] + _json(item["participants"])).casefold()
                ):
                    continue
            results.append(item)
        results.sort(
            key=lambda item: (
                (item["oldest_received_at"], item["target"])
                if tool == "inbox"
                else item["target"]
            )
        )
        if tool != "inbox":
            results.sort(key=lambda item: item["latest_message_at"], reverse=True)
        limit = args.get("limit", len(results) if tool == "inbox" else 20)
        # Freeze source order, not the shrinking unread result list. A previous
        # page may have been consumed while this cursor was held by the Agent.
        targets = (
            position["targets"] if position else [item["target"] for item in results]
        )
        offset = position["offset"] if position else 0
        lookup = {item["target"]: item for item in results}
        selected = []
        budget = 24000
        while offset < len(targets) and len(selected) < limit:
            item = lookup.get(targets[offset])
            if item and tool == "inbox":
                cost = len(_json(source_summary(item)))
                if selected and cost > budget:
                    break
                budget -= cost
            offset += 1
            if item:
                selected.append(item)
        has_more = any(target in lookup for target in targets[offset:])
        return {
            "conversations": selected,
            "has_more": has_more,
            "next_cursor": self._cursor(
                agent,
                tool,
                str(args.get("query", "")),
                args["action"],
                high,
                {"targets": targets, "offset": offset},
            )
            if has_more
            else None,
        }

    def _read_receipt_page(
        self, agent: str, session: str, call: str
    ) -> dict[str, Any] | None:
        row = self.store._db.execute(
            "SELECT page FROM inbox_read_receipts WHERE agent_id=? AND session_id=? AND tool_call_id=?",
            (agent, session, call),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def _read_candidates(
        self, agent: str, tool: str, args: Mapping[str, Any], *, high: int | None = None
    ) -> tuple[int, list]:
        db = self.store._db
        if high is None:
            high = db.execute(
                "SELECT COALESCE(MAX(seq),0) FROM inbox_entries WHERE agent_id=?",
                (agent,),
            ).fetchone()[0]
        position = [0, 0]
        if args.get("cursor"):
            high, position = self._decode_cursor(
                args["cursor"], agent, tool, args["target"], "read"
            )
        entries = [
            json.loads(row[0])
            for row in db.execute(
                """SELECT data FROM inbox_entries
            WHERE agent_id=? AND target=? AND seq<=?"""
                + (" AND consumed_at IS NULL" if tool == "inbox" else "")
                + " ORDER BY seq",
                (agent, args["target"], high),
            ).fetchall()
        ]
        if args.get("before_message_id"):
            matches = [
                e["seq"]
                for e in entries
                if e["message_id"] == args["before_message_id"]
            ]
            if not matches:
                raise ValueError("invalid_arguments: message is not in target history")
            entries = [e for e in entries if e["seq"] < matches[0]]
        candidates = []
        for entry in entries:
            consumed = (
                {
                    row[0]
                    for row in db.execute(
                        "SELECT part_key FROM inbox_consumed_parts WHERE agent_id=? AND entry_seq=?",
                        (agent, entry["seq"]),
                    )
                }
                if tool == "inbox"
                else set()
            )
            for index, part in enumerate(entry["parts"]):
                if [entry["seq"], index] >= position and part[
                    "part_key"
                ] not in consumed:
                    candidates.append((entry, index, part))
        return high, candidates

    @staticmethod
    def _bounded_candidates(
        candidates: list, limit: int
    ) -> tuple[list, list[int] | None]:
        selected = []
        chars = images = 0
        seen = set()
        for entry, index, part in candidates:
            text_size = sum(
                len(str(block.get("text", "")))
                if block.get("type") == "text"
                else len(_json(block))
                if block.get("type") != "image"
                else 0
                for block in part["content"]
            )
            image_count = sum(block.get("type") == "image" for block in part["content"])
            if (
                chars + text_size > 24000
                or images + image_count > 4
                or (entry["seq"] not in seen and len(seen) >= limit)
            ):
                return selected, [entry["seq"], index]
            chars += text_size
            images += image_count
            seen.add(entry["seq"])
            selected.append((entry, index, part))
        return selected, None

    @staticmethod
    def _has_image_locator(block: Mapping[str, Any]) -> bool:
        attachment = block.get("attachment")
        descriptor = attachment if isinstance(attachment, Mapping) else block
        return isinstance(descriptor.get("url"), str) and bool(
            descriptor["url"].strip()
        )

    async def _materialize_image(
        self, block: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        if self._image_materializer is None or not self._has_image_locator(block):
            return None
        try:
            resolved = await self._image_materializer(json.loads(_json(block)))
        except Exception:
            # A failed fetch cannot turn an unread image into a consumed placeholder.
            return None
        if (
            not isinstance(resolved, Mapping)
            or resolved.get("type") != "image"
            or not isinstance(resolved.get("source"), Mapping)
            or not resolved["source"]
        ):
            return None
        result = {**block, **resolved}
        result.pop("error", None)
        return result

    async def _materialize_received_parts(self, agent: str, candidates: list) -> None:
        for entry, index, part in candidates:
            for block_index, block in enumerate(part["content"]):
                if (
                    block.get("type") != "image"
                    or (block.get("source") or {}).get("type") == "base64"
                ):
                    continue
                materialized = await self._materialize_image(block)
                if materialized is None:
                    continue
                with self.store._lock, self.store._db:
                    db = self.store._db
                    row = db.execute(
                        "SELECT data FROM inbox_entries WHERE agent_id=? AND seq=?",
                        (agent, entry["seq"]),
                    ).fetchone()
                    consumed = db.execute(
                        """SELECT 1 FROM inbox_consumed_parts
                        WHERE agent_id=? AND entry_seq=? AND part_key=?""",
                        (agent, entry["seq"], part["part_key"]),
                    ).fetchone()
                    if row is None or consumed:
                        continue
                    current = json.loads(row[0])
                    current_part = current["parts"][index]
                    # A concurrent read may already have materialized or consumed this
                    # part. Never replace content that another immutable receipt saw.
                    if (
                        current_part["part_key"] != part["part_key"]
                        or current_part["content"][block_index] != block
                    ):
                        continue
                    current_part["content"][block_index] = materialized
                    db.execute(
                        "UPDATE inbox_entries SET data=? WHERE agent_id=? AND seq=?",
                        (_json(current), agent, entry["seq"]),
                    )

    async def _materialize_history_page(
        self, page: Mapping[str, Any]
    ) -> dict[str, Any]:
        result = json.loads(_json(page))
        errors = list(result.get("errors", []))
        for message in result.get("messages", []):
            content = []
            for block in message.get("content", []):
                if (
                    block.get("type") != "image"
                    or (block.get("source") or {}).get("type") == "base64"
                ):
                    content.append(block)
                    continue
                resolved = await self._materialize_image(block)
                if resolved is not None:
                    content.append(resolved)
                else:
                    errors.append(
                        {
                            "code": "attachment_unavailable",
                            "message_id": message.get("message_id"),
                            "part_key": message.get("part_key"),
                            "retryable": self._has_image_locator(block),
                        }
                    )
                    message["complete_message"] = False
            message["content"] = content
        if errors:
            result["errors"] = errors
        return result

    def _read(
        self,
        agent: str,
        session: str,
        call: str,
        tool: str,
        args: Mapping[str, Any],
        *,
        high: int | None = None,
    ) -> dict[str, Any]:
        db = self.store._db
        if tool == "inbox":
            old = self._read_receipt_page(agent, session, call)
            if old is not None:
                return old
            if not call:
                raise ValueError("invalid_arguments: missing tool call identity")
        high, candidates = self._read_candidates(agent, tool, args, high=high)
        candidates, remaining = self._bounded_candidates(
            candidates, args.get("limit", 20)
        )
        messages, selected, errors = [], [], []
        target_info = self.get_target(agent, args["target"])
        people = {
            identity: participant
            for participant in target_info.get("participants", [])
            for identity in (participant.get("id"), participant.get("agent_id"))
            if identity
        }
        returned_parts: dict[int, int] = {}
        total_parts: dict[int, int] = {}
        for entry, index, part in candidates:
            if any(
                b.get("type") == "image"
                and (b.get("source") or {}).get("type") != "base64"
                for b in part["content"]
            ):
                errors.append(
                    {
                        "code": "attachment_unavailable",
                        "message_id": entry["message_id"],
                        "part_key": part["part_key"],
                        "retryable": any(
                            self._has_image_locator(block) for block in part["content"]
                        ),
                    }
                )
                continue
            sender = entry["sender"]
            person = people.get(sender.get("id"))
            if person:
                sender = {
                    **sender,
                    "id": person.get("agent_id") or person["id"],
                    "name": person["name"],
                }
            returned_parts[entry["seq"]] = returned_parts.get(entry["seq"], 0) + 1
            total_parts[entry["seq"]] = len(entry["parts"])
            messages.append(
                {
                    **{
                        k: entry[k]
                        for k in (
                            "message_id",
                            "sender",
                            "source_time",
                            "received_at",
                            "source",
                        )
                    },
                    **part,
                    "entry_seq": entry["seq"],
                    "sender": sender,
                }
            )
            selected.append([entry["seq"], part["part_key"]])
        for message in messages:
            message["complete_message"] = (
                returned_parts[message["entry_seq"]]
                == total_parts[message["entry_seq"]]
            )
        page = {
            "target": args["target"],
            "name": target_info.get("name"),
            "messages": messages,
            "has_more": remaining is not None,
            "next_cursor": self._cursor(
                agent, tool, args["target"], "read", high, remaining
            )
            if remaining is not None
            else None,
        }
        if tool != "inbox":
            page.pop("name", None)
            for message in messages:
                message.pop("entry_seq", None)
        if errors:
            page["errors"] = errors
        if tool == "inbox":
            page["receipt_id"] = uuid4().hex
            db.execute(
                "INSERT INTO inbox_read_receipts VALUES (?,?,?,?,?,?,?,NULL)",
                (
                    agent,
                    session,
                    call,
                    page["receipt_id"],
                    _json(selected),
                    content_digest(serialize_inbox_page(page)),
                    _json(page),
                ),
            )
        else:
            page["history_scope"] = "received_only"
            page["permission_confirmed_at"] = self.get_target(agent, args["target"])[
                "permission_confirmed_at"
            ]
        return page

    def confirm_committed_read(self, proof: Mapping[str, Any]) -> bool:
        """Commit server-selected parts only when durable SDK content matches.

        Returns:
            Whether this proof newly committed a receipt. Replays are no-ops.
        """
        if (
            proof.get("name") != "inbox"
            or proof.get("is_error") is not False
            or proof.get("serialization_status") != "succeeded"
        ):
            return False
        with self.store._lock, self.store._db:
            db = self.store._db
            row = db.execute(
                """SELECT r.* FROM inbox_read_receipts r JOIN global_sessions s
                ON r.agent_id=s.agent_id AND r.session_id=s.session_id WHERE r.session_id=? AND r.tool_call_id=?""",
                (proof.get("session_id"), proof.get("tool_call_id")),
            ).fetchone()
            if (
                not row
                or row["committed_at"]
                or row["content_digest"] != proof.get("content_digest")
            ):
                return False
            now = _now()
            selected = json.loads(row["entries_and_parts"])
            for seq, part in selected:
                db.execute(
                    "INSERT OR IGNORE INTO inbox_consumed_parts VALUES (?,?,?)",
                    (row["agent_id"], seq, part),
                )
                entry = json.loads(
                    db.execute(
                        "SELECT data FROM inbox_entries WHERE agent_id=? AND seq=?",
                        (row["agent_id"], seq),
                    ).fetchone()[0]
                )
                count = db.execute(
                    "SELECT COUNT(*) FROM inbox_consumed_parts WHERE agent_id=? AND entry_seq=?",
                    (row["agent_id"], seq),
                ).fetchone()[0]
                if count == len(entry["parts"]):
                    db.execute(
                        "UPDATE inbox_entries SET consumed_at=? WHERE agent_id=? AND seq=?",
                        (now, row["agent_id"], seq),
                    )
            db.execute(
                "UPDATE inbox_read_receipts SET committed_at=? WHERE receipt_id=?",
                (now, row["receipt_id"]),
            )
            self.store._append_event(
                event_id="inbox-read:" + row["receipt_id"],
                root_agent_id=row["agent_id"],
                session_id=row["session_id"],
                turn_id=proof.get("turn_id"),
                event_type="inbox_read_committed",
                payload={
                    "receipt_id": row["receipt_id"],
                    "tool_call_id": row["tool_call_id"],
                    "entries_and_parts": selected,
                    "message_id": proof.get("message_id"),
                    "source_refs": [
                        {
                            "conversation_id": item["source"].get("conversation_id"),
                            "target": item["source"]["reply_target"],
                            "message_id": item["message_id"],
                        }
                        for item in json.loads(row["page"])["messages"]
                    ],
                },
            )
            return True
