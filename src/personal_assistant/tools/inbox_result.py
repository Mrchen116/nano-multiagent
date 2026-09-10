"""Model-facing Inbox content, independent of delivery receipts and UI details."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _time(value: str | None) -> str | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def source_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    """Return the facts needed to choose a pending conversation."""
    result = {"target": source["target"]}
    if source.get("name") and source["name"] != source["target"]:
        result["name"] = source["name"]
    result["unread"] = source["pending_count"]
    timestamp = _time(
        source.get("latest_message_at") or source.get("latest_received_at")
    )
    if timestamp:
        result["latest_at"] = timestamp
    if "mention" in source.get("attention_reasons", []):
        result["mentioned"] = True
    return result


def model_page(page: Mapping[str, Any]) -> dict[str, Any]:
    """Project a receipt-backed page without exposing internal accounting fields.

    Message parts on this page are grouped in source order. A partial message
    remains explicitly partial even when earlier parts were read on another page.
    """
    if "conversations" in page:
        result = {
            "conversations": [source_summary(row) for row in page["conversations"]]
        }
    else:
        result = {"target": page.get("target")}
        if page.get("name") and page["name"] != page.get("target"):
            result["name"] = page["name"]
        messages: list[dict[str, Any]] = []
        grouped: dict[str, dict[str, Any]] = {}
        for index, part in enumerate(page.get("messages", [])):
            message_id = part.get("message_id")
            key = (
                f"entry:{part['entry_seq']}"
                if part.get("entry_seq") is not None
                else message_id or f"anonymous:{index}"
            )
            if key not in grouped:
                sender = part.get("sender", {})
                message: dict[str, Any] = {}
                if message_id:
                    message["id"] = message_id
                if sender.get("name") and sender["name"] != sender.get("id"):
                    message["sender"] = sender["name"]
                if sender.get("id"):
                    message["sender_id"] = sender["id"]
                message["sender_type"] = sender.get("kind", "unknown")
                timestamp = _time(part.get("source_time") or part.get("received_at"))
                if timestamp:
                    message["time"] = timestamp
                message["content"] = []
                grouped[key] = message
                messages.append(message)
            message = grouped[key]
            message["content"].extend(part.get("content", []))
            if not part.get("complete_message", True):
                message["partial"] = True
        for message in messages:
            content = message["content"]
            if all(block.get("type") == "text" for block in content):
                message["text"] = "".join(block.get("text", "") for block in content)
                del message["content"]
        result["messages"] = messages
    if page.get("next_cursor"):
        result["next_cursor"] = page["next_cursor"]
    if page.get("errors"):
        result["errors"] = [
            {
                key: error[key]
                for key in ("code", "message_id", "retryable")
                if key in error
            }
            for error in page["errors"]
        ]
    return result
