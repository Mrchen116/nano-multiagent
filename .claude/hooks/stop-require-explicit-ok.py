#!/usr/bin/env python3
import datetime, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = REPO_ROOT / ".claude/state/active-subagents.json"
EXEMPT = "NO_SUBAGENT_STOP_OK"

data = json.loads(sys.stdin.read())

session_id = data.get("session_id", "")
last_msg = data.get("last_assistant_message", "") or ""
stop_hook_active = data.get("stop_hook_active", True)

if stop_hook_active or EXEMPT in last_msg:
    sys.exit(0)

active = 0
if session_id and STATE_FILE.exists():
    try:
        state = json.loads(STATE_FILE.read_text())
        active = len(state.get("sessions", {}).get(session_id, {}).get("agent_ids", []))
    except Exception:
        pass

LOG = REPO_ROOT / ".claude/state/hook-events.log"
with LOG.open("a") as f:
    f.write(
        f"{datetime.datetime.now().isoformat()} Stop session_id={session_id} active_in_session={active} exempt={EXEMPT in last_msg}\n"
    )

if active > 0:
    sys.exit(0)

reason = (
    "当前没有任何 subagent 在运行，如果这不符合你的预期，请继续调用工具或继续推进，不要直接停下。"
    "如果你确认这次就是应该结束，请在你的下一条回复中明确写出：NO_SUBAGENT_STOP_OK"
)
print(json.dumps({"decision": "block", "reason": reason}))
sys.exit(0)
