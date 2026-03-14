#!/usr/bin/env python3
import datetime, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = REPO_ROOT / ".claude/state/active-subagents.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG = REPO_ROOT / ".claude/state/hook-events.log"

data = json.loads(sys.stdin.read())

# Log raw stdin immediately so we can see what fires even if agent_id is missing
with LOG.open("a") as f:
    f.write(f"{datetime.datetime.now().isoformat()} SubagentStart raw={data}\n")

session_id = data.get("session_id", "")
agent_id = data.get("agent_id", "")
if not session_id or not agent_id:
    sys.exit(0)

state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"sessions": {}}
sessions = state.setdefault("sessions", {})
entry = sessions.setdefault(session_id, {"agent_ids": []})
agent_ids = entry.setdefault("agent_ids", [])
if agent_id not in agent_ids:
    agent_ids.append(agent_id)
STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))

with LOG.open("a") as f:
    f.write(
        f"{datetime.datetime.now().isoformat()} SubagentStart session_id={session_id} agent_id={agent_id} session_active={len(agent_ids)} total_sessions={len(sessions)}\n"
    )
