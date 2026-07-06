#!/usr/bin/env bash
# scripts/e2e-up.sh — start the full IM + Kernel API + Gateway stack inside the
# current worktree, with ephemeral ports and an isolated Gateway config.
#
# Idempotent within one worktree: if any .pid file is live, refuses to start to
# avoid clobbering. Run scripts/e2e-down.sh first if you want a clean restart.
#
# refactor-381: replaces the ~12-step manual setup ritual that worker /
# reviewer / contributor each had to re-invent (see
# docs/changes/bugfix-380-llm-upstream-error-visible/retro.md §2).
#
# Usage:
#   ./scripts/e2e-up.sh                                  # use defaults
#   ./scripts/e2e-up.sh --main-config /path/to/cfg.yaml  # alt source config
#   ./scripts/e2e-up.sh --wt /custom/worktree/path       # alt target worktree
#
# Side effects in $WT_ROOT (default = $PWD):
#   .e2e-ports.env            (source this in your shell to expose ports)
#   .e2e-jwt-secret           (random IM JWT secret for this run)
#   .gateway-config.yaml      (isolated copy of main config)
#   .gateway-workspace/       (per-agent workspaces, replacing ~/nano-assistant/workspace)
#   .im.pid / .api.pid / .gateway.pid
#   .im.log / .api.log / .gateway.log

set -euo pipefail

# ─── arg parsing ─────────────────────────────────────────────────────────────

WT_ROOT="${PWD}"
MAIN_CFG="${HOME}/.nano-assistant/config.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) WT_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    --main-config) MAIN_CFG="$2"; shift 2 ;;
    -h|--help) sed -n '1,/^set -e/p' "$0" | sed -n '2,/^$/p'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -f "$MAIN_CFG" ]]; then
  echo "main config not found: $MAIN_CFG" >&2
  echo "create ~/.nano-assistant/config.yaml first (see AGENTS.md) or pass --main-config" >&2
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

# REPO_ROOT must resolve to the checkout that holds src/ and scripts/, NOT to
# $WT_ROOT — feat-421 runs the stack with --wt pointing at a pytest tmp dir that
# is not a git checkout and has no src/. Derive it from this script's own path
# ($0 lives in <repo>/scripts/) so PYTHONPATH and free-ports.sh resolve no matter
# where $WT_ROOT points. Falls back to git/dirname only if $0 derivation fails.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd 2>/dev/null)"
REPO_ROOT="${REPO_ROOT:-$(git -C "$WT_ROOT" rev-parse --show-toplevel 2>/dev/null || dirname "$WT_ROOT")}"
SRC_DIR="$REPO_ROOT/src"
FREE_PORTS_SH="$REPO_ROOT/scripts/free-ports.sh"
[[ -x "$FREE_PORTS_SH" ]] || FREE_PORTS_SH="$SCRIPT_DIR/free-ports.sh"
# refactor-387 M3: kernel runs in-process; only 1 port needed (IM).
read -r IM_PORT < <("$FREE_PORTS_SH" 1)

JWT_SECRET="$(LC_ALL=C tr -dc 'a-zA-Z0-9' < /dev/urandom 2>/dev/null | head -c 32 || echo "e2e-$$-$(date +%s)")"
echo "$JWT_SECRET" > "$WT_ROOT/.e2e-jwt-secret"

# ─── derive Gateway config (worktree-local copy) ─────────────────────────────

WT_CFG="$WT_ROOT/.gateway-config.yaml"
cp "$MAIN_CFG" "$WT_CFG"

WT_NAME="$(basename "$WT_ROOT")"
NODE_ID="wt-${WT_NAME}-$$"
WORKSPACE_DIR="$WT_ROOT/.gateway-workspace"

if command -v yq >/dev/null 2>&1; then
  # bugfix-424 (#127): node.workspace_base isolates *dynamically* created agents
  # (built via IM agent.create) under the worktree, same as preset agents below.
  yq -i "
    .node.node_id = \"$NODE_ID\" |
    .node.workspace_base = \"$WORKSPACE_DIR\" |
    .im_service.url = \"http://127.0.0.1:$IM_PORT\" |
    .agents |= map(.workspace_root = \"$WORKSPACE_DIR/\" + .agent_id)
  " "$WT_CFG"
else
  # Fallback when yq is absent: use python.
  # refactor-387 M3: kernel.base_url no longer needed (kernel runs in-process).
  WT_CFG_PY="$WT_CFG" NODE_ID="$NODE_ID" IM_PORT="$IM_PORT" WORKSPACE_DIR="$WORKSPACE_DIR" \
    python3 - <<'PY'
import os, sys, yaml
path = os.environ["WT_CFG_PY"]
with open(path) as f: cfg = yaml.safe_load(f)
cfg.setdefault("node", {})["node_id"] = os.environ["NODE_ID"]
cfg.setdefault("im_service", {})["url"] = f"http://127.0.0.1:{os.environ['IM_PORT']}"
wsd = os.environ["WORKSPACE_DIR"]
# bugfix-424 (#127): isolate dynamically-created agents under the worktree too.
cfg["node"]["workspace_base"] = wsd
for agent in cfg.get("agents", []):
    agent["workspace_root"] = os.path.join(wsd, agent["agent_id"])
with open(path, "w") as f: yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
PY
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

# ─── start IM (bare uvicorn) ─────────────────────────────────────────────────
#
# feat-393 fix-r1: remove stale IM DB before each e2e run so heartbeat conversations
# created by a previous run (with different owner_id) do not pollute the new instance.
# The DB path is cwd-relative (data/im_service.sqlite3) so we remove it from $WT_ROOT.
rm -f "$WT_ROOT/data/im_service.sqlite3"
# feat-393 fix-r2: remove stale heartbeat-state.json so a previous run's last_due_at
# does not trigger catch-up backlog on restart (that was the root cause of the 4x burst).
rm -f "$WT_ROOT/heartbeat-state.json"
# e2e-up.sh starts a fresh IM DB every run; Gateway's local state must be fresh too.
# Otherwise old external chat bindings and buffered group context can route a new
# validation run through stale kernel sessions from a previous e2e attempt.
rm -f "$WT_ROOT/session_bindings.sqlite3"
rm -f "$WT_ROOT/group_context_buffer.sqlite3"
rm -f "$WT_ROOT/relay_dedup.sqlite3"

cd "$WT_ROOT"
IM_JWT_SECRET="$JWT_SECRET" PYTHONPATH="$SRC_DIR" \
  python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" \
  > "$WT_ROOT/.im.log" 2>&1 &
echo $! > "$WT_ROOT/.im.pid"

# Wait for IM ready. IM has no dedicated /health endpoint, so we probe
# /openapi.json — present on every FastAPI app once startup completes.
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$IM_PORT/openapi.json" >/dev/null 2>&1; then break; fi
  sleep 0.2
done
if ! curl -sf "http://127.0.0.1:$IM_PORT/openapi.json" >/dev/null 2>&1; then
  echo "IM failed to start; see $WT_ROOT/.im.log" >&2
  exit 1
fi

# Register nano user in the ephemeral IM (fresh DB, no users yet).
curl -sf -X POST "http://127.0.0.1:$IM_PORT/im/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"nano","password":"nano1234","display_name":"Test User"}' \
  >/dev/null 2>&1 || true  # ignore if already registered

# Resolve the nano user's real id in this ephemeral IM and patch config.node.user_id.
# feat-393 fix-r1: the main config carries a stale user_id from a prior persistent IM
# instance; the ephemeral IM is a fresh DB so that id does not exist (→ 404), causing
# heartbeat to pass a nonexistent to_user_id and never deliver messages to the owner.
# We login to obtain the authenticated profile which includes the real id, then update
# the worktree config copy so Gateway uses the correct owner for heartbeat delivery.
NANO_USER_ID="$(
  curl -sf -X POST "http://127.0.0.1:$IM_PORT/im/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"nano","password":"nano1234"}' 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('user',{}).get('id') or d.get('id',''))" 2>/dev/null
)" || true
if [[ -n "$NANO_USER_ID" ]]; then
  if command -v yq >/dev/null 2>&1; then
    yq -i ".node.user_id = \"$NANO_USER_ID\"" "$WT_CFG"
  else
    NANO_USER_ID="$NANO_USER_ID" WT_CFG_PY="$WT_CFG" python3 - <<'PY'
import os, yaml
path = os.environ["WT_CFG_PY"]
with open(path) as f: cfg = yaml.safe_load(f)
cfg.setdefault("node", {})["user_id"] = os.environ["NANO_USER_ID"]
with open(path, "w") as f: yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
PY
  fi
  echo "e2e config: node.user_id synced to ephemeral IM user $NANO_USER_ID"
else
  echo "WARNING: could not resolve nano user id from ephemeral IM; heartbeat delivery may fail" >&2
fi

# ─── validate llm config before starting Gateway ─────────────────────────────
# refactor-387 M3: kernel runs in-process inside Gateway; no separate Kernel API.

if ! python3 -c "import yaml; cfg=yaml.safe_load(open('$WT_CFG')); exit(0 if 'llm' in cfg else 1)" 2>/dev/null; then
  echo "ERROR: '$WT_CFG' is missing the 'llm:' section." >&2
  echo "Add the llm: block to ~/.nano-assistant/config.yaml first (see AGENTS.md 'minimum config example')." >&2
  exit 1
fi

# ─── start Gateway (wrapper, --foreground + --auto-bind) ─────────────────────
#
# Gateway is NOT a bare ASGI app — it's a supervisor process. In foreground mode
# it logs to the controlling stdio (we redirect to .gateway.log) and lives under
# the shell job, so the `$!` PID is the actual process to kill. --auto-bind
# replaces the interactive "click this URL" step that breaks worktree e2e.
# refactor-381.

PYTHONPATH="$SRC_DIR" python -m personal_assistant.main \
  --config "$WT_CFG" \
  --im-service-url "http://127.0.0.1:$IM_PORT" \
  --foreground \
  --auto-bind \
  > "$WT_ROOT/.gateway.log" 2>&1 &
echo $! > "$WT_ROOT/.gateway.pid"

# Wait for Gateway readiness. Probe the internal health port written into the
# log; absent a health line within 20s, abort.
GW_READY=0
for _ in $(seq 1 60); do
  if grep -q "INFO node .* auto-bound to IM\|Gateway started\|node_id=\|INFO im_connection" "$WT_ROOT/.gateway.log" 2>/dev/null; then
    GW_READY=1; break
  fi
  if ! kill -0 "$(cat "$WT_ROOT/.gateway.pid")" 2>/dev/null; then
    echo "Gateway process died during startup; see $WT_ROOT/.gateway.log" >&2
    tail -30 "$WT_ROOT/.gateway.log" >&2 || true
    exit 1
  fi
  sleep 0.5
done
if [[ $GW_READY -eq 0 ]]; then
  echo "Gateway did not signal readiness within 30s; see $WT_ROOT/.gateway.log" >&2
  tail -30 "$WT_ROOT/.gateway.log" >&2 || true
  exit 1
fi

# ─── persist port map for follow-up curl / tests ─────────────────────────────

cat > "$WT_ROOT/.e2e-ports.env" <<EOF
# Generated by scripts/e2e-up.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# refactor-387 M3: kernel is in-process; no API_PORT needed.
# source this file in your shell, then curl with \$IM_URL.
export IM_PORT=$IM_PORT
export IM_URL=http://127.0.0.1:$IM_PORT
export IM_JWT_SECRET=$JWT_SECRET
export NODE_ID=$NODE_ID
export VITE_IM_PROXY_TARGET=http://127.0.0.1:$IM_PORT
EOF

echo "e2e stack ready in $WT_ROOT"
echo "  IM   $IM_PORT  ($WT_ROOT/.im.log)"
echo "  GW   pid=$(cat "$WT_ROOT/.gateway.pid")  ($WT_ROOT/.gateway.log)"
echo "source $WT_ROOT/.e2e-ports.env to expose ports"
