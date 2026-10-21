"""Script model choices, never host source facts, for true-IM source regression."""

from __future__ import annotations

import json
import time


def source_blocks(body: dict, case: dict, case_id: str, tool) -> list[dict]:
    """Read actual host pages (including cursors) then delegate an observed action."""
    blocks = [
        block
        for message in body.get("messages", [])
        for block in (
            message.get("content") if isinstance(message.get("content"), list) else []
        )
    ]
    calls = {block["id"]: block for block in blocks if block.get("type") == "tool_use"}
    results = {
        block["tool_use_id"]: block
        for block in blocks
        if block.get("type") == "tool_result"
    }
    prefix = f"source-{case_id}"

    def call(name, args, suffix):
        return [tool(name, args, f"{prefix}-{suffix}")]

    def result(suffix):
        content = results.get(f"{prefix}-{suffix}", {}).get("content", [])
        text = (
            content
            if isinstance(content, str)
            else "\n".join(c.get("text", "") for c in content)
        )

        def page(value):
            # PTC's public rendered body wraps its stdout; consume only the
            # actual JSON printed by tools.inbox, never invent a cursor.
            if isinstance(value, dict):
                if "target" in value and "messages" in value:
                    return value
                children = value.values()
            elif isinstance(value, list):
                children = value
            elif isinstance(value, str):
                try:
                    return page(json.loads(value))
                except ValueError:
                    for line in value.splitlines():
                        if line.startswith("{") and line != value:
                            found = page(line)
                            if found:
                                return found
                    return None
            else:
                return None
            for child in children:
                found = page(child)
                if found:
                    return found
            return None

        return page(text) or {"unparsed": text}

    encoded = json.dumps(body)
    if "You are now acting as a compaction engine" in encoded:
        return [
            {
                "type": "text",
                "text": f"<summary>SUMMARY_RETRY_CASE_{case_id}: Continue source validation. Raw Inbox pages are intentionally omitted.</summary>",
            }
        ]
    # The child is a real host subagent, not a forged inherited source context.
    if (
        "SOURCE_CHILD_ACTION" in encoded
        and f"{prefix}-check" not in calls
        and f"{prefix}-resumed" not in calls
    ):
        effect_id = f"effect-{case_id}"
        if effect_id not in calls:
            return [
                tool(
                    "bash",
                    {
                        "description": "Record inherited source action",
                        "command": f"printf '{case_id}\\n' >> retry-effects.txt # RETRY_CASE_{case_id}",
                    },
                    effect_id,
                )
            ]
        return [{"type": "text", "text": "SOURCE_CHILD_COMPLETE"}]
    if case.get("compacted"):
        if f"{prefix}-resumed" not in calls:
            return call(
                "inbox",
                {"action": "read", "target": case["target"], "limit": 1},
                "resumed",
            )
        if f"{prefix}-child" not in calls:
            return call(
                "subagent",
                {
                    "description": "Check compacted sources",
                    "prompt": f"SOURCE_CHILD_ACTION RETRY_CASE_{case_id}: record exactly one isolated bash action.",
                    "run_in_background": False,
                },
                "child",
            )
        if f"{prefix}-delivered" not in calls:
            return call(
                "send_message",
                {"target": case["target"], "text": f"SOURCE_DONE_{case_id}"},
                "delivered",
            )
        return [{"type": "text", "text": "SOURCE_ROOT_COMPLETE"}]
    if case.get("ptc") and f"{prefix}-install" not in calls:
        return call(
            "plugin_manager",
            {"action": "install_bundle", "target": case["bundle"]},
            "install",
        )
    if f"{prefix}-check" not in calls:
        return call("inbox", {"action": "check"}, "check")
    reads = [key for key in calls if key.startswith(f"{prefix}-read-")]
    if not reads:
        args = {"action": "read", "target": case["target"], "limit": 1}
        if case.get("ptc"):
            return call(
                "run_code",
                {
                    "description": "Read one real Inbox fragment through PTC",
                    "code": f"console.log(JSON.stringify(await tools.inbox({json.dumps(args)})))",
                },
                "read-0",
            )
        return call("inbox", args, "read-0")
    index = len(reads) - 1
    page = result(f"read-{index}")
    if page.get("next_cursor"):
        return call(
            "inbox",
            {
                "action": "read",
                "target": case["target"],
                "limit": 1,
                "cursor": page["next_cursor"],
            },
            f"read-{index + 1}",
        )
    if case.get("ptc") and f"{prefix}-distinct-read" not in calls:
        # Exercise a distinct direct call as well as the observed PTC page. It
        # also lets the real host commit any fragment still unread after PTC.
        return call(
            "inbox",
            {"action": "read", "target": case["target"], "limit": 1},
            "distinct-read",
        )
    if f"{prefix}-proposal" not in calls:
        return call(
            "send_message",
            {"target": case["target"], "text": f"SOURCE_PROPOSAL_{case_id}"},
            "proposal",
        )
    if case.get("held") and f"{prefix}-held" not in calls:
        deadline = time.monotonic() + 15
        while not case.get("held_release") and time.monotonic() < deadline:
            time.sleep(0.01)
        if not case.get("held_release"):
            raise TimeoutError("Source fixture barrier was not released in 15s")
        return call(
            "send_message",
            {"target": case["target"], "text": f"SOURCE_HELD_PROPOSAL_{case_id}"},
            "held",
        )
    if case.get("held") and f"{prefix}-revalidated" not in calls:
        return call(
            "inbox",
            {"action": "read", "target": case["target"], "limit": 1},
            "revalidated",
        )
    if case.get("delegate") is False:
        return [{"type": "text", "text": "SOURCE_WAIT_FOR_RESTART"}]
    if case.get("resumed") and f"{prefix}-resumed" not in calls:
        return call(
            "inbox", {"action": "read", "target": case["target"], "limit": 1}, "resumed"
        )
    if f"{prefix}-child" not in calls:
        return call(
            "subagent",
            {
                "description": "Check source retention",
                "prompt": f"SOURCE_CHILD_ACTION RETRY_CASE_{case_id}: record exactly one isolated bash action.",
                "run_in_background": False,
            },
            "child",
        )
    if f"{prefix}-delivered" not in calls:
        return call(
            "send_message",
            {"target": case["target"], "text": f"SOURCE_DONE_{case_id}"},
            "delivered",
        )
    return [{"type": "text", "text": "SOURCE_ROOT_COMPLETE"}]
