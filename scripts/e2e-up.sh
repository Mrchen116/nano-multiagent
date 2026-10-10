#!/usr/bin/env bash
# scripts/e2e-up.sh — start the full IM + Gateway stack inside the
# current worktree, with ephemeral ports and an isolated Gateway config.
#
# Idempotent within one worktree: if any .pid file is live, refuses to start to
# avoid clobbering. Run scripts/e2e-down.sh first if you want a clean restart.
#
# refactor-381: replaces the ~12-step manual setup ritual that worker /
# reviewer / contributor each had to re-invent (see
# docs/changes/archive/bugfix-380-llm-upstream-error-visible/retro.md §2).
#
# Usage:
#   ./scripts/e2e-up.sh                                  # repository default profile
#   ./scripts/e2e-up.sh --feishu                         # dedicated test Bot profile
#   ./scripts/e2e-up.sh --main-config /path/to/cfg.yaml  # alt source config
#   ./scripts/e2e-up.sh --wt /custom/worktree/path       # alt target worktree
#
# Side effects in $WT_ROOT (default = $PWD):
#   .e2e-ports.env            (source this in your shell to expose ports)
#   .e2e-jwt-secret           (random IM JWT secret for this run)
#   .gateway-config.yaml      (isolated copy of main config)
#   .gateway-workspace/       (per-agent workspaces isolated from the user home)
#   .im.pid / .gateway.pid
#   .im.log / .api.log / .gateway.log

set -euo pipefail

# Resolve the repository from this script, not the caller's worktree: pytest can
# pass an arbitrary temporary directory as --wt.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd 2>/dev/null)"
DEFAULT_E2E_CONFIG="$REPO_ROOT/config/e2e/gateway.yaml"
DEFAULT_FEISHU_ENV="${XDG_CONFIG_HOME:-$HOME/.config}/nano-multiagent/feishu-e2e.env"
DEFAULT_FEISHU_LOCK_ROOT="${XDG_RUNTIME_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/nano-multiagent}"

# ─── arg parsing ─────────────────────────────────────────────────────────────

WT_ROOT="${PWD}"
MAIN_CFG="$DEFAULT_E2E_CONFIG"
E2E_PROFILE="default"
FEISHU_ENV="$DEFAULT_FEISHU_ENV"
MAIN_CONFIG_EXPLICIT=0
FEISHU_LOCK_DIR=""
FEISHU_LOCK_HELD=0
# One script-owned, condition-polled cold-start budget. Tests may lower it to
# exercise the deadline without changing production-facing Gateway timeouts.
IM_READINESS_TIMEOUT_SECONDS="${NANO_MULTIAGENT_E2E_IM_READINESS_TIMEOUT_SECONDS:-30}"
IM_READINESS_POLL_SECONDS=0.2

if ! [[ "$IM_READINESS_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "NANO_MULTIAGENT_E2E_IM_READINESS_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi

release_feishu_listener_lock() {
  [[ $FEISHU_LOCK_HELD -eq 1 ]] || return 0
  local owner_file="$FEISHU_LOCK_DIR/owner"
  if [[ -f "$owner_file" ]] && grep -Fqx "worktree=$WT_ROOT" "$owner_file"; then
    rm -f "$owner_file"
    rmdir "$FEISHU_LOCK_DIR" 2>/dev/null || true
  fi
  FEISHU_LOCK_HELD=0
}

claim_feishu_listener_lock() {
  FEISHU_LOCK_DIR="$(
    WT_CFG_PY="$WT_CFG" FEISHU_LOCK_ROOT="$DEFAULT_FEISHU_LOCK_ROOT" python3 - <<'PY'
import hashlib
import os
from pathlib import Path

import yaml

with open(os.environ["WT_CFG_PY"], encoding="utf-8") as stream:
    config = yaml.safe_load(stream)
for channel in config.get("channels", []):
    if channel.get("name") == "feishu:e2e":
        bot_open_id = channel["settings"]["botOpenId"]
        digest = hashlib.sha256(bot_open_id.encode("utf-8")).hexdigest()[:16]
        print(Path(os.environ["FEISHU_LOCK_ROOT"]) / f"feishu-e2e-{digest}.lock")
        break
else:
    raise RuntimeError("Feishu E2E channel was not rendered")
PY
  )"
  mkdir -p "$(dirname "$FEISHU_LOCK_DIR")"
  if ! mkdir "$FEISHU_LOCK_DIR" 2>/dev/null; then
    local owner_file="$FEISHU_LOCK_DIR/owner"
    local owner_pid=""
    local owner_worktree=""
    if [[ -f "$owner_file" ]]; then
      owner_pid="$(sed -n 's/^pid=//p' "$owner_file" | head -1)"
      owner_worktree="$(sed -n 's/^worktree=//p' "$owner_file" | head -1)"
    fi
    if [[ "$owner_pid" =~ ^[0-9]+$ ]] && kill -0 "$owner_pid" 2>/dev/null; then
      echo "dedicated Feishu E2E listener is already owned by ${owner_worktree:-another worktree}" >&2
      echo "stop that stack with scripts/e2e-down.sh before starting another --feishu stack" >&2
      return 1
    fi
    rm -f "$owner_file"
    if ! rmdir "$FEISHU_LOCK_DIR" 2>/dev/null || ! mkdir "$FEISHU_LOCK_DIR"; then
      echo "could not clear stale Feishu E2E listener lock: $FEISHU_LOCK_DIR" >&2
      return 1
    fi
  fi
  printf 'worktree=%s\npid=%s\n' "$WT_ROOT" "$$" > "$FEISHU_LOCK_DIR/owner"
  FEISHU_LOCK_HELD=1
  trap release_feishu_listener_lock EXIT
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) WT_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    --main-config) MAIN_CFG="$2"; MAIN_CONFIG_EXPLICIT=1; shift 2 ;;
    --profile) E2E_PROFILE="$2"; shift 2 ;;
    --feishu) E2E_PROFILE="feishu"; shift ;;
    --feishu-env) FEISHU_ENV="$2"; shift 2 ;;
    -h|--help) sed -n '1,/^set -e/p' "$0" | sed -n '2,/^$/p'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$E2E_PROFILE" in
  default)
    ;;
  feishu)
    if [[ $MAIN_CONFIG_EXPLICIT -eq 1 ]]; then
      echo "--feishu cannot be combined with --main-config" >&2
      exit 2
    fi
    ;;
  *)
    echo "unknown E2E profile: $E2E_PROFILE (expected default or feishu)" >&2
    exit 2
    ;;
esac

if [[ ! -f "$MAIN_CFG" ]]; then
  echo "E2E config not found: $MAIN_CFG" >&2
  echo "restore the repository E2E config or pass --main-config" >&2
  exit 1
fi

# ─── liveness check (refuse to clobber) ──────────────────────────────────────

for pidfile in "$WT_ROOT/.im.pid" "$WT_ROOT/.gateway.pid"; do
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "service still running: $pidfile (pid=$(cat "$pidfile"))" >&2
    echo "run ./scripts/e2e-down.sh first" >&2
    exit 1
  fi
done

# ─── port allocation ─────────────────────────────────────────────────────────

# REPO_ROOT was resolved from this script before arguments were parsed. It must
# not follow $WT_ROOT because test fixtures commonly use a non-git temp path.
FREE_PORTS_SH="$REPO_ROOT/scripts/free-ports.sh"
[[ -x "$FREE_PORTS_SH" ]] || FREE_PORTS_SH="$SCRIPT_DIR/free-ports.sh"
# Only the IM center listens on a port; DSH is a managed stdio child.
read -r IM_PORT < <("$FREE_PORTS_SH" 1)

JWT_SECRET="$(LC_ALL=C tr -dc 'a-zA-Z0-9' < /dev/urandom 2>/dev/null | head -c 32 || echo "e2e-$$-$(date +%s)")"
echo "$JWT_SECRET" > "$WT_ROOT/.e2e-jwt-secret"

# ─── derive Gateway config (worktree-local copy) ─────────────────────────────

WT_CFG="$WT_ROOT/.gateway-config.yaml"
cp "$MAIN_CFG" "$WT_CFG"
if [[ "$E2E_PROFILE" == "feishu" ]]; then
  python3 "$SCRIPT_DIR/e2e_feishu_config.py" \
    --config "$WT_CFG" \
    --env "$FEISHU_ENV"
  claim_feishu_listener_lock
fi
chmod 600 "$WT_CFG"

WT_NAME="$(basename "$WT_ROOT")"
NODE_ID="wt-${WT_NAME}-$$"
WORKSPACE_DIR="$WT_ROOT/.gateway-workspace"

WT_CFG_PY="$WT_CFG" NODE_ID="$NODE_ID" IM_PORT="$IM_PORT" WORKSPACE_DIR="$WORKSPACE_DIR" WT_ROOT_PY="$WT_ROOT" \
  python3 - <<'PYCFG'
import os, yaml
path = os.environ["WT_CFG_PY"]
with open(path) as f: cfg = yaml.safe_load(f)
cfg.setdefault("node", {})["node_id"] = os.environ["NODE_ID"]
cfg["node"]["user_id"] = ""
cfg.setdefault("im_service", {}).update(url=f"http://127.0.0.1:{os.environ['IM_PORT']}", token="", username="nano", password="nano1234")
cfg["im_service"].pop("refresh_token", None)
wsd = os.environ["WORKSPACE_DIR"]
cfg["node"]["workspace_base"] = wsd
cfg.setdefault("gateway", {})["autostart"] = False
cfg["gateway"].setdefault("environment", {})["NANO_OWNER_CONFIG_ROOT"] = os.path.join(os.environ["WT_ROOT_PY"], ".gateway-owner")
for agent in cfg.get("agents", []):
    agent["workspace_root"] = os.path.join(wsd, agent["agent_id"])
with open(path, "w") as f: yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
PYCFG

# An explicit critical-path model override must be registered in the copied config.
# The selector changes only the worktree-local default, so preset and dynamically
# created agents use the same route.
if [[ -n "${NANO_MULTIAGENT_E2E_MODEL:-}" ]]; then
  python3 "$SCRIPT_DIR/e2e_catalog.py" "$WT_CFG"
fi

# Pre-create each agent's workspace dir; Gateway refuses to start otherwise.
python3 - "$WT_CFG" "$WORKSPACE_DIR" <<'PY'
import os, sys, yaml
cfg_path, wsd = sys.argv[1], sys.argv[2]
with open(cfg_path) as f: cfg = yaml.safe_load(f)
os.makedirs(wsd, exist_ok=True)
for agent in cfg.get("agents", []):
    os.makedirs(agent["workspace_root"], exist_ok=True)
PY

# ─── start TypeScript IM ─────────────────────────────────────────────────
#
# feat-393 fix-r1: remove stale IM DB before each e2e run so heartbeat conversations
# created by a previous run (with different owner_id) do not pollute the new instance.
# The DB path is cwd-relative (data/im_service.sqlite3) so we remove it from $WT_ROOT.
rm -f "$WT_ROOT/data/im_service.sqlite3" "$WT_ROOT/data/im_service.sqlite3-wal" "$WT_ROOT/data/im_service.sqlite3-shm"
# Each run gets a fresh node identity; preserve prior per-node DSH evidence.
rm -f "$WT_ROOT/channel-credentials-v1.pem" "$WT_ROOT/device-binding-operation.json"
if [[ ! -f "$REPO_ROOT/apps/im-server/lib/main.js" || ! -f "$REPO_ROOT/apps/node/lib/cli.js" ]]; then
  echo "Build first: pnpm install --frozen-lockfile && pnpm build" >&2
  exit 1
fi

cd "$WT_ROOT"
IM_PUBLIC_URL="http://127.0.0.1:$IM_PORT" IM_JWT_SECRET="$JWT_SECRET" IM_DB_PATH="$WT_ROOT/data/im_service.sqlite3" IM_UPLOAD_DIR="$WT_ROOT/data/uploads" IM_PUBLIC_MODE=0 \
  node --input-type=module - "$REPO_ROOT/apps/im-server/lib/main.js" "$IM_PORT" "$WT_ROOT" <<'JS'
import {spawn,execFileSync} from 'node:child_process';
import {openSync,closeSync,writeFileSync} from 'node:fs';
const root=process.argv[4],log=openSync(root+'/.im.log','a');
const child=spawn(process.execPath,[process.argv[2],'serve','--host','127.0.0.1','--port',process.argv[3]],{cwd:root,env:process.env,detached:true,stdio:['ignore',log,log]});
writeFileSync(root+'/.im.pid',String(child.pid));
writeFileSync(root+'/.im.process-start',execFileSync('ps',['-p',String(child.pid),'-o','lstart=']));
closeSync(log);child.unref();
JS

# Readiness means the real TypeScript center has completed startup.
IM_READINESS_STARTED_SECONDS=$SECONDS
while true; do
  if curl -sf "http://127.0.0.1:$IM_PORT/health" >/dev/null 2>&1; then
    break
  fi
  IM_PID="$(cat "$WT_ROOT/.im.pid")"
  if ! kill -0 "$IM_PID" 2>/dev/null; then
    echo "IM process exited during startup; see $WT_ROOT/.im.log" >&2
    tail -30 "$WT_ROOT/.im.log" >&2 || true
    exit 1
  fi
  if (( SECONDS - IM_READINESS_STARTED_SECONDS >= IM_READINESS_TIMEOUT_SECONDS )); then
    echo "IM readiness timed out after ${IM_READINESS_TIMEOUT_SECONDS}s; see $WT_ROOT/.im.log" >&2
    tail -30 "$WT_ROOT/.im.log" >&2 || true
    exit 1
  fi
  sleep "$IM_READINESS_POLL_SECONDS"
done

# Explicit local admission; public registration intentionally stays pending.
IM_JWT_SECRET="$JWT_SECRET" node "$REPO_ROOT/apps/im-server/lib/main.js" init_admin \
  --username nano --password nano1234 --display-name "Test User" \
  --db-path "$WT_ROOT/data/im_service.sqlite3"

# The native CLI completes device proof and persists its runtime credential.
node "$REPO_ROOT/apps/node/lib/cli.js" bind --config "$WT_CFG" --auto-bind
node "$REPO_ROOT/apps/node/lib/cli.js" start --config "$WT_CFG"
node --input-type=module - "$WT_ROOT/.gateway-state.json" "$WT_ROOT/.gateway.pid" <<'JS'
import {readFileSync,writeFileSync} from 'node:fs';
writeFileSync(process.argv[3],String(JSON.parse(readFileSync(process.argv[2],'utf8')).pid));
JS

# Readiness requires the expected node to be online under the admitted owner.
# A successful proof alone is insufficient: registration and config sync follow it.
IM_E2E_URL="http://127.0.0.1:$IM_PORT" E2E_NODE_ID="$NODE_ID" E2E_GATEWAY_PID="$(cat "$WT_ROOT/.gateway.pid")" python - <<'PYREADY'
import os, time, httpx
with httpx.Client(base_url=os.environ["IM_E2E_URL"], trust_env=False) as client:
    login = client.post("/im/v1/auth/login", json={"username": "nano", "password": "nano1234"})
    login.raise_for_status()
    pair = login.json()
    client.headers["Authorization"] = "Bearer " + pair["access_token"]
    for _ in range(60):
        os.kill(int(os.environ["E2E_GATEWAY_PID"]), 0)
        response = client.get("/im/v1/nodes")
        response.raise_for_status()
        if any(node["node_id"] == os.environ["E2E_NODE_ID"] and node["owner_id"] == pair["user"]["owner_id"] and node["status"] == "online" for node in response.json()):
            break
        time.sleep(0.5)
    else:
        raise SystemExit("Gateway did not register online within 30s; inspect .gateway.log")
PYREADY

if [[ $FEISHU_LOCK_HELD -eq 1 ]]; then
  printf 'worktree=%s\npid=%s\n' "$WT_ROOT" "$(cat "$WT_ROOT/.gateway.pid")" > "$FEISHU_LOCK_DIR/owner"
  FEISHU_LOCK_HELD=0
  trap - EXIT
fi

# ─── persist port map for follow-up curl / tests ─────────────────────────────

FEISHU_LOCK_ENV_LINE=""
if [[ "$E2E_PROFILE" == "feishu" ]]; then
  FEISHU_LOCK_ENV_LINE="export E2E_FEISHU_LISTENER_LOCK=$FEISHU_LOCK_DIR"
fi
cat > "$WT_ROOT/.e2e-ports.env" <<EOF
# Generated by scripts/e2e-up.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# DSH uses a private stdio link; no runtime HTTP port.
# source this file in your shell, then curl with \$IM_URL.
export IM_PORT=$IM_PORT
export IM_URL=http://127.0.0.1:$IM_PORT
export IM_JWT_SECRET=$JWT_SECRET
export NODE_ID=$NODE_ID
export VITE_IM_PROXY_TARGET=http://127.0.0.1:$IM_PORT
export E2E_PROFILE=$E2E_PROFILE
$FEISHU_LOCK_ENV_LINE
EOF

echo "e2e stack ready in $WT_ROOT"
echo "  IM   $IM_PORT  ($WT_ROOT/.im.log)"
echo "  GW   pid=$(cat "$WT_ROOT/.gateway.pid")  ($WT_ROOT/gateway.log)"
echo "  profile $E2E_PROFILE"
echo "source $WT_ROOT/.e2e-ports.env to expose ports"
echo "hint: the default profile uses config/e2e/gateway.yaml, never ~/.nanoassistant"
echo "      Feishu requires --feishu and the private profile documented in worktree-runtime.md"
