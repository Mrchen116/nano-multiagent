"""Persist authenticated Agent work journals and their shared HTTP/live projection."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from IM.infra.repositories.agents import AgentProfileRepository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_work_query_snapshots (
 snapshot_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_work_journals (
 node_id TEXT, journal_id TEXT, through_seq INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(node_id,journal_id));
CREATE TABLE IF NOT EXISTS agent_work_events (
 revision INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, journal_id TEXT, seq INTEGER,
 event_id TEXT UNIQUE NOT NULL, root_agent_id TEXT NOT NULL, session_id TEXT NOT NULL,
 turn_id TEXT, type TEXT NOT NULL, observed_at TEXT, payload TEXT NOT NULL,
 UNIQUE(node_id,journal_id,seq));
CREATE TABLE IF NOT EXISTS agent_work_sessions (
 session_id TEXT PRIMARY KEY, root_agent_id TEXT NOT NULL, node_id TEXT NOT NULL,
 scope TEXT NOT NULL, parent_session_id TEXT, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_work_turns (
 session_id TEXT, turn_id TEXT, seq INTEGER, payload TEXT NOT NULL,
 PRIMARY KEY(session_id,turn_id));
CREATE TABLE IF NOT EXISTS agent_work_items (
 session_id TEXT, turn_id TEXT, item_id TEXT, seq INTEGER, kind TEXT,
 observed_at TEXT, payload TEXT NOT NULL, revision INTEGER,
 PRIMARY KEY(session_id,turn_id,item_id));
"""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invalid_arguments")
    return value


class AgentWorkRepository:
    """Store contiguous journal batches atomically; never infer a missing execution."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection
        self.db.executescript(_SCHEMA)

    def session(self, root: str, session: str) -> dict[str, Any]:
        """Return only a Session proven to belong to this root."""
        row = self.db.execute(
            "SELECT * FROM agent_work_sessions WHERE root_agent_id=? AND session_id=?",
            (root, session),
        ).fetchone()
        if row is None:
            raise ValueError("scope_not_allowed")
        return {**json.loads(row["payload"]), **dict(row)}

    def append(
        self, *, node_id: str, journal_id: str, from_seq: int, events: list[dict]
    ) -> dict:
        """Commit one complete valid batch or return the missing contiguous sequence.

        Raises:
            ValueError: Invalid identity or a batch item conflicts with durable ownership.
        """
        _text(journal_id)
        row = self.db.execute(
            "SELECT through_seq FROM agent_work_journals WHERE node_id=? AND journal_id=?",
            (node_id, journal_id),
        ).fetchone()
        through = int(row[0]) if row else 0
        if from_seq > through + 1:
            return {
                "journal_id": journal_id,
                "through_seq": through,
                "expected_seq": through + 1,
            }
        if not events or len(events) > 100:
            raise ValueError("invalid_arguments")
        with self.db:
            for offset, event in enumerate(events):
                seq = event["seq"]
                if seq != from_seq + offset:
                    raise ValueError("invalid_sequence")
                root = _text(event.get("root_agent_id"))
                session = _text(event.get("session_id"))
                profile = AgentProfileRepository(self.db).get_profile(agent_id=root)
                if (
                    profile is None
                    or profile.node_id != node_id
                    or profile.work_mode != "global"
                    or profile.is_stale
                ):
                    raise ValueError("scope_not_allowed")
                event_id = _text(event.get("event_id"))
                kind = _text(event.get("type"))
                payload = event.get("payload")
                if not isinstance(payload, dict):
                    raise ValueError("invalid_arguments")
                old = self.db.execute(
                    "SELECT event_id,root_agent_id,session_id,payload FROM agent_work_events WHERE node_id=? AND journal_id=? AND seq=?",
                    (node_id, journal_id, seq),
                ).fetchone()
                if old:
                    if tuple(old) != (event_id, root, session, _json(payload)):
                        raise ValueError("event_identity_conflict")
                    continue
                if seq != through + 1:
                    raise ValueError("invalid_sequence")
                if kind == "session_registered":
                    self._register(root, session, node_id, payload)
                else:
                    self.session(root, session)
                if kind == "session_linked":
                    if payload.get("parent_session_id") != session:
                        raise ValueError("scope_not_allowed")
                    self._register(
                        root,
                        _text(payload.get("child_session_id")),
                        node_id,
                        {
                            **payload,
                            "scope": "workflow"
                            if payload.get("workflow_run_id")
                            else "subagent",
                            "parent_session_id": session,
                        },
                    )
                cursor = self.db.execute(
                    "INSERT INTO agent_work_events(node_id,journal_id,seq,event_id,root_agent_id,session_id,turn_id,type,observed_at,payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        node_id,
                        journal_id,
                        seq,
                        event_id,
                        root,
                        session,
                        event.get("turn_id"),
                        kind,
                        event.get("observed_at"),
                        _json(payload),
                    ),
                )
                revision = cursor.lastrowid
                self._project(event, revision)
                through = seq
            self.db.execute(
                "INSERT INTO agent_work_journals VALUES (?,?,?) ON CONFLICT(node_id,journal_id) DO UPDATE SET through_seq=excluded.through_seq",
                (node_id, journal_id, through),
            )
        return {"journal_id": journal_id, "through_seq": through}

    def _register(self, root: str, session: str, node: str, payload: dict) -> None:
        scope = payload.get("scope")
        if scope not in {"global_main", "subagent", "workflow", "cron"}:
            raise ValueError("invalid_scope")
        parent = payload.get("parent_session_id")
        if scope in {"subagent", "workflow"}:
            self.session(root, _text(parent))
        old = self.db.execute(
            "SELECT root_agent_id,node_id,scope,parent_session_id FROM agent_work_sessions WHERE session_id=?",
            (session,),
        ).fetchone()
        if old and tuple(old) != (root, node, scope, parent):
            raise ValueError("session_identity_conflict")
        if scope == "global_main":
            other = self.db.execute(
                "SELECT session_id FROM agent_work_sessions WHERE root_agent_id=? AND scope='global_main'",
                (root,),
            ).fetchone()
            if other and other[0] != session:
                raise ValueError("main_session_conflict")
        self.db.execute(
            "INSERT INTO agent_work_sessions VALUES (?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload",
            (session, root, node, scope, parent, _json(payload)),
        )

    def _project(self, event: dict, revision: int) -> None:
        session = event["session_id"]
        turn_id = event.get("turn_id")
        kind = event["type"]
        p = event["payload"]
        if (
            not turn_id
            and p.get("run_id")
            and kind not in {"cron_trigger", "cron_delivery"}
        ):
            matched = self.db.execute(
                "SELECT turn_id FROM agent_work_turns WHERE session_id=? AND json_extract(payload,'$.run_id')=? ORDER BY seq DESC LIMIT 1",
                (session, p["run_id"]),
            ).fetchone()
            if matched:
                turn_id = matched["turn_id"]
        if not turn_id:
            if kind in {
                "control_result",
                "recording_degraded",
                "model_fallback",
                "cron_trigger",
                "cron_delivery",
            }:
                self.db.execute(
                    "INSERT INTO agent_work_items VALUES (?,?,?,?,?,?,?,?)",
                    (
                        session,
                        "",
                        event["event_id"],
                        revision,
                        kind,
                        event.get("observed_at"),
                        _json(p),
                        revision,
                    ),
                )
            return
        row = self.db.execute(
            "SELECT seq,payload FROM agent_work_turns WHERE session_id=? AND turn_id=?",
            (session, turn_id),
        ).fetchone()
        turn = (
            json.loads(row["payload"])
            if row
            else {
                "session_id": session,
                "turn_id": turn_id,
                "status": "unknown",
                "usage": None,
                "source_refs": [],
            }
        )
        if kind == "inbox_wake_admitted":
            turn["trigger"] = {"kind": "inbox", "submission_id": p.get("submission_id")}
        if kind in {"turn_started", "turn_start"}:
            turn.update(
                status="running",
                origin=p.get("origin"),
                trigger=p.get("trigger"),
                model_id=p.get("model_id") or p.get("model"),
                run_id=p.get("run_id"),
                started_at=p.get("started_at") or event.get("observed_at"),
            )
            admitted = self.db.execute(
                "SELECT payload FROM agent_work_events WHERE session_id=? AND type='inbox_wake_admitted' AND json_extract(payload,'$.run_id')=? ORDER BY revision DESC LIMIT 1",
                (session, p.get("run_id")),
            ).fetchone()
            if admitted:
                turn["trigger"] = {
                    "kind": "inbox",
                    "submission_id": json.loads(admitted[0]).get("submission_id"),
                }
        if kind in {"turn_end", "run_completed", "run_failed", "run_cancelled"}:
            stop = p.get("stop_reason")
            terminal = p.get("status") or (
                "interrupted"
                if stop in {"cancelled", "aborted", "interrupted"}
                or kind == "run_cancelled"
                else "failed"
                if p.get("completed") is False or p.get("error") or kind == "run_failed"
                else "completed"
            )
            turn.update(
                status=terminal,
                finished_at=p.get("finished_at") or event.get("observed_at"),
                elapsed_ms=p.get("elapsed_ms", p.get("duration_ms")),
                model_id=p.get("model") or turn.get("model_id"),
            )
            if isinstance(p.get("usage"), dict):
                u = p["usage"]
                turn["usage"] = {
                    **u,
                    "context_used": u.get("context_used", u.get("prompt_tokens")),
                    "output": u.get("output", u.get("completion_tokens")),
                    "context_window": p.get("context_window", u.get("context_window")),
                }
        if kind == "turn_input_committed" and p.get("submission_id"):
            admitted = self.db.execute(
                "SELECT payload FROM agent_work_events WHERE session_id=? AND type='inbox_wake_admitted' AND json_extract(payload,'$.submission_id')=? LIMIT 1",
                (session, p["submission_id"]),
            ).fetchone()
            if admitted:
                turn["trigger"] = {"kind": "inbox", "submission_id": p["submission_id"]}
        if kind == "permission_request":
            turn["status"] = "waiting_permission"
        if kind == "permission_resolved" and turn["status"] == "waiting_permission":
            other_pending = self.db.execute(
                "SELECT 1 FROM agent_work_items WHERE session_id=? AND turn_id=? AND kind='permission' AND item_id!=? AND json_extract(payload,'$.status')='pending' LIMIT 1",
                (session, turn_id, f"permission:{p.get('request_id')}"),
            ).fetchone()
            turn["status"] = "waiting_permission" if other_pending else "running"
        if p.get("source_refs"):
            turn["source_refs"] = p["source_refs"]
        self.db.execute(
            "INSERT INTO agent_work_turns VALUES (?,?,?,?) ON CONFLICT(session_id,turn_id) DO UPDATE SET payload=excluded.payload",
            (session, turn_id, row["seq"] if row else revision, _json(turn)),
        )
        if kind in {
            "turn_started",
            "turn_start",
            "turn_end",
            "tool_result_committed",
            "turn_input_committed",
            "run_heartbeat",
            "inbox_wake_admitted",
        }:
            return
        call = p.get("call_id") or p.get("tool_call_id")
        item_kind = (
            "tool"
            if kind
            in {
                "tool_start",
                "tool_end",
                "draft_withheld",
                "message_sent",
                "dispatch_confirmed",
                "inbox_read_committed",
            }
            and call
            else "permission"
            if kind in {"permission_request", "permission_resolved"}
            else kind
        )
        item_id = (
            f"tool:{call}"
            if item_kind == "tool"
            else f"permission:{p.get('request_id')}"
            if item_kind == "permission"
            else f"message:{p.get('message_id')}"
            if kind in {"message", "message_delta", "text_delta"}
            and p.get("message_id")
            else event["event_id"]
        )
        old = self.db.execute(
            "SELECT seq,payload FROM agent_work_items WHERE session_id=? AND turn_id=? AND item_id=?",
            (session, turn_id, item_id),
        ).fetchone()
        payload = json.loads(old["payload"]) if old else {}
        if item_kind == "tool":
            if kind in {"tool_start", "tool_end"}:
                payload.update(p)
                payload["input"] = p.get("arguments") or payload.get("input", {})
                payload["reason"] = p.get("reason_code")
                payload.update(
                    id=call,
                    status="running"
                    if kind == "tool_start"
                    else "failed"
                    if p.get("error") or p.get("is_error")
                    else "completed",
                )
                presentation = p.get("presentation") or {}
                payload["output"] = presentation.get("summary", payload.get("output"))
                for key in ("label", "summary", "detail", "emoji"):
                    if key in presentation:
                        payload[key] = presentation[key]
                payload["name"] = (
                    p.get("name") or p.get("tool_name") or payload.get("name", "tool")
                )
            else:
                payload.setdefault("work_facts", []).append({"type": kind, **p})
        elif item_kind == "permission":
            payload.update(p.get("permission_request", p))
            payload["status"] = (
                "resolved" if kind == "permission_resolved" else "pending"
            )
        else:
            if kind in {"message_delta", "text_delta"}:
                payload["text"] = str(payload.get("text", "")) + str(
                    p.get("text") or p.get("delta") or ""
                )
            else:
                payload.update(p)
        seq = old["seq"] if old else revision
        payload["seq"] = seq
        self.db.execute(
            "INSERT INTO agent_work_items VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(session_id,turn_id,item_id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision",
            (
                session,
                turn_id,
                item_id,
                seq,
                item_kind,
                event.get("observed_at"),
                _json(payload),
                revision,
            ),
        )

    def items(
        self, root: str, session: str, turn: str, after_seq: int = 0, limit: int = 100
    ) -> dict:
        """Read a stable, bounded item page after verifying root membership."""
        self.session(root, session)
        rows = self.db.execute(
            "SELECT * FROM agent_work_items WHERE session_id=? AND turn_id=? AND seq>? ORDER BY seq LIMIT ?",
            (session, turn, after_seq, limit + 1),
        ).fetchall()
        return {
            "items": [
                {
                    **{
                        k: r[k]
                        for k in ("item_id", "seq", "kind", "observed_at", "revision")
                    },
                    "payload": json.loads(r["payload"]),
                }
                for r in rows[:limit]
            ],
            "next_cursor": str(rows[limit - 1]["seq"]) if len(rows) > limit else None,
        }

    def turns(
        self, root: str, session: str, before_turn: str | None = None, limit: int = 20
    ) -> dict:
        """Read newest turns without mixing child usage into the parent."""
        registered = self.session(root, session)
        before = 2**63 - 1
        if before_turn:
            anchor = self.db.execute(
                "SELECT seq FROM agent_work_turns WHERE session_id=? AND turn_id=?",
                (session, before_turn),
            ).fetchone()
            if not anchor:
                raise ValueError("invalid_cursor")
            before = anchor[0]
        rows = self.db.execute(
            "SELECT * FROM agent_work_turns WHERE session_id=? AND seq<? ORDER BY seq DESC LIMIT ?",
            (session, before, limit + 1),
        ).fetchall()
        turns = []
        for row in rows[:limit]:
            turn = json.loads(row["payload"])
            turn["scope"] = registered["scope"]
            if registered["scope"] == "subagent":
                # The same child can resume many times; bind the title to the
                # launch preceding this turn, not the Session's first description.
                launch = self.db.execute(
                    "SELECT payload FROM agent_work_items WHERE session_id=? "
                    "AND kind='tool' AND seq<=? "
                    "AND json_extract(payload,'$.name')='agent' "
                    "AND COALESCE(json_extract(payload,'$.detail.agent_id'), "
                    "json_extract(payload,'$.input.agent_id'))=? "
                    "AND COALESCE(json_extract(payload,'$.detail.status'),'') "
                    "!= 'message_queued' ORDER BY seq DESC LIMIT 1",
                    (
                        registered["parent_session_id"],
                        row["seq"],
                        registered.get("child_agent_id"),
                    ),
                ).fetchone()
                if launch:
                    payload = json.loads(launch["payload"])
                    turn["description"] = (payload.get("input") or {}).get(
                        "description"
                    ) or (payload.get("detail") or {}).get("description")
            if registered["scope"] == "cron":
                turn["job_id"] = registered.get("job_id")
                turn["trigger"] = {
                    "kind": "cron",
                    "source": registered.get("trigger"),
                }
            page = self.items(root, session, row["turn_id"])
            turns.append(
                {
                    **turn,
                    "items": page["items"],
                    "next_items_cursor": page["next_cursor"],
                }
            )
        return {
            "turns": turns,
            "control_items": self.items(root, session, "")["items"],
            "next_cursor": rows[limit - 1]["turn_id"] if len(rows) > limit else None,
        }

    def revision(self, root: str) -> int:
        """Return the latest persisted revision without loading work-view content."""
        return self.db.execute(
            "SELECT COALESCE(MAX(revision),0) FROM agent_work_events WHERE root_agent_id=?",
            (root,),
        ).fetchone()[0]

    def view(self, root: str, before_turn: str | None = None, limit: int = 20) -> dict:
        """Read the root work overview and latest reported main usage."""
        rows = self.db.execute(
            "SELECT * FROM agent_work_sessions WHERE root_agent_id=?", (root,)
        ).fetchall()
        main = next(
            (r["session_id"] for r in rows if r["scope"] == "global_main"), None
        )
        page = (
            self.turns(root, main, before_turn, limit)
            if main
            else {"turns": [], "next_cursor": None}
        )
        revision = self.revision(root)
        latest = None
        if main:
            for row in self.db.execute(
                "SELECT payload FROM agent_work_turns WHERE session_id=? ORDER BY seq DESC",
                (main,),
            ):
                t = json.loads(row[0])
                if t.get("usage"):
                    latest = {
                        "session_id": main,
                        "turn_id": t["turn_id"],
                        "model_id": t.get("model_id"),
                        **t["usage"],
                    }
                    break
        return {
            "root_agent_id": root,
            "main_session_id": main,
            "revision": revision,
            "latest_main_usage": latest,
            "main_execution": (
                "idle"
                if page["turns"][0]["status"] in {"completed", "failed", "interrupted"}
                else page["turns"][0]["status"]
            )
            if page["turns"]
            else "idle",
            "control_items": self.items(root, main, "")["items"] if main else [],
            "other_executions": [
                {
                    key: value
                    for key, value in {**json.loads(r["payload"]), **dict(r)}.items()
                    if key
                    in {
                        "session_id",
                        "root_agent_id",
                        "scope",
                        "parent_session_id",
                        "parent_tool_call_id",
                        "child_agent_id",
                        "workflow_run_id",
                        "description",
                        "title",
                        "status",
                        "job_id",
                        "trigger",
                    }
                }
                for r in rows
                if r["scope"] != "global_main"
            ],
            **page,
        }

    def pending_permission(self, root: str, request: str) -> dict:
        """Resolve a browser request through persisted root and Session ownership."""
        rows = self.db.execute(
            "SELECT i.session_id,i.turn_id,i.payload FROM agent_work_items i JOIN agent_work_sessions s USING(session_id) WHERE s.root_agent_id=? AND i.item_id=?",
            (root, f"permission:{request}"),
        ).fetchall()
        for row in rows:
            payload = json.loads(row["payload"])
            turn = self.db.execute(
                "SELECT payload FROM agent_work_turns WHERE session_id=? AND turn_id=?",
                (row["session_id"], row["turn_id"]),
            ).fetchone()
            if (
                payload.get("status") == "pending"
                and turn
                and json.loads(turn[0]).get("status")
                in {"running", "waiting_permission", "unknown"}
            ):
                return {
                    **payload,
                    "session_id": row["session_id"],
                    "turn_id": row["turn_id"],
                }
        raise ValueError("request_ended")

    def mark_active_unknown(self) -> None:
        """Mark unfinished execution unknown after an IM process restart."""
        with self.db:
            for row in self.db.execute(
                "SELECT session_id,turn_id,payload FROM agent_work_turns"
            ).fetchall():
                payload = json.loads(row["payload"])
                if payload.get("status") in {"running", "waiting_permission"}:
                    payload["status"] = "unknown"
                    self.db.execute(
                        "UPDATE agent_work_turns SET payload=? WHERE session_id=? AND turn_id=?",
                        (_json(payload), row["session_id"], row["turn_id"]),
                    )
