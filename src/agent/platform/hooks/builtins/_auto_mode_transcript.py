"""Project current conversation facts into the pinned Auto classifier transcript."""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Sequence

from agent.platform.hooks.builtins._auto_mode_policy import (
    AGENT_SOURCE_INSTRUCTIONS,
    SCHEDULED_SOURCE_INSTRUCTIONS,
    SUMMARY_SOURCE_INSTRUCTIONS,
    SYSTEM_SOURCE_INSTRUCTIONS,
    SYSTEM_WITH_HUMAN_SOURCE_INSTRUCTIONS,
    UNCLASSIFIED_SOURCE_INSTRUCTIONS,
)

SOURCE_INSTRUCTIONS = {
    "agent": AGENT_SOURCE_INSTRUCTIONS,
    "scheduled-trigger": SCHEDULED_SOURCE_INSTRUCTIONS,
    "system": SYSTEM_SOURCE_INSTRUCTIONS,
    "system-with-human": SYSTEM_WITH_HUMAN_SOURCE_INSTRUCTIONS,
    "summary": SUMMARY_SOURCE_INSTRUCTIONS,
    "unclassified": UNCLASSIFIED_SOURCE_INSTRUCTIONS,
}


def _get(value: Any, name: str, default: Any = None) -> Any:
    return (
        value.get(name, default)
        if isinstance(value, Mapping)
        else getattr(value, name, default)
    )


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        return "\n".join(
            b.get("text", "")
            for b in content
            if isinstance(b, Mapping) and b.get("type") == "text"
        )
    return ""


def _truncate(text: str, *, tail: bool = False) -> str:
    # CC's oe/ud count UTF-16 code units and remove a split boundary surrogate.
    encoded = text.encode("utf-16-le", errors="surrogatepass")
    if len(encoded) <= 4000:
        return text
    selected = encoded[-4000:] if tail else encoded[:4000]
    return selected.decode("utf-16-le", errors="ignore")


def _source_text(text: str, source: str | None, *, with_human: bool) -> str:
    key = "system-with-human" if source == "system" and with_human else source
    prefix = SOURCE_INSTRUCTIONS.get(key, "")
    if not prefix or text.startswith(prefix):
        return text
    return f"{prefix}\n\n{text}"


def build_transcript_entries(
    messages: Sequence[Any],
    *,
    project_tool_result: Callable[[str, Any], str | None] | None = None,
    prior_assistant_context: bool = True,
) -> list[dict[str, Any]]:
    """Select native user turns, paired assistant text and recorded tool facts.

    Args:
        messages: Current visible history with application-owned provenance.
        project_tool_result: Legacy persisted-result reader; never grants live status.
        prior_assistant_context: Enable the main-loop assistant-before-human branch.

    Returns:
        Entries preserving order and the original tool call identity and arguments.

    Raises:
        ValueError: A required host projection failed or returned an invalid value.
    """
    entries: list[dict[str, Any]] = []
    calls: dict[str, tuple[str, Any]] = {}
    pending_assistant: str | None = None

    def result(call_id: Any, content: Any, is_error: bool, message: Any) -> None:
        call = calls.pop(call_id, None) if isinstance(call_id, str) else None
        if call is None:
            return
        name, _args = call
        metadata = _get(message, "context_metadata", {}) or {}
        if metadata.get("host_projection_error"):
            raise ValueError(
                f"host projection failed for {name}: {metadata['host_projection_error']}"
            )
        outcome = metadata.get("tool_outcome") or {
            "status": "error" if is_error else "ok"
        }
        entries.append(
            {
                "role": "tool",
                "type": "outcome",
                "tool_call_id": call_id,
                "content": outcome,
            }
        )
        if is_error:
            return
        projected = metadata.get("host_classifier_context")
        materialized = isinstance(projected, str)
        if (
            "host_classifier_context" not in metadata
            and project_tool_result is not None
        ):
            projected = project_tool_result(name, content)
        if projected is not None and not isinstance(projected, str):
            raise ValueError(f"invalid classifier result projection for {name}")
        if projected:
            entries.append(
                {
                    "role": "tool",
                    "type": "host_context",
                    "name": name,
                    "tool_call_id": call_id,
                    "message_id": _get(message, "message_id") if materialized else None,
                    "content": projected,
                }
            )

    for message in messages:
        role = _get(message, "role")
        content = _get(message, "content")
        metadata = _get(message, "context_metadata", {}) or {}
        if role == "assistant":
            prose = _text(content)
            if prior_assistant_context and prose.strip():
                pending_assistant = _truncate(prose, tail=True)
            uses = (
                [
                    dict(block)
                    for block in content
                    if isinstance(block, Mapping) and block.get("type") == "tool_use"
                ]
                if isinstance(content, list)
                else []
            )
            if not uses:
                uses = [
                    {
                        "type": "tool_use",
                        "name": _get(call, "name", ""),
                        "input": dict(_get(call, "arguments", {}) or {}),
                        "id": _get(call, "call_id"),
                    }
                    for call in (_get(message, "tool_calls", ()) or ())
                ]
            for call in uses:
                if isinstance(call.get("id"), str):
                    calls[call["id"]] = (call.get("name", ""), call.get("input", {}))
            if uses:
                entries.append({"role": "assistant", "content": uses})
        elif role == "tool":
            result(
                _get(message, "tool_call_id"),
                content,
                _get(message, "is_error", False),
                message,
            )
        elif role == "user":
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, Mapping)
                        and block.get("type") == "tool_result"
                    ):
                        result(
                            block.get("tool_use_id"),
                            block.get("content"),
                            block.get("is_error", False),
                            message,
                        )
            parts = metadata.get("context_parts") or [
                {
                    "text": _text(content),
                    "context_origin": metadata.get("context_origin"),
                }
            ]
            with_human = metadata.get("context_has_human") or any(
                part.get("context_origin") == "human" for part in parts
            )
            for part in parts:
                text = part.get("text", "")
                if not text:
                    continue
                source = part.get("context_origin") or "human"
                if pending_assistant is not None and source == "human":
                    entries.append(
                        {
                            "role": "assistant",
                            "content": [{"type": "text", "text": pending_assistant}],
                        }
                    )
                pending_assistant = None
                entries.append(
                    {
                        "role": "user",
                        "content": _source_text(text, source, with_human=with_human),
                    }
                )
    return entries


def serialize_transcript(
    entries: Sequence[Mapping[str, Any]], *, live_context: Any = None
) -> str:
    """Serialize facts as CC-style JSON lines, computing host liveness at use time.

    Args:
        entries: Selected native and inherited conversation entries.
        live_context: Runtime's exact message/call/text registry, absent after restart.

    Returns:
        JSON lines safe to embed inside the transcript wrapper.
    """
    lines: list[str] = []

    def append(value: Any) -> None:
        line = json.dumps(value, ensure_ascii=False, default=str)
        for char in ("<", ">", "\u2028", "\u2029", "\u0085"):
            line = line.replace(char, f"\\u{ord(char):04x}")
        lines.append(line)

    for entry in entries:
        role = entry["role"]
        if role == "tool":
            call_id = entry["tool_call_id"]
            if entry["type"] == "outcome":
                append({"outcome": entry["content"], "id": call_id})
            else:
                content = entry["content"]
                live = live_context is not None and live_context.is_live(
                    entry.get("message_id"), call_id, content
                )
                append(
                    {
                        "host_context_live" if live else "host_context": _truncate(
                            content
                        ),
                        "id": call_id,
                    }
                )
        elif role == "user":
            append({"user": entry["content"]})
        elif role == "assistant":
            for block in entry["content"]:
                if block["type"] == "text":
                    append({"assistant": block["text"]})
                else:
                    name = block.get("name", "")
                    if name.strip().lower() in {
                        "user",
                        "assistant",
                        "id",
                        "outcome",
                        "meta",
                        "host_context",
                        "host_context_live",
                    }:
                        name = f"[{name}]"
                    append(
                        {
                            name: block.get("input", {}),
                            **({"id": block["id"]} if block.get("id") else {}),
                        }
                    )
    return "\n".join(lines)
