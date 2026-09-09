"""Query only the calling Agent's real conversation memberships without read receipts."""

from __future__ import annotations

import base64
import json
import sqlite3

from IM.infra.repositories.agent_work import AgentWorkRepository
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.messages import MessageRepository


def _encode(value: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(value, separators=(",", ":")).encode()
    ).decode()


def _decode(raw: str) -> dict:
    try:
        value = json.loads(base64.urlsafe_b64decode(raw))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValueError("invalid_cursor") from None


class WorkConversationQuery:
    """Read public message content for a registered global main Session."""

    def __init__(
        self, connection: sqlite3.Connection, work: AgentWorkRepository
    ) -> None:
        self.db = connection
        self.work = work

    def query(
        self, *, node_id: str, agent_id: str, session_id: str, action: str, **params
    ) -> dict:
        """Return one bounded page after authenticating node, Agent and main Session.

        Raises:
            ValueError: Invalid cursor or inaccessible target, without leaking its existence.
        """
        profile = AgentProfileRepository(self.db).get_profile(agent_id=agent_id)
        if profile is None or profile.node_id != node_id or profile.is_stale:
            raise ValueError("scope_not_allowed")
        session = self.work.session(agent_id, session_id)
        if session["node_id"] != node_id or session["scope"] != "global_main":
            raise ValueError("scope_not_allowed")
        limit = params.get("limit", 20)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 50
            or action not in {"list", "read"}
        ):
            raise ValueError("invalid_arguments")
        rows = self.db.execute(
            """SELECT c.* FROM conversations c JOIN conversation_participants cp ON cp.conversation_id=c.id
          JOIN users u ON u.id=cp.user_id WHERE u.username=? ORDER BY COALESCE(c.last_message_at,c.created_at) DESC,c.id""",
            (f"agent:{agent_id}",),
        ).fetchall()
        target = params.get("target")
        identity = {
            "agent": agent_id,
            "action": action,
            "target": target,
            "query": params.get("query"),
        }
        cursor = _decode(params["cursor"]) if params.get("cursor") else None
        if cursor and any(cursor.get(k) != v for k, v in identity.items()):
            raise ValueError("invalid_cursor")
        if action == "list":
            conversations = []
            for row in rows:
                participants = self._participants(row["id"])
                query = str(params.get("query") or "").casefold()
                if (
                    query
                    and query not in row["title"].casefold()
                    and not any(query in p["name"].casefold() for p in participants)
                ):
                    continue
                conversations.append(
                    {
                        "target": row["id"],
                        "name": row["title"],
                        "kind": row["type"],
                        "channel": row["external_source"] or "web",
                        "participants": participants,
                        "latest_message_at": row["last_message_at"],
                        "history_availability": "im_history",
                    }
                )
            # Cursor freezes membership/order of this page snapshot. Recheck current permissions on every query.
            ids = cursor["ids"] if cursor else [c["target"] for c in conversations]
            lookup = {c["target"]: c for c in conversations}
            ordered = [lookup[i] for i in ids if i in lookup]
            start = cursor["offset"] if cursor else 0
            page = ordered[start : start + limit]
            more = start + limit < len(ordered)
            return {
                "conversations": page,
                "has_more": more,
                "next_cursor": _encode(
                    {**identity, "ids": ids, "offset": start + limit}
                )
                if more
                else None,
            }
        if params.get("before_message_id") and cursor:
            raise ValueError("invalid_arguments")
        if target not in {r["id"] for r in rows}:
            raise ValueError("target_not_accessible")
        messages = MessageRepository(self.db).list_all_messages(conversation_id=target)
        messages = [
            m
            for m in messages
            if m.sender_type in {"user", "agent"} and (m.content or m.attachments)
        ]
        if params.get("before_message_id"):
            before = next(
                (
                    i
                    for i, m in enumerate(messages)
                    if m.id == params["before_message_id"]
                ),
                None,
            )
            if before is None:
                raise ValueError("target_not_accessible")
            messages = messages[:before]
        ids = cursor["ids"] if cursor else [m.id for m in reversed(messages)]
        by_id = {m.id: m for m in messages}
        index = cursor.get("offset", 0) if cursor else 0
        part = cursor.get("part", 0) if cursor else 0
        budget = 24000
        images = 0
        page = []
        row = next(r for r in rows if r["id"] == target)
        while index < len(ids) and len(page) < limit:
            m = by_id.get(ids[index])
            if m is None:
                index += 1
                part = 0
                continue
            parts = [
                {"type": "text", "text": m.content[i : i + 24000]}
                for i in range(0, len(m.content), 24000)
            ]
            parts += [
                {
                    "type": "image"
                    if a.content_type.startswith("image/")
                    else "attachment",
                    "url": a.url,
                    "file_name": a.file_name,
                    "content_type": a.content_type,
                }
                for a in m.attachments
            ]
            while part < len(parts) and len(page) < limit:
                content = parts[part]
                cost = len(content.get("text", ""))
                if cost > budget or (content["type"] == "image" and images >= 4):
                    break
                budget -= cost
                images += int(content["type"] == "image")
                sender = m.sender
                page.append(
                    {
                        "message_id": m.id,
                        "sender": {
                            "id": m.sender_user_id,
                            "name": sender.display_name if sender else m.sender_user_id,
                            "kind": m.sender_type,
                        },
                        "source_time": m.created_at,
                        "source": {
                            "channel": row["external_source"] or "web",
                            "conversation_id": target,
                            "reply_target": target,
                        },
                        "part_key": str(part),
                        "content": [content],
                        "complete_message": len(parts) == 1,
                    }
                )
                part += 1
            if part < len(parts):
                break
            index += 1
            part = 0
        more = index < len(ids)
        return {
            "target": target,
            "messages": page,
            "history_scope": "im_history",
            "has_more": more,
            "next_cursor": _encode(
                {**identity, "ids": ids, "offset": index, "part": part}
            )
            if more
            else None,
        }

    def _participants(self, conversation_id: str) -> list[dict]:
        return [
            {
                "id": r["id"],
                "name": r["display_name"],
                "kind": "agent" if r["username"].startswith("agent:") else "user",
            }
            for r in self.db.execute(
                "SELECT u.id,u.display_name,u.username FROM users u JOIN conversation_participants cp ON cp.user_id=u.id WHERE cp.conversation_id=?",
                (conversation_id,),
            )
        ]
