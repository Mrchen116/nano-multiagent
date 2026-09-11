"""Carry application-owned message provenance without provider-specific fields."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from threading import Lock
from typing import Any, Mapping, Sequence

from agent.core.agent.state import InputPart
from agent.core.llm.interfaces import LLMMessage


def classifier_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Select context facts without copying persistence or delivery bookkeeping."""
    keys = {
        "context_origin",
        "context_parts",
        "context_has_human",
        "is_compact_summary",
        "host_classifier_context",
        "host_projection_error",
        "tool_outcome",
        "inherited_approval_context",
    }
    return {key: value for key, value in metadata.items() if key in keys}


def origin_for_input(origin: Any, metadata: Mapping[str, Any] | None = None) -> str:
    """Resolve the source of an input independently of scheduling priority.

    Args:
        origin: Run origin supplied by the caller.
        metadata: Application-owned session or input metadata.

    Returns:
        The original speaker/source category.
    """
    metadata = metadata or {}
    explicit = metadata.get("context_origin")
    if isinstance(explicit, str) and explicit:
        return explicit
    if metadata.get("kind") == "subagent":
        return "agent"
    value = getattr(origin, "value", origin)
    if value == "cron":
        return "scheduled-trigger"
    if value in {"heartbeat", "background_task", "workflow"}:
        return "system"
    return "human" if value in {None, "", "human", "user"} else "unclassified"


def input_context_metadata(
    parts: Sequence[InputPart], *, origin: Any, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Preserve each submitted part's source, including mixed steer batches.

    Args:
        parts: Parsed input parts supplied by the application.
        origin: Scheduling origin of this turn.
        metadata: Session-owned identity and default source.

    Returns:
        Persistable provenance for the complete input message.
    """
    default = origin_for_input(origin, metadata)
    entries = [
        {
            "type": part.type,
            **({"text": part.text} if part.type == "text" else {}),
            "context_origin": part.metadata.get("context_origin") or default,
        }
        for part in parts
    ]
    sources = {entry["context_origin"] for entry in entries}
    result = {
        "context_origin": next(iter(sources)) if len(sources) == 1 else default,
        "context_parts": entries,
    }
    if {"human", "system"} <= sources or any(
        part.metadata.get("context_has_human") for part in parts
    ):
        result["context_has_human"] = True
    for part in parts:
        inherited = part.metadata.get("inherited_approval_context")
        if isinstance(inherited, Mapping):
            result["inherited_approval_context"] = dict(inherited)
    return result


def render_source_message(
    message: LLMMessage, instructions: Mapping[str, str]
) -> LLMMessage:
    """Annotate model input using source descriptions supplied by the platform.

    Args:
        message: Runtime message carrying its unmodified source facts.
        instructions: Source category to description, owned by the caller.

    Returns:
        A wire-compatible message with source descriptions in text content.
    """
    if message.role != "user" or not instructions:
        return message
    metadata = message.context_metadata
    entries = metadata.get("context_parts") or [
        {"text": message.content, "context_origin": metadata.get("context_origin")}
    ]
    with_human = metadata.get("context_has_human") or any(
        e.get("context_origin") == "human" for e in entries
    )

    def annotate(text: str, source: Any) -> str:
        key = "system-with-human" if source == "system" and with_human else source
        description = instructions.get(key, "")
        return f"{description}\n\n{text}" if description else text

    if isinstance(message.content, str):
        content: Any = "\n".join(
            annotate(e["text"], e.get("context_origin"))
            for e in entries
            if isinstance(e.get("text"), str)
        )
    else:
        part_entries = iter(entries)
        content = []
        for block in message.content:
            entry = next(part_entries, {})
            source = entry.get("context_origin", metadata.get("context_origin"))
            if block.get("type") == "text":
                content.append(
                    {**block, "text": annotate(block.get("text", ""), source)}
                )
            else:
                if source in instructions:
                    content.append({"type": "text", "text": annotate("", source)})
                content.append(block)
    return replace(message, content=content)


def restore_input_parts(
    content: Any, metadata: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Restore submitted parts without reinterpreting their persisted source.

    Args:
        content: Persisted text or structured content blocks.
        metadata: Message-owned source and accepted delegation context.

    Returns:
        Canonical submit parts retaining each original part's provenance.
    """
    shared = {
        key: metadata[key]
        for key in ("context_origin", "context_has_human", "inherited_approval_context")
        if key in metadata
    }
    entries = metadata.get("context_parts") or ()
    if isinstance(content, str):
        if entries:
            return [{**shared, **dict(entry)} for entry in entries]
        return [{"type": "text", "text": content, **shared}]
    parts = []
    for index, part in enumerate(content):
        entry = entries[index] if index < len(entries) else {}
        parts.append(
            {
                **dict(part),
                **shared,
                "context_origin": entry.get(
                    "context_origin", metadata.get("context_origin")
                ),
            }
        )
    return parts


class LiveToolContext:
    """Remember host facts produced by this runtime, never facts loaded from disk."""

    def __init__(self) -> None:
        self._entries: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._lock = Lock()

    def register(self, message_id: str, call_id: str, content: str) -> None:
        """Register one result's exact identity and materialized host text."""
        with self._lock:
            self._entries[(message_id, call_id)] = content
            while len(self._entries) > 10000:
                self._entries.popitem(last=False)

    def is_live(
        self, message_id: str | None, call_id: str | None, content: str
    ) -> bool:
        """Return whether both result identity and original text still match."""
        with self._lock:
            return self._entries.get((message_id, call_id)) == content

    def clear(self) -> None:
        """Discard provenance when the owning runtime closes."""
        with self._lock:
            self._entries.clear()
