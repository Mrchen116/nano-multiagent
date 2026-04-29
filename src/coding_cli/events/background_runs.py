"""Background-origin run event handling for the interactive REPL."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BackgroundRunEventProcessor:
    """Track and format non-user run events for one subscribed session."""

    seen_run_ids: set[str] = field(default_factory=set)
    pending_events: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def process(self, event: dict[str, object]) -> list[str]:
        """Return display lines produced by a background-origin event."""
        event_name = event.get("event")
        run_id = event.get("run_id")
        if event_name == "run_status":
            return self._process_run_status(event=event, run_id=run_id)
        if not isinstance(run_id, str) or not run_id.strip():
            return []
        if run_id in self.seen_run_ids:
            return _format_background_event_lines(event)
        self.pending_events.setdefault(run_id, []).append(event)
        return []

    def _process_run_status(self, *, event: dict[str, object], run_id: object) -> list[str]:
        origin = event.get("origin")
        if not isinstance(origin, str) or origin.strip() in ("", "user"):
            return []
        if not isinstance(run_id, str) or not run_id.strip():
            return []

        lines: list[str] = []
        if run_id not in self.seen_run_ids:
            self.seen_run_ids.add(run_id)
            header = format_origin_header(event)
            if header:
                lines.append(header)
        for pending in self.pending_events.pop(run_id, []):
            lines.extend(_format_background_event_lines(pending))
        return lines


def format_origin_header(event: dict[str, object]) -> str | None:
    """Format a display header for a non-user run_status event."""
    origin = event.get("origin")
    if not isinstance(origin, str) or origin.strip() == "" or origin == "user":
        return None
    source_task_id = event.get("source_task_id")
    if origin == "background_task" and isinstance(source_task_id, str) and source_task_id.strip():
        return f"── background wake (task_id={source_task_id.strip()}) ──"
    if origin == "heartbeat":
        return "── heartbeat ──"
    return f"── origin: {origin.strip()} ──"


def _format_background_event_lines(event: dict[str, object]) -> list[str]:
    event_name = event.get("event")
    if event_name == "assistant_message":
        content = event.get("content") or ""
        if not content:
            return []
        lines = content.split("\n")
        while lines and lines[-1] == "":
            lines.pop()
        return [f"> {line}" for line in lines]
    if event_name == "tool_start":
        name = str(event.get("name") or "?")
        return [f"  ▸ {name}"]
    if event_name == "tool_end":
        name = str(event.get("name") or "?")
        duration_ms = event.get("duration_ms")
        duration_str = ""
        if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
            duration_str = f" ({int(duration_ms)}ms)"
        return [f"  ✓ {name}{duration_str}"]
    return []
