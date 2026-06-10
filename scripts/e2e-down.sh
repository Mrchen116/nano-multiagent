#!/usr/bin/env bash
# scripts/e2e-down.sh — stop everything scripts/e2e-up.sh started.
#
# Pairs with e2e-up.sh. Safe to run repeatedly. Cleans pid files, ports env,
# JWT secret, gateway log/config copies. Does NOT remove .gateway-workspace/
# (agent data may still be useful for inspection after a run).
#
# Shutdown order (Decision 7 / bugfix-402-M3):
#   1. SIGTERM Gateway — waits up to GATEWAY_GRACE_SECONDS for clean exit
#   2. Force-kill Gateway on timeout
#   3. Stop IM (Gateway must be gone first so in-flight runs can settle)
#
# Usage:
#   ./scripts/e2e-down.sh
#   ./scripts/e2e-down.sh --wt /custom/worktree/path

set -euo pipefail

WT_ROOT="${PWD}"
GATEWAY_GRACE_SECONDS=5
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) WT_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    -h|--help) sed -n '1,/^set -e/p' "$0" | sed -n '2,/^$/p'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Step 1: Signal Gateway and wait for graceful exit before touching IM.
# Gateway's shutdown drains in-flight runs before closing IM transport;
# sending SIGTERM to both at once would close IM before runs settle.
gateway_pid_file="$WT_ROOT/.gateway.pid"
if [[ -f "$gateway_pid_file" ]]; then
  gw_pid=$(cat "$gateway_pid_file")
  if kill -0 "$gw_pid" 2>/dev/null; then
    kill "$gw_pid" 2>/dev/null || true
    # Wait for graceful exit, then force-kill on timeout.
    elapsed=0
    while kill -0 "$gw_pid" 2>/dev/null; do
      if [[ $elapsed -ge $GATEWAY_GRACE_SECONDS ]]; then
        echo "gateway pid=$gw_pid did not exit within ${GATEWAY_GRACE_SECONDS}s — force-killing" >&2
        kill -9 "$gw_pid" 2>/dev/null || true
        break
      fi
      sleep 0.2
      elapsed=$(( elapsed + 1 ))
    done
  fi
  rm -f "$gateway_pid_file"
fi

# Step 2: Now that Gateway is gone, stop IM and Kernel API.
stopped_pids=()
for pidfile in "$WT_ROOT/.api.pid" "$WT_ROOT/.im.pid"; do
  if [[ -f "$pidfile" ]]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      stopped_pids+=("$pid")
    fi
    rm -f "$pidfile"
  fi
done

# Give remaining services a moment, then force-kill stragglers.
if [[ ${#stopped_pids[@]} -gt 0 ]]; then
  sleep 0.5
  for pid in "${stopped_pids[@]}"; do
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  done
fi

# Remove generated state. .gateway-workspace/ is preserved for post-mortem.
rm -f "$WT_ROOT/.e2e-ports.env"
rm -f "$WT_ROOT/.e2e-jwt-secret"
rm -f "$WT_ROOT/.gateway-config.yaml"

echo "e2e stack stopped (wt=$WT_ROOT)"
