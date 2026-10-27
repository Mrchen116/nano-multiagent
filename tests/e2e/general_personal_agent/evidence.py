"""Read-only evidence collection using the same public IM interfaces as the UI."""

from __future__ import annotations

import re
from urllib.parse import quote


def get(client, path: str, **params) -> dict:
    """Read an authenticated public IM resource, failing on HTTP errors."""
    response = client._http.get(path, headers=client._auth_headers, params=params)
    response.raise_for_status()
    return response.json()


def timeline(client, conversation: str) -> list[dict]:
    """Collect every timeline page, including interactions and attachment messages."""
    items, cursor, seen = [], None, set()
    while True:
        page = get(
            client,
            f"/im/v1/conversations/{conversation}/messages",
            limit=100,
            **({"before_message_id": cursor} if cursor else {}),
        )
        items[0:0] = page["items"]
        cursor = page.get("next_before_message_id")
        if not cursor:
            return items
        if cursor in seen:
            raise ValueError("timeline pagination did not progress")
        seen.add(cursor)


def turns(client, base: str) -> dict:
    """Collect complete turns and tool items, retaining native IDs and receipts."""
    view = get(client, base, limit=50)
    all_turns = list(view.get("turns", []))
    cursor, seen = view.get("next_cursor"), set()
    while cursor:
        if cursor in seen:
            raise ValueError("work pagination did not progress")
        seen.add(cursor)
        page = get(client, base, before_turn=cursor, limit=50)
        all_turns.extend(page["turns"])
        cursor = page.get("next_cursor")
    # A child base ends in /sessions/<id>/turns; item URLs still use root base.
    root_base = base.split("/sessions/")[0]
    for turn in all_turns:
        cursor, seen = turn.get("next_items_cursor"), set()
        while cursor:
            if cursor in seen:
                raise ValueError("work item pagination did not progress")
            seen.add(cursor)
            path = (
                f"{root_base}/sessions/{quote(turn['session_id'], safe='')}/turns/"
                f"{quote(turn['turn_id'], safe='')}/items"
            )
            page = get(client, path, after_seq=cursor, limit=200)
            turn["items"].extend(page["items"])
            cursor = page.get("next_cursor")
    return {**view, "turns": all_turns}


def capture(client, agent: str, chats: dict[str, str]) -> dict:
    """Capture complete main/child Work and user-visible source conversations.

    Missing child evidence is explicit; it is never silently treated as success.
    Provider requests are separate evidence because Work is not final model input.
    """
    base = f"/im/v1/agents/{agent}/work"
    work = turns(client, base)
    children, errors = {}, []
    for child in work.get("other_executions", []):
        sid = child.get("session_id")
        if not sid:
            continue
        try:
            children[sid] = turns(
                client, f"{base}/sessions/{quote(sid, safe='')}/turns"
            )
        except Exception as error:
            errors.append({"session_id": sid, "error": str(error)})
    messages = {name: timeline(client, cid) for name, cid in chats.items()}
    views = [work, *children.values()]
    tools, context_pointers, usages = [], [], []
    for view in views:
        for turn in view.get("turns", []):
            pointer = {"session_id": turn["session_id"], "turn_id": turn["turn_id"]}
            context_pointers.append(pointer)
            if turn.get("usage"):
                usages.append({**pointer, "usage": turn["usage"]})
            for item in turn.get("items", []):
                if item.get("kind") == "tool":
                    tools.append(
                        {**pointer, "seq": item["seq"], "payload": item["payload"]}
                    )
    return {
        "work": work,
        "children": children,
        "messages": messages,
        "tool_results": tools,
        "context_pointers": context_pointers,
        "usage": usages,
        "resources": resources(messages),
        "errors": errors,
    }


def resources(value: object) -> list[str]:
    """Extract actual resource references; a path/URL alone is not byte validation."""
    found = set()

    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key in {
                    "url",
                    "resource_id",
                    "artifact_id",
                    "media_id",
                    "download_url",
                } and isinstance(child, str):
                    found.add(child)
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            found.update(re.findall(r'https?://[^\s<>"\)]+', item))

    visit(value)
    return sorted(found)


def metrics(snapshot: dict, elapsed: float) -> dict:
    """Report observed counters only; unavailable measurements remain null."""
    turns_by_id = {}
    for view in [snapshot["work"], *snapshot.get("children", {}).values()]:
        for turn in view.get("turns", []):
            turns_by_id[(turn["session_id"], turn["turn_id"])] = turn
    return {
        "elapsed_seconds": elapsed,
        "observed_turns": len(turns_by_id),
        "observed_tool_calls": len(snapshot["tool_results"]),
        "reported_usage": snapshot["usage"],
        "model_calls": None,
        "duplicate_notifications": None,
        "incorrect_memory": None,
        "response_blocking_seconds": None,
        "delivered_resources": snapshot["resources"],
    }
