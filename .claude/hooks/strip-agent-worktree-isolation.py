#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime

DEBUG_LOG = Path(".claude/state/pretooluse-agent.log")


def log(msg: str) -> None:
    DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        log(f"[ERROR] failed to parse stdin json: {e}")
        return 0

    hook_event_name = payload.get("hook_event_name")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}

    # 只处理 Agent 工具
    if hook_event_name != "PreToolUse" or tool_name != "Agent":
        return 0

    # 调试日志：先看真实输入长什么样
    log(f"[INPUT] tool_input={json.dumps(tool_input, ensure_ascii=False)}")

    # 如果没有 isolation，或者不是 worktree，直接放过
    if tool_input.get("isolation") != "worktree":
        return 0

    # 复制一份并删除 isolation 字段
    updated_input = dict(tool_input)
    updated_input.pop("isolation", None)

    log(
        f"[REWRITE] removed isolation=worktree; updated_input={json.dumps(updated_input, ensure_ascii=False)}"
    )

    # PreToolUse 通过 hookSpecificOutput 返回 permissionDecision + updatedInput
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": (
                'Removed Agent tool parameter isolation="worktree" for this project.'
            ),
            "updatedInput": updated_input,
            "additionalContext": (
                'In this project, Agent tool calls must not use isolation="worktree". '
                "The isolation field was removed automatically. "
                "Continue without worktree isolation."
            ),
        }
    }

    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
