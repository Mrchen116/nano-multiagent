#!/usr/bin/env bash
# scripts/e2e-resilience.sh — bugfix-446 real-stack connection-resilience e2e.
#
# Drives a real IM + real Gateway (separate processes, ephemeral port, isolated config)
# and verifies the gateway recovers its IM node to "online" after transient faults,
# WITHOUT any manual restart of the Gateway process:
#
#   Scenario A (IM restart):  online → kill IM → restart IM → node auto back online.
#   Scenario B (start order):  start Gateway BEFORE IM (IM down) → Gateway does not crash
#                              → start IM → node comes online.
#
# Why no LLM proxy gate: connection resilience is purely node register/heartbeat over the
# gateway↔IM websocket, observable via GET /im/v1/nodes. No model call is made. (The
# gateway config still needs an llm: section to start — refactor-382 — but it is never used.)
#
# Machine "sleep" cannot be simulated in CI; killing the IM process / dropping the socket is
# the equivalent observable fault (socket dies, gateway must reconnect). See design decision 5.
#
# Usage:
#   scripts/e2e-resilience.sh                       # self-managed tmp workdir
#   scripts/e2e-resilience.sh --wt /path/to/workdir # explicit workdir (pytest passes a tmp)
#   scripts/e2e-resilience.sh --main-config /cfg.yaml

set -euo pipefail

WT_ROOT=""
MAIN_CFG="${HOME}/.nano-assistant/config.yaml"
PREPARE_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepare-only) PREPARE_ONLY=1; shift ;;
    --wt) WT_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    --main-config) MAIN_CFG="$2"; shift 2 ;;
    -h|--help) sed -n '2,/^set -e/p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -f "$MAIN_CFG" ]]; then
  echo "main config not found: $MAIN_CFG (see AGENTS.md, must include the llm: section)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$REPO_ROOT/src"
FREE_PORTS_SH="$REPO_ROOT/scripts/free-ports.sh"

[[ -n "$WT_ROOT" ]] || WT_ROOT="$(mktemp -d)"
echo "resilience e2e workdir: $WT_ROOT"

# ─── helpers ─────────────────────────────────────────────────────────────────

stop_pidfile() {
  local pidfile=$1 pid
  [[ -f "$pidfile" ]] || return 0
  pid=$(cat "$pidfile")
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in {1..30}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}

cleanup() {
  stop_pidfile "$WT_ROOT/.gateway.pid"
  stop_pidfile "$WT_ROOT/.im.pid"
}
trap cleanup EXIT

start_im() {
  # Reuse the same cwd-relative DB across restarts within one run so the node binding
  # persists (that is exactly what makes auto-recovery observable). The DB is only wiped
  # by reset_im_state at the start of each scenario.
  cd "$WT_ROOT"
  IM_JWT_SECRET="$JWT_SECRET" PYTHONPATH="$SRC_DIR" \
    python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" \
    >> "$WT_ROOT/.im.log" 2>&1 &
  echo $! > "$WT_ROOT/.im.pid"
  for _ in $(seq 1 50); do
    curl -sf "http://127.0.0.1:$IM_PORT/openapi.json" >/dev/null 2>&1 && return 0
    sleep 0.2
  done
  echo "IM failed to start; see $WT_ROOT/.im.log" >&2
  tail -20 "$WT_ROOT/.im.log" >&2 || true
  return 1
}

register_nano() {
  curl -sf -X POST "http://127.0.0.1:$IM_PORT/im/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"username":"nano","password":"nano1234","display_name":"Test User"}' \
    >/dev/null 2>&1 || true  # idempotent: ignore "already registered"
}

reset_im_state() {
  rm -f "$WT_ROOT/data/im_service.sqlite3" "$WT_ROOT/heartbeat-state.json"
  : > "$WT_ROOT/.im.log"
}

start_gateway() {
  cd "$REPO_ROOT"
  : > "$WT_ROOT/.gateway.log"
  PYTHONPATH="$SRC_DIR" python -m personal_assistant.main \
    --config "$WT_CFG" \
    --im-service-url "http://127.0.0.1:$IM_PORT" \
    --foreground \
    --auto-bind \
    > "$WT_ROOT/.gateway.log" 2>&1 &
  echo $! > "$WT_ROOT/.gateway.pid"
}

gateway_alive() { kill -0 "$(cat "$WT_ROOT/.gateway.pid" 2>/dev/null)" 2>/dev/null; }

# Print the status of our node ("" if not present yet). Logs in as nano each call.
node_status() {
  PYTHONPATH="$SRC_DIR" NODE_ID="$NODE_ID" IM_PORT="$IM_PORT" python3 - <<'PY' 2>/dev/null || true
import json, os, urllib.request
base = f"http://127.0.0.1:{os.environ['IM_PORT']}"
node_id = os.environ["NODE_ID"]
def post(path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=5))
try:
    tok = post("/im/v1/auth/login", {"username": "nano", "password": "nano1234"})
    token = tok.get("access_token") or tok.get("token") or ""
    req = urllib.request.Request(base + "/im/v1/nodes", headers={"Authorization": f"Bearer {token}"})
    nodes = json.load(urllib.request.urlopen(req, timeout=5))
    for n in nodes:
        if n.get("node_id") == node_id:
            print(n.get("status", ""))
            break
except Exception:
    pass
PY
}

poll_node_online() {
  local timeout=$1 desc=$2 deadline
  deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    [[ "$(node_status)" == "online" ]] && { echo "  ✓ $desc"; return 0; }
    gateway_alive || { echo "  ✗ $desc: gateway process died" >&2; tail -20 "$WT_ROOT/.gateway.log" >&2; return 1; }
    sleep 1
  done
  echo "  ✗ $desc: node not online within ${timeout}s (last status: '$(node_status)')" >&2
  tail -20 "$WT_ROOT/.gateway.log" >&2 || true
  return 1
}

# ─── derive isolated gateway config ──────────────────────────────────────────

read -r IM_PORT < <("$FREE_PORTS_SH" 1)
JWT_SECRET="resilience-$$-$(date +%s)"
WT_CFG="$WT_ROOT/.gateway-config.yaml"
WORKSPACE_DIR="$WT_ROOT/.gateway-workspace"
NODE_ID="wt-resilience-$$"
cp "$MAIN_CFG" "$WT_CFG"
if command -v yq >/dev/null 2>&1; then
  yq -i "
    .node.node_id = \"$NODE_ID\" |
    .node.workspace_base = \"$WORKSPACE_DIR\" |
    .im_service.url = \"http://127.0.0.1:$IM_PORT\" |
    .agents |= map(.workspace_root = \"$WORKSPACE_DIR/\" + .agent_id)
  " "$WT_CFG"
else
  WT_CFG_PY="$WT_CFG" NODE_ID="$NODE_ID" IM_PORT="$IM_PORT" WORKSPACE_DIR="$WORKSPACE_DIR" \
    python3 - <<'PY'
import os
import yaml

path = os.environ["WT_CFG_PY"]
with open(path) as f:
    cfg = yaml.safe_load(f)
cfg.setdefault("node", {})["node_id"] = os.environ["NODE_ID"]
workspace_dir = os.environ["WORKSPACE_DIR"]
cfg["node"]["workspace_base"] = workspace_dir
cfg.setdefault("im_service", {})["url"] = f"http://127.0.0.1:{os.environ['IM_PORT']}"
for agent in cfg.get("agents", []):
    agent["workspace_root"] = os.path.join(workspace_dir, agent["agent_id"])
with open(path, "w") as f:
    yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
PY
fi
python3 - "$WT_CFG" "$WORKSPACE_DIR" <<'PY'
import os, sys, yaml
cfg_path, wsd = sys.argv[1], sys.argv[2]
with open(cfg_path) as f: cfg = yaml.safe_load(f)
os.makedirs(wsd, exist_ok=True)
for agent in cfg.get("agents", []):
    os.makedirs(agent["workspace_root"], exist_ok=True)
PY

echo "  IM_PORT=$IM_PORT  NODE_ID=$NODE_ID"
if [[ "$PREPARE_ONLY" == "1" ]]; then
  echo "PREPARE_ONLY PASS"
  exit 0
fi

# ─── Scenario A: IM restart → node auto-recovers ─────────────────────────────

echo "Scenario A: IM restart"
reset_im_state
start_im
register_nano
start_gateway
poll_node_online 45 "A1 initial node online"
echo "  killing IM ..."
stop_pidfile "$WT_ROOT/.im.pid"
sleep 4
gateway_alive || { echo "  ✗ A: gateway died while IM was down" >&2; exit 1; }
echo "  restarting IM (same DB) ..."
start_im
register_nano
poll_node_online 75 "A2 node auto back online after IM restart (no gateway restart)"
stop_pidfile "$WT_ROOT/.gateway.pid"
stop_pidfile "$WT_ROOT/.im.pid"

# ─── Scenario B: Gateway starts before IM ────────────────────────────────────

echo "Scenario B: Gateway before IM"
reset_im_state
start_gateway
sleep 6
gateway_alive || { echo "  ✗ B: gateway crashed when started before IM" >&2; tail -20 "$WT_ROOT/.gateway.log" >&2; exit 1; }
echo "  ✓ B1 gateway survived startup with IM down"
echo "  starting IM ..."
start_im
register_nano
poll_node_online 75 "B2 node online after IM comes up"
stop_pidfile "$WT_ROOT/.gateway.pid"
stop_pidfile "$WT_ROOT/.im.pid"

echo "RESILIENCE E2E PASS"
