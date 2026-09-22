"""Expose durable task records through the executing PA Agent's Gateway."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from agent.sdk import ToolContext
from personal_assistant.tools.inbox import QueryPresenter


ACTION_FIELDS = {
    "create": {"target", "title", "description", "mode", "request_key"},
    "list": {"query", "cursor", "limit"},
    "get": {"graph_id", "scope_id", "view"},
    "apply": {
        "graph_id",
        "base_revision",
        "request_key",
        "operations",
        "change_note",
        "target",
    },
}
REQUIRED_FIELDS = {
    "create": {"title", "mode", "request_key"},
    "list": set(),
    "get": {"graph_id"},
    "apply": {
        "graph_id",
        "base_revision",
        "request_key",
        "operations",
        "change_note",
    },
}


def validate_arguments(args: Mapping[str, Any]) -> str:
    """Reject unknown/absent business fields; IM owns all graph invariants."""
    if not isinstance(args, Mapping):
        raise ValueError("invalid_arguments: expected an object")
    action = args.get("action")
    if not isinstance(action, str) or action not in ACTION_FIELDS:
        raise ValueError("invalid_arguments: action must be create/list/get/apply")
    unexpected = set(args) - ACTION_FIELDS[action] - {"action"}
    missing = REQUIRED_FIELDS[action] - set(args)
    if unexpected or missing:
        raise ValueError(
            f"invalid_arguments: unexpected={sorted(unexpected)}, missing={sorted(missing)}"
        )
    if "target" in args and (
        not isinstance(args["target"], str) or not args["target"].strip()
    ):
        raise ValueError("invalid_arguments: target must be non-empty text")
    return action


def unavailable_result(args: Mapping[str, Any], *, uncertain: bool) -> dict[str, Any]:
    """Keep the original mutation identity when its result cannot be confirmed."""
    if uncertain and args.get("action") in {"create", "apply"}:
        return {
            "code": "write_outcome_unknown",
            "request_key": args.get("request_key"),
            "message": "Write outcome is unknown. Retry exactly the same arguments and request_key; do not invent another mutation key.",
        }
    return {
        "code": "source_unavailable",
        "message": "IM task graph service is unavailable; try again after reconnection.",
    }


class TaskGraphTool:
    """Read or atomically update task records, with ordinary tool approval policy."""

    name = "task_graph"
    description = (
        "Record user-approved plans and progress in durable task graphs, then return the Web IM link. "
        "These records never schedule or execute tasks. Discuss first; create only when the user asks to save a plan. "
        "Goals belong to your account and are shared with its other enabled Agents; no Agent assignment is needed. "
        "create requires title, mode and a unique request_key, with no required chat. "
        "For create/apply, target optionally records the discussion where changed nodes were last updated. Bound single-thread runs record their actual chat automatically. "
        "Global or unbound runs must explicitly supply the relevant Inbox/conversations target to record a chat; otherwise no chat is recorded. Never guess the last chat. "
        "list searches all account goals by title, returning paginated summaries ordered by latest update; get/apply use a known graph_id regardless of prompt channel. "
        "get defaults to root scope; use scope_id for nested children or view=all for the bounded full document. "
        "Node IDs are stable within their graph (e.g. n1); reuse the returned IDs. "
        "dag orders direct children by prerequisites; explore records alternative siblings and one selected candidate. "
        "Container nesting and derivation are different: X-derived Z remains X's sibling. Each node can contain a nested dag/explore. "
        "A negative result can be done; selecting a candidate does not finish its parent or other candidates. "
        "For apply, read the current revision, supply a unique request_key and an ordinary change_note (including any done-to-doing reason). "
        "On version_conflict, reread and reconcile before a new mutation. On write_outcome_unknown, retry the EXACT same arguments/key. "
        "Never claim a write succeeded without confirmation. No deletion, reparenting or nonempty mode conversion."
    )
    presenter = QueryPresenter("Task graph")
    max_result_size_chars = None
    is_concurrency_safe = False
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(ACTION_FIELDS)},
            "target": {
                "type": "string",
                "description": "Optional discussion source for create/apply: existing IM conversation_id or Inbox/conversations target. Only changed nodes receive this last-update chat.",
            },
            "title": {"type": "string", "maxLength": 240},
            "description": {"type": "string", "maxLength": 32000},
            "mode": {"type": "string", "enum": ["dag", "explore"]},
            "graph_id": {"type": "string"},
            "scope_id": {"type": "string"},
            "view": {"type": "string", "enum": ["scope", "all"]},
            "query": {"type": "string"},
            "cursor": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "base_revision": {"type": "integer", "minimum": 1},
            "request_key": {
                "type": "string",
                "maxLength": 128,
                "description": "Required for BOTH create and apply. Choose a unique key for each new mutation; preserve the same key and arguments on uncertain retries.",
            },
            "change_note": {"type": "string", "maxLength": 8000},
            "operations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 100,
                "description": (
                    "Atomic finite operations; IDs may use @client_ref defined by an earlier add_task in this batch. "
                    "add_task: container_id,title,client_ref plus optional description/mode/status/result/links/order/derived_from_id. "
                    "update_task: node_id,patch (title/description/mode/status/result/links/order only). "
                    "add_dependency/remove_dependency: from,to (direct siblings in dag). "
                    "set_derivation: node_id,derived_from_id (sibling in explore, or null). "
                    "select_candidate: scope_id,node_id (direct child or null),reason. "
                    "Modes none/dag/explore; statuses todo/doing/done/paused/dropped. Links are http(s) URLs or protected IM attachment paths. "
                    'Example: [{"op":"add_task","client_ref":"A","container_id":"n1","title":"Choose a direction","mode":"explore"}].'
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {
                            "type": "string",
                            "enum": [
                                "add_task",
                                "update_task",
                                "add_dependency",
                                "remove_dependency",
                                "set_derivation",
                                "select_candidate",
                            ],
                        },
                        "client_ref": {"type": "string"},
                        "container_id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "mode": {"type": "string", "enum": ["none", "dag", "explore"]},
                        "status": {
                            "type": "string",
                            "enum": ["todo", "doing", "done", "paused", "dropped"],
                        },
                        "result": {"type": "string"},
                        "links": {"type": "array", "items": {"type": "string"}},
                        "order": {"type": "number"},
                        "derived_from_id": {"type": ["string", "null"]},
                        "node_id": {"type": ["string", "null"]},
                        "scope_id": {"type": "string"},
                        "reason": {"type": "string"},
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                        "patch": {
                            "type": "object",
                            "description": "Only title/description/mode/status/result/links/order.",
                        },
                    },
                    "required": ["op"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(
        self, *, gateway_dispatch_url_provider: Callable[[], str | None] | None = None
    ) -> None:
        self._provider = gateway_dispatch_url_provider

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Send trusted ToolContext identity separately from model business fields.

        Raises:
            ValueError: Invalid action fields, before network I/O.
            RuntimeError: An explicit service error or uncertain write outcome.
        """
        validate_arguments(args)
        url = (
            self._provider()
            if self._provider
            else ctx.session_metadata.get("gateway_dispatch_url")
        )
        if not isinstance(url, str) or not url:
            raise RuntimeError(json.dumps(unavailable_result(args, uncertain=False)))
        parsed = urlsplit(url)
        endpoint = urlunsplit(
            (parsed.scheme, parsed.netloc, "/internal/task-graph", "", "")
        )
        try:
            response = httpx.post(
                endpoint,
                json={
                    "source_agent_id": ctx.session_metadata.get("agent_id"),
                    "origin_kernel_session_id": ctx.session_id,
                    "origin_run_id": ctx.run_id,
                    "tool_call_id": ctx.tool_call_id,
                    "args": dict(args),
                },
                timeout=httpx.Timeout(connect=3, read=50, write=10, pool=3),
                trust_env=False,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(
                json.dumps(unavailable_result(args, uncertain=True))
            ) from exc
        if (
            response.status_code >= 400
            or not isinstance(body, dict)
            or body.get("ok") is not True
        ):
            error = (
                body.get("error")
                if isinstance(body, dict)
                else unavailable_result(args, uncertain=True)
            )
            raise RuntimeError(json.dumps(error, ensure_ascii=False))
        return body["result"]

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        """Keep complete bounded task data and actual errors in the model context."""
        return (
            error
            if error is not None
            else json.dumps(output, ensure_ascii=False, separators=(",", ":"))
        )

    def to_auto_classifier_input(self, tool_input: Mapping[str, Any]) -> str:
        """Expose the destination and all proposed record changes for approval."""
        return json.dumps(dict(tool_input), ensure_ascii=False)


def get_tool() -> TaskGraphTool:
    """Return the native PA tool for standalone product discovery."""
    return TaskGraphTool()
