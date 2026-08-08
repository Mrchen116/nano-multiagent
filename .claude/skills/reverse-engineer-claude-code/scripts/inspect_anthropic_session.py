#!/usr/bin/env python3
"""Summarize Anthropic Messages API request captures from an LLM Proxy session."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SENSITIVE_KEY = re.compile(
    r"(?:authorization|api[_-]?key|auth[_-]?token|access[_-]?token|secret|password|cookie)",
    re.IGNORECASE,
)
SENSITIVE_VALUE = re.compile(
    r"(?i)(?:bearer\s+)[A-Za-z0-9._~+/=-]+|\bsk-[A-Za-z0-9_-]{8,}\b"
)


def redact(value: Any) -> Any:
    """Return a recursively redacted copy suitable for terminal inspection."""
    if isinstance(value, dict):
        return {
            key: "<redacted>" if SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SENSITIVE_VALUE.sub("<redacted>", value)
    return value


def system_text(system: Any) -> str:
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in system
        )
    return ""


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def effort_of(request: dict[str, Any]) -> Any:
    output_config = request.get("output_config")
    if isinstance(output_config, dict) and "effort" in output_config:
        return output_config["effort"]
    return request.get("effort")


def load_requests(session_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    captures: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(session_dir.rglob("*-req-anthropic_messages.json")):
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, dict):
            captures.append((path, value))
    return captures


def summarize(path: Path, request: dict[str, Any]) -> dict[str, Any]:
    tools = request.get("tools") or []
    tool_names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
    prompt = system_text(request.get("system"))
    return {
        "file": path.name,
        "model": request.get("model"),
        "effort": effort_of(request),
        "system_chars": len(prompt),
        "system_sha256_16": digest(prompt),
        "messages": len(request.get("messages") or []),
        "tools": tool_names,
    }


def matching_tools(
    captures: list[tuple[Path, dict[str, Any]]], tool_name: str
) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path, request in captures:
        for tool in request.get("tools") or []:
            if not isinstance(tool, dict) or tool.get("name") != tool_name:
                continue
            canonical = json.dumps(tool, ensure_ascii=False, sort_keys=True)
            key = digest(canonical)
            found.setdefault(
                key,
                {"sha256_16": key, "first_seen": path.name, "tool": redact(tool)},
            )
    return list(found.values())


def render_text(
    captures: list[tuple[Path, dict[str, Any]]],
    tool_name: str | None,
    show_system: bool,
    show_last_message: bool,
) -> None:
    print("file\tmodel\teffort\tsystem_chars\tmessages\ttools")
    for path, request in captures:
        row = summarize(path, request)
        print(
            f"{row['file']}\t{row['model']}\t{row['effort']}\t"
            f"{row['system_chars']}\t{row['messages']}\t{','.join(row['tools'])}"
        )

    if tool_name:
        for item in matching_tools(captures, tool_name):
            print(
                f"\n=== tool {tool_name} sha256:{item['sha256_16']} "
                f"first_seen:{item['first_seen']} ==="
            )
            print(json.dumps(item["tool"], ensure_ascii=False, indent=2))

    if show_system:
        seen: set[str] = set()
        for path, request in captures:
            prompt = system_text(request.get("system"))
            key = digest(prompt)
            if key in seen:
                continue
            seen.add(key)
            print(f"\n=== system sha256:{key} first_seen:{path.name} ===")
            print(redact(prompt))

    if show_last_message:
        for path, request in captures:
            messages = request.get("messages") or []
            if not messages:
                continue
            print(f"\n=== last_message {path.name} ===")
            print(json.dumps(redact(messages[-1]), ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--tool", help="print each unique matching tool definition")
    parser.add_argument("--show-system", action="store_true")
    parser.add_argument("--show-last-message", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    captures = load_requests(args.session_dir)
    if not captures:
        raise SystemExit(
            f"no Anthropic request captures found under {args.session_dir}"
        )

    if args.as_json:
        result: dict[str, Any] = {
            "session_dir": str(args.session_dir),
            "requests": [summarize(path, request) for path, request in captures],
        }
        if args.tool:
            result["matching_tools"] = matching_tools(captures, args.tool)
        if args.show_system:
            result["systems"] = [
                {
                    "file": path.name,
                    "sha256_16": digest(system_text(request.get("system"))),
                    "text": redact(system_text(request.get("system"))),
                }
                for path, request in captures
            ]
        if args.show_last_message:
            result["last_messages"] = [
                {
                    "file": path.name,
                    "message": redact((request.get("messages") or [None])[-1]),
                }
                for path, request in captures
            ]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    render_text(captures, args.tool, args.show_system, args.show_last_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
