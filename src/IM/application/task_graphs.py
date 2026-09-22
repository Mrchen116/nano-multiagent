"""Own task graph authorization, atomic writes and consumer projections."""

from __future__ import annotations

import base64
import hashlib
import json
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from IM.domain.task_graphs import (
    MAX_DOCUMENT_BYTES,
    TaskGraphError,
    apply_operations,
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


_ACTION_FIELDS = {
    "list": {"conversation_id", "query", "cursor", "limit"},
    "get": {"graph_id", "scope_id", "view"},
    "create": {"conversation_id", "title", "description", "mode", "request_key"},
    "apply": {"graph_id", "base_revision", "request_key", "operations", "change_note"},
}


def _forbidden() -> None:
    raise TaskGraphError(
        "not_found_or_forbidden", "Task graph or conversation is not accessible"
    )


def _summary(document: dict, home_title: str) -> dict:
    root = next(n for n in document["nodes"] if n["id"] == document["root_node_id"])
    return {
        **{
            k: document[k]
            for k in (
                "graph_id",
                "root_node_id",
                "home_conversation_id",
                "revision",
                "created_at",
                "updated_at",
                "updated_by",
            )
        },
        **{k: root[k] for k in ("title", "mode", "status")},
        "home_conversation_title": home_title,
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
        write = action in {"create", "apply"}
        if write and actor.kind != "agent":
            _forbidden()
        with closing(connect(self.db_path)) as db, db:
            # The write reservation covers membership, receipt lookup and revision.
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            repository = TaskGraphRepository(db)
            principal = repository.actor_user(actor.kind, actor.id, actor.node_id)
            if principal is None:
                _forbidden()
            user_id = principal["id"]
            actor_name = f"{principal['display_name']} ({actor.id})"
            if action == "list":
                return self._list(repository, user_id, args)
            if action == "create":
                conversation_id = require_text(
                    args.get("conversation_id"), "conversation_id"
                )
                document = None
            else:
                graph_id = require_text(args.get("graph_id"), "graph_id")
                document = repository.get(graph_id)
                if document is None:
                    _forbidden()
                conversation_id = document["home_conversation_id"]
            conversation = repository.member_conversation(conversation_id, user_id)
            if conversation is None:
                _forbidden()
            if document is not None and document.get("schema_version") != 1:
                raise TaskGraphError(
                    "invalid_graph", "Unsupported task graph schema_version"
                )
            if action == "get":
                return self._get(document, conversation["title"], args)
            key = require_text(args.get("request_key"), "request_key")
            actor_key = f"{actor.kind}:{actor.id}"
            operation_hash = hashlib.sha256(
                json.dumps(
                    {"action": action, "args": args},
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
                graph_id, root = "tg_" + uuid4().hex, "tn_" + uuid4().hex
                document = {
                    "schema_version": 1,
                    "graph_id": graph_id,
                    "home_conversation_id": conversation_id,
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
                        )
                    ],
                    "dependencies": [],
                    "created_at": now,
                    "updated_at": now,
                    "updated_by": actor_name,
                }
                validate_document(document)
                result = _summary(document, conversation["title"])
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
                result = {
                    **_summary(document, conversation["title"]),
                    "client_refs": refs,
                    "changed_ids": changed,
                }
            if (
                len(json.dumps(document, ensure_ascii=False).encode())
                > MAX_DOCUMENT_BYTES
            ):
                raise TaskGraphError("invalid_graph", "Graph document exceeds 2 MiB")
            repository.save(
                document,
                actor_key=actor_key,
                request_key=key,
                operation_hash=operation_hash,
                result=result,
            )
            return result

    def _list(self, repository: TaskGraphRepository, user_id: str, args: dict) -> dict:
        conversation = args.get("conversation_id")
        if conversation is not None:
            require_text(conversation, "conversation_id")
            if repository.member_conversation(conversation, user_id) is None:
                _forbidden()
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
                if (
                    saved["query"] != query
                    or saved["conversation_id"] != conversation
                    or saved["user_id"] != user_id
                ):
                    raise ValueError()
                after = (
                    require_text(saved["created_at"], "cursor time"),
                    require_text(saved["graph_id"], "cursor graph"),
                )
            except (ValueError, KeyError, TypeError):
                raise TaskGraphError(
                    "invalid_arguments", "Invalid cursor for this query"
                ) from None
        rows, total = repository.list_for_member(
            user_id=user_id,
            conversation_id=conversation,
            query=query,
            after=after,
            limit=limit,
        )
        items = [
            _summary(json.loads(row["document_json"]), row["home_title"])
            for row in rows[:limit]
        ]
        cursor = None
        if len(rows) > limit:
            last = items[-1]
            cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "query": query,
                        "conversation_id": conversation,
                        "user_id": user_id,
                        "created_at": last["created_at"],
                        "graph_id": last["graph_id"],
                    }
                ).encode()
            ).decode()
        return {"items": items, "next_cursor": cursor, "total": total}

    def _get(self, document: dict, home_title: str, args: dict) -> dict:
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
        common = _summary(document, home_title)
        if view == "all":
            return {
                **document,
                "home_conversation_title": home_title,
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
