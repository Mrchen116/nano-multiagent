#!/usr/bin/env python3
"""Transform old async stub clients to new SSE API."""

import re


def find_method_bounds(lines, start_idx):
    """Find the end index of a method given its starting line index."""
    base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    i = start_idx + 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.strip().startswith("#"):
            break
        i += 1
    return i


def transform_send_message_async_method(lines, start_idx, end_idx):
    """Transform send_message_async method to submit_message."""
    result = []
    for line in lines[start_idx:end_idx]:
        if "def send_message_async(self, *, session_id: str, text: str)" in line:
            indent = len(line) - len(line.lstrip())
            result.append(
                " " * indent
                + 'def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:\n'
            )
        elif '"send_message_async"' in line:
            result.append(line.replace('"send_message_async"', '"submit_message"'))
        else:
            result.append(line)
    return result


def transform_stream_session_events_method(lines, start_idx, end_idx):
    """Transform stream_session_events method to stream_session async generator."""
    result = []
    in_event_dict = False
    event_dict_indent = 0
    data_nesting = 0
    event_dict_lines = []
    current_event_name = None

    i = start_idx
    while i < end_idx:
        line = lines[i]

        # Transform signature
        if "def stream_session_events(" in line:
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + "async def stream_session(self, *, session_id: str, last_event_id: int | None = None):\n")
            i += 1
            continue

        # Skip parameter lines and return type annotation
        if any(p in line for p in ["after_sequence", "max_events", "timeout_seconds", "-> list[dict[str, object]]"]) and not line.strip().startswith("self.calls"):
            if line.strip() == ")":
                pass  # skip
            i += 1
            continue

        # Skip del line
        if "del after_sequence" in line or "del session_id, after_sequence" in line:
            i += 1
            continue

        # Transform call logging
        if '"stream_session_events"' in line:
            result.append(line.replace('"stream_session_events"', '"stream_session"'))
            i += 1
            continue

        # Transform return [ to for _event in [
        if re.match(r'^\s*return\s*\[\s*$', line):
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + "for _event in [\n")
            i += 1
            continue

        # Close the list with yield
        if line.strip() == "]" and not in_event_dict:
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + "]:\n")
            result.append(" " * (indent + 4) + "yield _event\n")
            i += 1
            continue

        # Empty return [] -> just skip (yield nothing)
        if re.match(r'^\s*return\s*\[\s*\]\s*$', line):
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + "return\n")
            i += 1
            continue

        # Handle event dict transformation
        # Detect start of event dict: {"event_id": ..., "event": "...", "data": {...}}
        # We'll do this by looking for the pattern line-by-line

        result.append(line)
        i += 1

    # Post-process: transform event dicts in the result
    return transform_event_dicts_in_method(result)


def transform_event_dicts_in_method(lines):
    """Transform event dicts from old format to new format."""
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this line starts an event dict with event_id
        m = re.match(r'^(\s*)\{\s*"event_id":\s*"[^"]*",\s*$', line)
        if m:
            indent = m.group(1)
            event_lines = [line]
            j = i + 1
            brace_count = 1
            while j < len(lines) and brace_count > 0:
                jl = lines[j]
                event_lines.append(jl)
                brace_count += jl.count("{") - jl.count("}")
                j += 1

            transformed = transform_single_event_dict(event_lines)
            result.extend(transformed)
            i = j
            continue

        # Check if line starts an event dict without event_id but with event and data
        m2 = re.match(r'^(\s*)\{\s*"event":\s*"([^"]*)",\s*"data":\s*\{\s*$', line)
        if m2:
            indent = m2.group(1)
            event_name = m2.group(2)
            event_lines = [line]
            j = i + 1
            brace_count = 2  # outer dict + data dict
            while j < len(lines) and brace_count > 0:
                jl = lines[j]
                event_lines.append(jl)
                brace_count += jl.count("{") - jl.count("}")
                j += 1

            transformed = transform_single_event_dict(event_lines)
            result.extend(transformed)
            i = j
            continue

        result.append(line)
        i += 1

    return result


def transform_single_event_dict(lines):
    """Transform one event dict from old format to new format."""
    text = "".join(lines)

    # Extract event name
    event_match = re.search(r'"event":\s*"([^"]*)"', text)
    if not event_match:
        return lines
    event_name = event_match.group(1)

    # For text_delta, change to assistant_message and delta to content
    if event_name == "text_delta":
        event_name = "assistant_message"
        text = text.replace('"delta":', '"content":')

    # Remove event_id field
    text = re.sub(r'\s*"event_id":\s*"[^"]*",\s*\n', '\n', text)

    # Flatten data: replace "data": { with nothing, and the matching } with nothing
    # This is tricky. Let's use a brace-counting approach.
    lines_out = []
    in_data = False
    data_depth = 0
    data_started = False

    for line in lines:
        stripped = line.strip()

        if not in_data:
            if '"data":' in line and '{' in line:
                # Start of data dict
                # Replace "data": { with just the content before it
                prefix = line[:line.find('"data":')]
                rest = line[line.find('"data":') + len('"data":'):]
                rest = rest.strip()
                if rest.startswith('{'):
                    rest = rest[1:]
                    if rest.strip():
                        lines_out.append(prefix + rest.lstrip() + '\n')
                    in_data = True
                    data_depth = 1
                    data_started = True
                continue
            elif stripped == '{':
                lines_out.append(line)
                continue
            elif stripped.startswith('{'):
                lines_out.append(line)
                continue
            else:
                lines_out.append(line)
                continue
        else:
            # We're inside the data dict
            data_depth += line.count('{') - line.count('}')
            if data_depth <= 0:
                # End of data dict
                # Remove the closing brace
                # If there's content after }, keep it
                brace_idx = line.rfind('}')
                if brace_idx >= 0:
                    after = line[brace_idx + 1:]
                    if after.strip() and after.strip() != ',':
                        lines_out.append(line[:brace_idx] + after + '\n')
                    elif after.strip() == ',':
                        # Check if the line before had a trailing comma
                        prev = lines_out[-1].rstrip()
                        if not prev.endswith(','):
                            lines_out[-1] = prev + ',\n'
                in_data = False
                data_depth = 0
                continue
            else:
                lines_out.append(line)
                continue

    # Update event name
    for idx, line in enumerate(lines_out):
        if '"event": "text_delta"' in line:
            lines_out[idx] = line.replace('"event": "text_delta"', f'"event": "{event_name}"')

    return lines_out


def transform_file(path: str) -> None:
    with open(path, "r") as f:
        lines = f.readlines()

    # Find all method bounds first
    methods = []  # list of (start, end, type)
    i = 0
    while i < len(lines):
        line = lines[i]
        if "def send_message_async(" in line:
            end = find_method_bounds(lines, i)
            methods.append((i, end, "send_message_async"))
            i = end
        elif "def stream_session_events(" in line:
            end = find_method_bounds(lines, i)
            methods.append((i, end, "stream_session_events"))
            i = end
        else:
            i += 1

    # Sort methods by start index in reverse order so we can replace from end to start
    methods.sort(key=lambda x: x[0], reverse=True)

    for start, end, method_type in methods:
        if method_type == "send_message_async":
            new_lines = transform_send_message_async_method(lines, start, end)
        else:
            new_lines = transform_stream_session_events_method(lines, start, end)
        lines = lines[:start] + new_lines + lines[end:]

    with open(path, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    transform_file("tests/unit/test_cli_main.py")
    print("Transformation complete.")
