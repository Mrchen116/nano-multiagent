#!/usr/bin/env python3
import json, sys
from pathlib import Path

STATE_FILE = Path(".claude/state/active-subagents.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

data = json.loads(sys.stdin.read())
agent_id = data.get("agent_id", "")
if not agent_id:
    sys.exit(0)

state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"agents": {}}
state["agents"][agent_id] = {"agent_id": agent_id}
STATE_FILE.write_text(json.dumps(state, indent=2))
