"""Own task graph authorization, atomic writes and consumer projections."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from urllib.parse import urlsplit, unquote
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from IM.domain.task_graphs import (
    MAX_DOCUMENT_BYTES,
    TaskGraphError,
    apply_operations,
    delete_subtree,
    new_node,
    require_text,
    validate_document,
)
from IM.infra._timestamps import utc_now
from IM.infra.db import connect
from IM.infra.repositories.task_graphs import TaskGraphRepository


@dataclass(frozen=True)
class TaskGraphActor:
    """Carry a principal derived from browser auth or registered Gateway identity."""

    kind: str
    id: str
    node_id: str | None = None
    source_message_id: str | None = None
    source_message_ids: tuple[str, ...] = ()


_ACTION_FIELDS = {
    "list": {"query", "cursor", "limit"},
    "activity": {"conversation_id"},
    "delete": {
        "graph_id",
        "node_id",
        "base_revision",
        "request_key",
        "conversation_id",
    },
    "get": {"graph_id", "scope_id", "view"},
    "create": {"conversation_id", "title", "description", "mode", "request_key"},
    "apply": {
        "graph_id",
        "base_revision",
        "request_key",
        "operations",
        "change_note",
        "conversation_id",
    },
}


def _forbidden() -> None:
    raise TaskGraphError(
        "not_found_or_forbidden", "Task graph or conversation is not accessible"
    )


def _summary(document: dict) -> dict:
    root = next(n for n in document["nodes"] if n["id"] == document["root_node_id"])
    return {
        **{
            k: document[k]
            for k in (
                "graph_id",
                "root_node_id",
                "revision",
                "created_at",
                "updated_at",
                "updated_by",
            )
        },
        **{k: root[k] for k in ("title", "mode", "status")},
        "relative_url": "/tasks/" + document["graph_id"],
    }


class TaskGraphService:
    """Execute graph commands with one connection and transaction per request.

    A private short-lived connection prevents unrelated IM repositories from
    committing a half-finished graph write on the app's shared connection.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def execute(self, actor: TaskGraphActor, action: str, args: dict[str, Any]) -> dict:
        """Read or atomically mutate an authorized graph without running agents.

        Args:
            actor: Identity captured by the authenticated API boundary.
            action: One of create, list, get or apply.
            args: Action-specific business parameters; no actor fields accepted.

        Returns:
            Saved write receipt, bounded list, or current graph projection.

        Raises:
            TaskGraphError: Invalid input, inaccessible graph, or conflicting write.
        """
        if (
            not isinstance(action, str)
            or action not in _ACTION_FIELDS
            or not isinstance(args, dict)
            or args.keys() - _ACTION_FIELDS[action]
        ):
            raise TaskGraphError(
                "invalid_arguments", "Unknown action or argument fields"
            )
        if len(json.dumps(args, ensure_ascii=False).encode()) > MAX_DOCUMENT_BYTES:
            raise TaskGraphError("invalid_arguments", "Request exceeds 2 MiB")
        if actor.kind not in {"user", "agent"}:
            _forbidden()
        write = action in {"create", "apply", "delete"}
        if write and actor.kind != "agent":
            _forbidden()
        with closing(connect(self.db_path)) as db, db:
            # The write reservation covers account authorization, receipts and revision.
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            repository = TaskGraphRepository(db)
            principal = repository.actor_user(actor.kind, actor.id, actor.node_id)
            if principal is None:
                _forbidden()
            user_id = principal["id"]
            owner_id = principal["owner_id"]
            actor_name = f"{principal['display_name']} ({actor.id})"
            if action == "list":
                return self._list(repository, owner_id, args)
            if action == "activity":
                chat_id = require_text(args.get("conversation_id"), "conversation_id")
                if repository.member_conversation(chat_id, user_id) is None:
                    _forbidden()
                return {"items": repository.activity(chat_id)}
            if write:
                key = require_text(args.get("request_key"), "request_key")
                actor_key = f"{actor.kind}:{actor.id}"
                operation_hash = hashlib.sha256(
                    json.dumps(
                        {
                            "action": action,
                            "args": {
                                k: v for k, v in args.items() if k != "conversation_id"
                            },
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest()
                receipt = repository.receipt(actor_key, key)
                if receipt is not None:
                    if receipt["operation_hash"] != operation_hash:
                        raise TaskGraphError(
                            "request_key_reused",
                            "Use the original parameters with this request_key",
                        )
                    return json.loads(receipt["result_json"])
            document = None
            if action != "create":
                graph_id = require_text(args.get("graph_id"), "graph_id")
                document = repository.get(graph_id)
                if document is None:
                    _forbidden()
            if document is not None and document.get("schema_version") != 1:
                raise TaskGraphError(
                    "invalid_graph", "Unsupported task graph schema_version"
                )
            if action == "get":
                return self._get(
                    self._project_chats(repository, document, user_id), args
                )
            conversation_id = args.get("conversation_id")
            if conversation_id is not None:
                require_text(conversation_id, "conversation_id")
                if repository.member_conversation(conversation_id, user_id) is None:
                    _forbidden()
            source = (
                repository.source_message(actor.source_message_id, user_id)
                if actor.source_message_id
                else None
            )
            if actor.source_message_id and source is None:
                _forbidden()
            provenance = {
                "agent_id": actor.id,
                "source_message_id": actor.source_message_id,
                "initiator_id": source["sender_source_id"] or source["sender_user_id"]
                if source
                else None,
                "channel": source["external_source"] if source else None,
                "source_chat_id": source["conversation_id"] if source else None,
            }
            now = utc_now()
            if action == "create":
                title = require_text(args.get("title"), "title", limit=240)
                description = require_text(
                    args.get("description", ""), "description", limit=32000, empty=True
                )
                mode = args.get("mode")
                if mode not in ("dag", "explore"):
                    raise TaskGraphError(
                        "invalid_arguments", "Root mode must be dag or explore"
                    )
                graph_id, root = "tg_" + uuid4().hex[:8], "n1"
                # The write reservation keeps this check and insertion atomic.
                while repository.get(graph_id) is not None:
                    graph_id = "tg_" + uuid4().hex[:8]
                document = {
                    "schema_version": 1,
                    "graph_id": graph_id,
                    "owner_id": owner_id,
                    "root_node_id": root,
                    "revision": 1,
                    "nodes": [
                        new_node(
                            node_id=root,
                            container_id=None,
                            title=title,
                            description=description,
                            mode=mode,
                            actor=actor_name,
                            now=now,
                            last_chat_id=conversation_id,
                        )
                    ],
                    "dependencies": [],
                    "created_at": now,
                    "updated_at": now,
                    "updated_by": actor_name,
                }
                validate_document(document)
                changed = [root]
                result = _summary(document)
            else:
                revision = args.get("base_revision")
                if type(revision) is not int or revision < 1:
                    raise TaskGraphError(
                        "invalid_arguments", "base_revision must be a positive integer"
                    )
                if revision != document["revision"]:
                    raise TaskGraphError(
                        "version_conflict",
                        "Read the current graph before adjusting this change",
                        current_revision=document["revision"],
                    )
                if action == "delete":
                    node_id = args.get("node_id", document["root_node_id"])
                    node = next(
                        (n for n in document["nodes"] if n["id"] == node_id), None
                    )
                    if node is None:
                        raise TaskGraphError(
                            "invalid_arguments", "node_id is not in this graph"
                        )
                    # Authorization comes from persisted human input, never tool arguments.
                    names = [
                        node["title"],
                        document["graph_id"]
                        if node_id == document["root_node_id"]
                        else f"{document['graph_id']}/{node_id}",
                    ]
                    source_ids = tuple(
                        dict.fromkeys(
                            (
                                *(
                                    (actor.source_message_id,)
                                    if actor.source_message_id
                                    else ()
                                ),
                                *actor.source_message_ids,
                            )
                        )
                    )
                    authorized = False
                    for source_id in source_ids:
                        candidate = repository.source_message(source_id, user_id)
                        if candidate is None:
                            continue
                        text = re.sub(
                            r'^(?:\s*<mention\s+type="user"\s+target_id="[^"]+"\s*/>)+',
                            "",
                            candidate["content"],
                        )
                        authorized = any(
                            re.fullmatch(
                                r"(?:请|确认|请确认)?(?:删除|删掉|移除)\s*[‘“\"']?"
                                + re.escape(name)
                                + r"[’”\"']?[。！!]?|(?:please\s+|confirm\s+)?(?:delete|remove)\s+[\"']?"
                                + re.escape(name)
                                + r"[\"']?[.!]?",
                                text.strip(),
                                re.I,
                            )
                            for name in names
                        )
                        if authorized:
                            break
                    if not authorized:
                        raise TaskGraphError(
                            "confirmation_required",
                            f'Ask the user to reply with exactly "删除 {names[1]}" or "delete {names[1]}" to confirm this scope. Do not claim a different chat or Web deletion is required.',
                        )
                    document, removed = delete_subtree(
                        document, node_id, actor=actor_name, now=now
                    )
                    result = {
                        "graph_id": graph_id,
                        "revision": document["revision"],
                        "deleted_ids": removed,
                        "deleted": not bool(document["nodes"]),
                        "updated_by": actor_name,
                    }
                    repository.delete(
                        document,
                        removed,
                        actor_key=actor_key,
                        request_key=key,
                        operation_hash=operation_hash,
                        result=result,
                    )
                    return result
                note = require_text(
                    args.get("change_note"), "change_note", limit=8000, empty=True
                )
                document, refs, changed = apply_operations(
                    document,
                    args.get("operations"),
                    actor=actor_name,
                    now=now,
                    change_note=note,
                )
                for node in document["nodes"]:
                    if node["id"] in changed:
                        node["last_chat_id"] = conversation_id
                result = {
                    **_summary(document),
                    "client_refs": refs,
                    "changed_ids": changed,
                }
            if (
                len(json.dumps(document, ensure_ascii=False).encode())
                > MAX_DOCUMENT_BYTES
            ):
                raise TaskGraphError("invalid_graph", "Graph document exceeds 2 MiB")
            for node in document["nodes"]:
                if node["id"] in changed:
                    node["provenance"] = provenance
            repository.save(
                document,
                actor_key=actor_key,
                request_key=key,
                operation_hash=operation_hash,
                result=result,
            )
            repository.record_activity(document, changed, conversation_id)
            return result

    def _list(self, repository: TaskGraphRepository, owner_id: str, args: dict) -> dict:
        query = require_text(
            args.get("query", ""), "query", limit=240, empty=True
        ).strip()
        limit = args.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise TaskGraphError(
                "invalid_arguments", "limit must be an integer from 1 to 50"
            )
        after = None
        if args.get("cursor") is not None:
            cursor = require_text(args["cursor"], "cursor", limit=2048)
            try:
                saved = json.loads(base64.urlsafe_b64decode(cursor))
                if saved["query"] != query or saved["owner_id"] != owner_id:
                    raise ValueError()
                after = (
                    require_text(saved["updated_at"], "cursor time"),
                    require_text(saved["graph_id"], "cursor graph"),
                )
            except (ValueError, KeyError, TypeError):
                raise TaskGraphError(
                    "invalid_arguments", "Invalid cursor for this query"
                ) from None
        rows, total = repository.list_for_owner(
            owner_id=owner_id,
            query=query,
            after=after,
            limit=limit,
        )
        items = [_summary(json.loads(row["document_json"])) for row in rows[:limit]]
        cursor = None
        if len(rows) > limit:
            last = items[-1]
            cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "query": query,
                        "owner_id": owner_id,
                        "updated_at": last["updated_at"],
                        "graph_id": last["graph_id"],
                    }
                ).encode()
            ).decode()
        return {"items": items, "next_cursor": cursor, "total": total}

    def _project_chats(
        self, repository: TaskGraphRepository, document: dict, user_id: str
    ) -> dict:
        """Expose update-chat links only under their independent current chat ACL."""
        projected = {key: value for key, value in document.items() if key != "owner_id"}
        chats = {}
        projected["nodes"] = []
        for node in document["nodes"]:
            chat_id = node.get("last_chat_id")
            if chat_id and chat_id not in chats:
                chats[chat_id] = repository.member_conversation(chat_id, user_id)
            chat = chats.get(chat_id)
            projected["nodes"].append(
                {
                    **node,
                    "provenance": (
                        {
                            **node.get("provenance", {}),
                            "source_message_id": None,
                            "source_chat_id": None,
                            "initiator_id": None,
                        }
                        if repository.member_conversation(
                            node.get("provenance", {}).get("source_chat_id"), user_id
                        )
                        is None
                        else node.get("provenance")
                    ),
                    "links": [
                        link
                        for link in node["links"]
                        if self._link_allowed(repository, link, user_id)
                    ],
                    "last_chat_id": chat["id"] if chat is not None else None,
                    "last_chat_title": chat["title"] if chat is not None else None,
                }
            )
        return projected

    @staticmethod
    def _link_allowed(repository: TaskGraphRepository, link: str, user_id: str) -> bool:
        path = unquote(urlsplit(link).path)
        match = re.match(r"/im/v1/conversations/([^/]+)/(?:images|attachments)/", path)
        return (
            match is None
            or repository.member_conversation(match[1], user_id) is not None
        )

    def _get(self, document: dict, args: dict) -> dict:
        view = args.get("view", "scope")
        if view not in ("scope", "all"):
            raise TaskGraphError("invalid_arguments", "view must be scope or all")
        nodes = {n["id"]: n for n in document["nodes"]}
        scope_id = require_text(
            args.get("scope_id", document["root_node_id"]), "scope_id"
        )
        if scope_id not in nodes:
            raise TaskGraphError(
                "invalid_arguments", "scope_id is not a node in this graph"
            )
        common = _summary(document)
        if view == "all":
            return {
                **document,
                "relative_url": common["relative_url"],
            }
        scope = nodes[scope_id]
        children = sorted(
            (n for n in nodes.values() if n["container_id"] == scope_id),
            key=lambda n: (n["order"], n["id"]),
        )
        counts = {key: 0 for key in nodes}
        for node in nodes.values():
            if node["container_id"] in counts:
                counts[node["container_id"]] += 1
        path, current = [], scope
        while current is not None:
            path.append(current)
            current = nodes.get(current["container_id"])
        child_ids = {n["id"] for n in children}
        return {
            **common,
            "schema_version": 1,
            "root": nodes[document["root_node_id"]],
            "scope": scope,
            "breadcrumbs": list(reversed(path)),
            "children": [{**n, "child_count": counts[n["id"]]} for n in children],
            "dependencies": [
                e for e in document["dependencies"] if e["from"] in child_ids
            ],
            "derivations": [
                {"from": n["derived_from_id"], "to": n["id"]}
                for n in children
                if n["derived_from_id"]
            ],
        }
