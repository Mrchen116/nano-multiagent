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

for pidfile in "$WT_ROOT/.im.pid" "$WT_ROOT/.api.pid" "$WT_ROOT/.gateway.pid"; do
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "service still running: $pidfile (pid=$(cat "$pidfile"))" >&2
    echo "run ./scripts/e2e-down.sh first" >&2
    exit 1
  fi
done

# ─── port allocation ─────────────────────────────────────────────────────────

REPO_ROOT="$(git -C "$WT_ROOT" rev-parse --show-toplevel 2>/dev/null || dirname "$WT_ROOT")"
FREE_PORTS_SH="$REPO_ROOT/scripts/free-ports.sh"
[[ -x "$FREE_PORTS_SH" ]] || FREE_PORTS_SH="$(dirname "$0")/free-ports.sh"
read -r IM_PORT API_PORT < <("$FREE_PORTS_SH" 2)

JWT_SECRET="$(LC_ALL=C tr -dc 'a-zA-Z0-9' < /dev/urandom 2>/dev/null | head -c 32 || echo "e2e-$$-$(date +%s)")"
echo "$JWT_SECRET" > "$WT_ROOT/.e2e-jwt-secret"

# ─── derive Gateway config (worktree-local copy) ─────────────────────────────

WT_CFG="$WT_ROOT/.gateway-config.yaml"
cp "$MAIN_CFG" "$WT_CFG"

WT_NAME="$(basename "$WT_ROOT")"
NODE_ID="wt-${WT_NAME}-$$"
WORKSPACE_DIR="$WT_ROOT/.gateway-workspace"

if command -v yq >/dev/null 2>&1; then
  yq -i "
    .node.node_id = \"$NODE_ID\" |
    .im_service.url = \"http://127.0.0.1:$IM_PORT\" |
    .agents[].workspace_root = \"$WORKSPACE_DIR/\" + .agents[].agent_id
  " "$WT_CFG"
else
  # Fallback when yq is absent: use python.
  WT_CFG_PY="$WT_CFG" NODE_ID="$NODE_ID" IM_PORT="$IM_PORT" WORKSPACE_DIR="$WORKSPACE_DIR" \
    python3 - <<'PY'
import os, sys, yaml
path = os.environ["WT_CFG_PY"]
with open(path) as f: cfg = yaml.safe_load(f)
cfg.setdefault("node", {})["node_id"] = os.environ["NODE_ID"]
cfg.setdefault("im_service", {})["url"] = f"http://127.0.0.1:{os.environ['IM_PORT']}"
wsd = os.environ["WORKSPACE_DIR"]
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

cd "$WT_ROOT"
IM_JWT_SECRET="$JWT_SECRET" PYTHONPATH=src \
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

# ─── start Kernel API (bare uvicorn) ─────────────────────────────────────────
# Use personal_assistant.kernel_app which reads NANO_MULTIAGENT_LLM_CONFIG_JSON
# and calls init_model_registry() before create_app().

if ! python3 -c "import yaml; cfg=yaml.safe_load(open('$WT_CFG')); exit(0 if 'llm' in cfg else 1)" 2>/dev/null; then
  echo "ERROR: '$WT_CFG' is missing the 'llm:' section." >&2
  echo "Add the llm: block to ~/.nano-assistant/config.yaml first (see AGENTS.md 'minimum config example')." >&2
  exit 1
fi

LLM_CONFIG_JSON=$(PYTHONPATH=src python3 -c "
import sys, yaml
sys.path.insert(0, 'src')
from personal_assistant.config.local_store import load_local_config
cfg = load_local_config('$WT_CFG')
print(cfg.llm.to_json())
")

NANO_MULTIAGENT_LLM_CONFIG_JSON="$LLM_CONFIG_JSON" \
PYTHONPATH=src python -m uvicorn personal_assistant.kernel_app:app \
  --host 127.0.0.1 --port "$API_PORT" \
  > "$WT_ROOT/.api.log" 2>&1 &
echo $! > "$WT_ROOT/.api.pid"

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$API_PORT/v1/health" >/dev/null 2>&1; then break; fi
  sleep 0.2
done
if ! curl -sf "http://127.0.0.1:$API_PORT/v1/health" >/dev/null 2>&1; then
  echo "Kernel API failed to start; see $WT_ROOT/.api.log" >&2
  exit 1
fi

# ─── start Gateway (wrapper, --foreground + --auto-bind) ─────────────────────
#
# Gateway is NOT a bare ASGI app — it's a supervisor process. In foreground mode
# it logs to the controlling stdio (we redirect to .gateway.log) and lives under
# the shell job, so the `$!` PID is the actual process to kill. --auto-bind
# replaces the interactive "click this URL" step that breaks worktree e2e.
# refactor-381.

PYTHONPATH=src python -m personal_assistant.main \
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
# source this file in your shell, then curl with \$IM_URL / \$API_URL.
export IM_PORT=$IM_PORT
export API_PORT=$API_PORT
export IM_URL=http://127.0.0.1:$IM_PORT
export API_URL=http://127.0.0.1:$API_PORT
export IM_JWT_SECRET=$JWT_SECRET
export NODE_ID=$NODE_ID
EOF

echo "e2e stack ready in $WT_ROOT"
echo "  IM   $IM_PORT  ($WT_ROOT/.im.log)"
echo "  API  $API_PORT  ($WT_ROOT/.api.log)"
echo "  GW   pid=$(cat "$WT_ROOT/.gateway.pid")  ($WT_ROOT/.gateway.log)"
echo "source $WT_ROOT/.e2e-ports.env to expose ports"
