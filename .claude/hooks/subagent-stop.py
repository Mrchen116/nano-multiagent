#!/usr/bin/env python3
import datetime, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = REPO_ROOT / ".claude/state/active-subagents.json"
LOG = REPO_ROOT / ".claude/state/hook-events.log"

data = json.loads(sys.stdin.read())
session_id = data.get("session_id", "")
agent_id = data.get("agent_id", "")
if not session_id or not agent_id or not STATE_FILE.exists():
    sys.exit(0)

state = json.loads(STATE_FILE.read_text())
sessions = state.setdefault("sessions", {})
entry = sessions.get(session_id)
if entry is None:
    sys.exit(0)

agent_ids = entry.setdefault("agent_ids", [])
entry["agent_ids"] = [current for current in agent_ids if current != agent_id]
if not entry["agent_ids"]:
    sessions.pop(session_id, None)

STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))

with LOG.open("a") as f:
    f.write(
        f"{datetime.datetime.now().isoformat()} SubagentStop session_id={session_id} agent_id={agent_id} remaining_in_session={len(entry.get('agent_ids', [])) if session_id in sessions else 0} total_sessions={len(sessions)}\n"
    )
