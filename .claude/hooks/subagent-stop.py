#!/usr/bin/env python3
import json, sys
from pathlib import Path

STATE_FILE = Path(".claude/state/active-subagents.json")

data = json.loads(sys.stdin.read())
agent_id = data.get("agent_id", "")
if not agent_id or not STATE_FILE.exists():
    sys.exit(0)

state = json.loads(STATE_FILE.read_text())
state["agents"].pop(agent_id, None)
STATE_FILE.write_text(json.dumps(state, indent=2))
