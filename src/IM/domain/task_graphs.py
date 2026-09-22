"""Validate and edit task documents without executing or scheduling their nodes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

MAX_NODES = 500
MAX_DEPENDENCIES = 1000
MAX_OPERATIONS = 100
MAX_DEPTH = 8
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MODES = frozenset({"none", "dag", "explore"})
STATUSES = frozenset({"todo", "doing", "done", "paused", "dropped"})
EDITABLE_FIELDS = frozenset(
    {"title", "description", "mode", "status", "result", "links", "order"}
)


class TaskGraphError(ValueError):
    """Report one actionable failure without exposing inaccessible graph data."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        """Return the shared HTTP/tool error payload."""
        return {"code": self.code, "message": str(self), **self.details}


def require_text(
    value: Any, field: str, *, limit: int = 128, empty: bool = False
) -> str:
    """Validate a bounded string without silently truncating saved content."""
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (not empty and not value.strip())
    ):
        raise TaskGraphError(
            "invalid_arguments",
            f"{field} must be a string of 1–{limit} characters"
            if not empty
            else f"{field} must be a string of at most {limit} characters",
        )
    return value


def new_node(
    *,
    node_id: str,
    container_id: str | None,
    title: str,
    actor: str,
    now: str,
    **fields: Any,
) -> dict:
    """Create a leaf or empty scope with server-owned identity and timestamps."""
    return {
        "id": node_id,
        "container_id": container_id,
        "title": title,
        "description": "",
        "mode": "none",
        "status": "todo",
        "result": "",
        "derived_from_id": None,
        "selected_candidate_id": None,
        "selection_reason": "",
        "links": [],
        "order": 0,
        "last_chat_id": None,
        **fields,
        "created_at": now,
        "updated_at": now,
        "updated_by": actor,
    }


def _invalid(message: str) -> None:
    raise TaskGraphError("invalid_graph", message)


def _acyclic(ids: set[str], edges: list[tuple[str, str]]) -> None:
    pending = {key: 0 for key in ids}
    outgoing: dict[str, list[str]] = {key: [] for key in ids}
    for start, end in edges:
        pending[end] += 1
        outgoing[start].append(end)
    ready = [key for key, count in pending.items() if count == 0]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for end in outgoing[key]:
            pending[end] -= 1
            if pending[end] == 0:
                ready.append(end)
    if visited != len(ids):
        _invalid("Relationships must not contain a cycle")


def validate_document(document: dict) -> None:
    """Reject malformed containment, relation semantics and node content.

    Args:
        document: Complete candidate document, including unchanged nodes.

    Raises:
        TaskGraphError: A node, relationship, selection or size limit is invalid.
    """
    if document.get("schema_version") != 1:
        _invalid("Unsupported task graph schema_version")
    nodes = document["nodes"]
    if (
        not 1 <= len(nodes) <= MAX_NODES
        or len(document["dependencies"]) > MAX_DEPENDENCIES
    ):
        _invalid("A graph allows at most 500 nodes and 1000 dependencies")
    by_id = {n["id"]: n for n in nodes}
    root = document["root_node_id"]
    if len(by_id) != len(nodes) or root not in by_id:
        _invalid("Node IDs must be unique and include the root")
    if by_id[root]["container_id"] is not None or by_id[root]["mode"] not in (
        "dag",
        "explore",
    ):
        _invalid("The root must be a plan or exploration scope with no container")
    children: dict[str, list[dict]] = {key: [] for key in by_id}
    derivations = []
    for node in nodes:
        require_text(node["title"], "title", limit=240)
        for field in ("description", "result"):
            require_text(node[field], field, limit=32000, empty=True)
        require_text(
            node["selection_reason"], "selection_reason", limit=8000, empty=True
        )
        if (
            not isinstance(node["mode"], str)
            or not isinstance(node["status"], str)
            or node["mode"] not in MODES
            or node["status"] not in STATUSES
        ):
            _invalid("Unknown node mode or record status")
        if type(node["order"]) is not int:
            _invalid("order must be an integer")
        links = node["links"]
        if not isinstance(links, list) or len(links) > 20:
            _invalid("links must contain at most 20 URLs")
        for link in links:
            require_text(link, "link", limit=2048)
            try:
                url = urlsplit(link)
            except ValueError:
                _invalid("Link is not a valid URL")
            if not (
                (url.scheme in {"http", "https"} and url.netloc)
                or (
                    not url.scheme
                    and not url.netloc
                    and url.path.startswith("/im/v1/conversations/")
                    and any(part in url.path for part in ("/images/", "/attachments/"))
                )
            ):
                _invalid(
                    "Links must be HTTP(S) URLs or protected IM attachment references"
                )
        if node["id"] != root:
            parent = by_id.get(node["container_id"])
            if parent is None or parent["mode"] == "none":
                _invalid("Every non-root node must belong to a subdivided scope")
            children[parent["id"]].append(node)
            seen = {node["id"]}
            current = parent
            while True:
                if current["id"] in seen or len(seen) >= MAX_DEPTH:
                    _invalid(
                        "Containment must reach the root within eight levels without a cycle"
                    )
                seen.add(current["id"])
                if current["id"] == root:
                    break
                current = by_id.get(current["container_id"])
                if current is None:
                    _invalid("Containment must reach the root")
        source = node["derived_from_id"]
        if source is not None:
            other = by_id.get(source)
            parent = by_id.get(node["container_id"])
            if (
                other is None
                or parent is None
                or parent["mode"] != "explore"
                or other["container_id"] != parent["id"]
            ):
                _invalid("A direction source must belong to the same exploration scope")
            derivations.append((source, node["id"]))
    dependencies = []
    for edge in document["dependencies"]:
        start, end = by_id.get(edge["from"]), by_id.get(edge["to"])
        parent = by_id.get(start["container_id"]) if start else None
        if (
            start is None
            or end is None
            or parent is None
            or parent["mode"] != "dag"
            or end["container_id"] != parent["id"]
        ):
            _invalid("Dependencies must join direct children of the same plan scope")
        dependencies.append((start["id"], end["id"]))
    if len(set(dependencies)) != len(dependencies):
        _invalid("Dependencies must be unique")
    _acyclic(set(by_id), dependencies)
    _acyclic(set(by_id), derivations)
    for node in nodes:
        chosen = node["selected_candidate_id"]
        if chosen is not None:
            candidate = by_id.get(chosen)
            if (
                node["mode"] != "explore"
                or candidate not in children[node["id"]]
                or candidate["status"] == "dropped"
            ):
                _invalid(
                    "The selected direction must be a non-dropped direct exploration candidate"
                )


def apply_operations(
    document: dict, operations: Any, *, actor: str, now: str, change_note: str
) -> tuple[dict, dict[str, str], list[str]]:
    """Apply one finite batch to a copy and validate its complete final state.

    Args:
        document: Current persisted graph; never changed in place.
        operations: Ordered public operations, with same-batch @references.
        actor: Verified actor display text for server-generated attribution.
        now: Server-generated UTC timestamp.
        change_note: Human-readable reason, required when reopening completed work.

    Returns:
        Validated candidate document, new reference mapping and changed node IDs.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= MAX_OPERATIONS:
        raise TaskGraphError("invalid_arguments", "operations must contain 1–100 items")
    candidate = deepcopy(document)
    nodes = {n["id"]: n for n in candidate["nodes"]}
    refs: dict[str, str] = {}
    changed: set[str] = set()
    allowed = {
        "add_task": {"op", "client_ref", "container_id", "derived_from_id"}
        | EDITABLE_FIELDS,
        "update_task": {"op", "node_id", "patch"},
        "add_dependency": {"op", "from", "to"},
        "remove_dependency": {"op", "from", "to"},
        "set_derivation": {"op", "node_id", "derived_from_id"},
        "select_candidate": {"op", "scope_id", "node_id", "reason"},
    }

    def resolve(value: Any, *, nullable: bool = False) -> str | None:
        if value is None and nullable:
            return None
        text = require_text(value, "node reference")
        node_id = refs.get(text[1:]) if text.startswith("@") else text
        if node_id not in nodes:
            _invalid(f"Unknown node or forward reference: {text}")
        return node_id

    for index, operation in enumerate(operations):
        try:
            if (
                not isinstance(operation, dict)
                or not isinstance(operation.get("op"), str)
                or operation.get("op") not in allowed
            ):
                raise TaskGraphError("invalid_arguments", "Unknown operation")
            kind = operation["op"]
            if operation.keys() - allowed[kind]:
                raise TaskGraphError("invalid_arguments", f"Unknown fields for {kind}")
            if kind == "add_task":
                ref = require_text(operation.get("client_ref"), "client_ref")
                if ref in refs or ref.startswith("@"):
                    _invalid(
                        "client_ref must be unique within the batch and not start with @"
                    )
                parent = resolve(operation.get("container_id"))
                # Nodes are never deleted or renumbered; allocation is graph-local.
                node_id = f"n{len(nodes) + 1}"
                fields = {
                    key: value
                    for key, value in operation.items()
                    if key in EDITABLE_FIELDS
                }
                title = fields.pop("title", None)
                source = resolve(operation.get("derived_from_id"), nullable=True)
                item = new_node(
                    node_id=node_id,
                    container_id=parent,
                    title=title,
                    actor=actor,
                    now=now,
                    derived_from_id=source,
                    **fields,
                )
                candidate["nodes"].append(item)
                nodes[node_id] = item
                refs[ref] = node_id
                changed.update([node_id, parent])
            elif kind == "update_task":
                node_id = resolve(operation.get("node_id"))
                patch = operation.get("patch")
                if (
                    not isinstance(patch, dict)
                    or not patch
                    or patch.keys() - EDITABLE_FIELDS
                ):
                    raise TaskGraphError(
                        "invalid_arguments",
                        "patch must contain only editable node fields",
                    )
                old = nodes[node_id]
                if (
                    "mode" in patch
                    and patch["mode"] != old["mode"]
                    and any(n["container_id"] == node_id for n in candidate["nodes"])
                ):
                    _invalid("A non-empty scope cannot change its internal mode")
                if (
                    old["status"] == "done"
                    and patch.get("status") == "doing"
                    and not change_note.strip()
                ):
                    _invalid("Reopening completed work requires a change_note")
                old.update(patch)
                changed.add(node_id)
            elif kind in {"add_dependency", "remove_dependency"}:
                edge = {
                    "from": resolve(operation.get("from")),
                    "to": resolve(operation.get("to")),
                }
                if kind == "add_dependency":
                    if edge not in candidate["dependencies"]:
                        candidate["dependencies"].append(edge)
                elif edge in candidate["dependencies"]:
                    candidate["dependencies"].remove(edge)
                else:
                    raise TaskGraphError(
                        "relation_not_found", "That dependency does not exist"
                    )
                changed.update(edge.values())
            elif kind == "set_derivation":
                node_id = resolve(operation.get("node_id"))
                parent = nodes.get(nodes[node_id]["container_id"])
                if parent is None or parent["mode"] != "explore":
                    _invalid(
                        "Derivation can only be changed inside an exploration scope"
                    )
                nodes[node_id]["derived_from_id"] = resolve(
                    operation.get("derived_from_id"), nullable=True
                )
                changed.add(node_id)
            else:
                node_id = resolve(operation.get("scope_id"))
                if nodes[node_id]["mode"] != "explore":
                    _invalid("Selection can only be changed on an exploration scope")
                nodes[node_id]["selected_candidate_id"] = resolve(
                    operation.get("node_id"), nullable=True
                )
                nodes[node_id]["selection_reason"] = require_text(
                    operation.get("reason", ""), "reason", limit=8000, empty=True
                )
                changed.add(node_id)
        except TaskGraphError as exc:
            exc.details["operation_index"] = index
            raise
    validate_document(candidate)
    for node_id in changed:
        nodes[node_id].update(updated_at=now, updated_by=actor, change_note=change_note)
    candidate.update(
        revision=document["revision"] + 1, updated_at=now, updated_by=actor
    )
    return candidate, refs, sorted(changed)
