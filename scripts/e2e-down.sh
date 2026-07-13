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

PYTHON_BIN="$(command -v python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "python is required to validate Gateway teardown identity" >&2
  exit 1
fi

gateway_process_status() {
  local pid=$1 process_stat
  process_stat="$(ps -p "$pid" -o stat= 2>/dev/null | tr -d '[:space:]')"
  if [[ -z "$process_stat" || "$process_stat" == Z* ]]; then
    echo exited
  else
    echo alive
  fi
}

validate_gateway_identity() {
  local gw_pid=$1 identity_file internal_pid live_command live_start
  local identity_values identity_pid identity_internal identity_config identity_start
  identity_file="$WT_ROOT/.gateway-identity.json"
  if [[ ! -f "$identity_file" || ! -f "$WT_ROOT/gateway.pid" ]]; then
    return 1
  fi
  identity_values="$($PYTHON_BIN - "$identity_file" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(
    payload.get("pid", ""),
    payload.get("internal_pid", ""),
    payload.get("config_path", ""),
    payload.get("process_start", ""),
    sep="\t",
)
PY
)" || return 1
  IFS=$'\t' read -r identity_pid identity_internal identity_config identity_start <<< "$identity_values"
  internal_pid="$(tr -d '[:space:]' < "$WT_ROOT/gateway.pid")"
  [[ "$identity_pid" == "$gw_pid" ]] || return 1
  [[ "$identity_internal" == "$gw_pid" ]] || return 1
  [[ "$internal_pid" == "$gw_pid" ]] || return 1
  [[ "$identity_config" == "$WT_ROOT/.gateway-config.yaml" ]] || return 1

  live_command="$(ps -p "$gw_pid" -o command= 2>/dev/null)"
  live_start="$(ps -p "$gw_pid" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  "$PYTHON_BIN" - "$live_command" "$identity_config" "$live_start" "$identity_start" <<'PY'
import shlex
import sys

command, expected_config, live_start, expected_start = sys.argv[1:]
try:
    argv = shlex.split(command)
except ValueError:
    raise SystemExit(1)
module_ok = any(
    argv[index : index + 2] == ["-m", "personal_assistant.main"]
    for index in range(max(0, len(argv) - 1))
)
config_indexes = [index for index, value in enumerate(argv) if value == "--config"]
config_ok = (
    len(config_indexes) == 1
    and config_indexes[0] + 1 < len(argv)
    and argv[config_indexes[0] + 1] == expected_config
)
foreground_ok = argv.count("--foreground") == 1
auto_bind_ok = argv.count("--auto-bind") == 1
raise SystemExit(
    0
    if module_ok
    and config_ok
    and foreground_ok
    and auto_bind_ok
    and live_start == expected_start
    else 1
)
PY
}

# Step 1: Signal Gateway and wait for graceful exit before touching IM.
# Gateway's shutdown drains in-flight runs before closing IM transport;
# sending SIGTERM to both at once would close IM before runs settle.
gateway_pid_file="$WT_ROOT/.gateway.pid"
if [[ -f "$gateway_pid_file" ]]; then
  gw_pid=$(tr -d '[:space:]' < "$gateway_pid_file")
  gateway_exit_confirmed=0
  if ! validate_gateway_identity "$gw_pid"; then
    echo "gateway identity mismatch for pid=$gw_pid; refusing to signal or tear down stack" >&2
    exit 1
  fi
  gateway_status="$(gateway_process_status "$gw_pid")"
  if [[ "$gateway_status" == "alive" ]]; then
    if ! kill "$gw_pid" 2>/dev/null; then
      if [[ "$(gateway_process_status "$gw_pid")" != "exited" ]]; then
        echo "gateway pid=$gw_pid exists but cannot be signalled; retaining stack" >&2
        exit 1
      fi
      gateway_exit_confirmed=1
    fi
    # Wait for graceful exit, then force-kill on timeout.
    # bugfix-402-M6: elapsed was incremented by 1 per 0.2s sleep, so the loop
    # exited after GATEWAY_GRACE_SECONDS × 0.2s (≈ 1s) instead of the intended
    # GATEWAY_GRACE_SECONDS (5s).  Track ticks at 0.2s granularity.
    elapsed_ticks=0
    max_ticks=$(( GATEWAY_GRACE_SECONDS * 5 ))
    while [[ "$(gateway_process_status "$gw_pid")" != "exited" ]]; do
      if [[ $elapsed_ticks -ge $max_ticks ]]; then
        echo "gateway pid=$gw_pid did not exit within ${GATEWAY_GRACE_SECONDS}s — force-killing" >&2
        if ! kill -9 "$gw_pid" 2>/dev/null \
          && [[ "$(gateway_process_status "$gw_pid")" != "exited" ]]; then
          echo "gateway pid=$gw_pid survived but cannot receive SIGKILL; retaining stack" >&2
          exit 1
        fi
        # SIGKILL is asynchronous. Do not erase lifecycle evidence until the
        # owned external PID is observably gone.
        for _ in $(seq 1 10); do
          if [[ "$(gateway_process_status "$gw_pid")" == "exited" ]]; then
            gateway_exit_confirmed=1
            break
          fi
          sleep 0.05
        done
        break
      fi
      sleep 0.2
      elapsed_ticks=$(( elapsed_ticks + 1 ))
    done
    if [[ "$(gateway_process_status "$gw_pid")" == "exited" ]]; then
      gateway_exit_confirmed=1
    fi
  else
    gateway_exit_confirmed=1
  fi
  if [[ $gateway_exit_confirmed -eq 1 ]]; then
    # Only .gateway.pid establishes process ownership. gateway.pid and the
    # background state file may contain stale or unrelated numbers, so cleanup
    # must never signal the PIDs recorded inside them.
    rm -f "$gateway_pid_file"
    rm -f "$WT_ROOT/gateway.pid"
    rm -f "$WT_ROOT/.gateway-state.json"
    rm -f "$WT_ROOT/.gateway-identity.json"
  else
    echo "gateway pid=$gw_pid still appears alive; retaining lifecycle state" >&2
    exit 1
  fi
fi

# Step 2: Now that Gateway is gone, stop IM.
stopped_pids=()
for pidfile in "$WT_ROOT/.im.pid"; do
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
rm -f "$WT_ROOT/.gateway-config.yaml.pre-refactor-461.bak"

echo "e2e stack stopped (wt=$WT_ROOT)"
