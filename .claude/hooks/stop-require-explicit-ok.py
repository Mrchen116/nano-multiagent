#!/usr/bin/env python3
import json, sys
from pathlib import Path

STATE_FILE = Path(".claude/state/active-subagents.json")
EXEMPT = "NO_SUBAGENT_STOP_OK"

data = json.loads(sys.stdin.read())

last_msg = data.get("last_assistant_message", "") or ""

if EXEMPT in last_msg:
    sys.exit(0)

# Check active subagents
active = 0
if STATE_FILE.exists():
    try:
        state = json.loads(STATE_FILE.read_text())
        active = len(state.get("agents", {}))
    except Exception:
        pass

if active > 0:
    sys.exit(0)

# Block
reason = (
    "<systeam_reminder>当前没有任何 subagent 在运行。"
    "如果你其实还需要继续处理，请继续调用工具或继续推进，不要直接停下。"
    "如果你确认这次就是应该结束，请在你的下一条回复中明确写出：NO_SUBAGENT_STOP_OK"
)
print(json.dumps({"decision": "block", "reason": reason}))
sys.exit(0)
