#!/usr/bin/env python3
"""Transform old async stub clients in test_cli_main.py to new SSE API."""

import re

def transform_file(path: str) -> None:
    with open(path, "r") as f:
        lines = f.readlines()

    result = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Replace send_message_async signature
        if "def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:" in line:
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + 'def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:\n')
            i += 1
            continue

        # Replace send_message_async call logging
        if 'self.calls.append(("send_message_async",' in line:
            line = line.replace('"send_message_async"', '"submit_message"')
            result.append(line)
            i += 1
            continue

        # Detect stream_session_events signature start
        if "def stream_session_events(" in line:
            # Replace with async def stream_session signature
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + "async def stream_session(self, *, session_id: str, last_event_id: int | None = None):\n")
            i += 1
            # Skip old parameter lines until we hit the body
            while i < len(lines) and ("after_sequence" in lines[i] or "max_events" in lines[i] or "timeout_seconds" in lines[i] or "-> list[dict[str, object]]" in lines[i] or lines[i].strip() == ")"):
                i += 1
            continue

        # Replace stream_session_events call logging
        if 'self.calls.append(("stream_session_events",' in line:
            line = line.replace('"stream_session_events"', '"stream_session"')
            result.append(line)
            i += 1
            continue

        # Skip del after_sequence, max_events, timeout_seconds lines
        if "del after_sequence, max_events, timeout_seconds" in line or "del session_id, after_sequence, max_events, timeout_seconds" in line:
            i += 1
            continue

        result.append(line)
        i += 1

    # Second pass: transform event dicts inside stream_session methods
    content = "".join(result)

    # Pattern 1: text_delta events -> assistant_message with content
    # Match {"event_id": "...", "event": "text_delta", "data": {"run_id": "...", "delta": "..."}}
    def replace_text_delta_event(m):
        run_id = m.group(1)
        delta = m.group(2)
        # Escape any quotes in delta
        delta_escaped = delta.replace('"', '\\"')
        return f'{{\n                    "event": "assistant_message",\n                    "run_id": "{run_id}",\n                    "content": "{delta_escaped}",\n                }}'

    content = re.sub(
        r'\{\s*"event_id":\s*"[^"]*",\s*"event":\s*"text_delta",\s*"data":\s*\{\s*"run_id":\s*"([^"]*)",\s*"delta":\s*"((?:[^"\\]|\\.)*)"\s*\}\s*\}',
        replace_text_delta_event,
        content,
    )

    # Also handle text_delta with event but no event_id
    content = re.sub(
        r'\{\s*"event":\s*"text_delta",\s*"data":\s*\{\s*"run_id":\s*"([^"]*)",\s*"delta":\s*"((?:[^"\\]|\\.)*)"\s*\}\s*\}',
        replace_text_delta_event,
        content,
    )

    # Pattern 2: other events with event_id -> flatten data
    def replace_event_with_event_id(m):
        event_name = m.group(1)
        data_content = m.group(2).strip()
        # Remove trailing comma if present for clean join
        data_content = data_content.rstrip().rstrip(",")
        return f'{{\n                    "event": "{event_name}",\n                    {data_content},\n                }}'

    content = re.sub(
        r'\{\s*"event_id":\s*"[^"]*",\s*"event":\s*"([^"]*)",\s*"data":\s*\{([\s\S]*?)\}\s*\}',
        replace_event_with_event_id,
        content,
    )

    # Pattern 3: events without event_id -> flatten data
    def replace_event_without_event_id(m):
        event_name = m.group(1)
        data_content = m.group(2).strip()
        data_content = data_content.rstrip().rstrip(",")
        return f'{{\n                    "event": "{event_name}",\n                    {data_content},\n                }}'

    content = re.sub(
        r'\{\s*"event":\s*"([^"]*)",\s*"data":\s*\{([\s\S]*?)\}\s*\}',
        replace_event_without_event_id,
        content,
    )

    # Third pass: transform return [ ... ] to for _event in [ ... ]: yield _event
    # This is tricky with regex. Let's do a simpler approach for specific patterns.

    with open(path, "w") as f:
        f.write(content)


if __name__ == "__main__":
    transform_file("tests/unit/test_cli_main.py")
    print("Transformation complete.")
