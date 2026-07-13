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
    --wt) WT_ROOT="$(cd "$2" && pwd -P)"; shift 2 ;;
    -h|--help) sed -n '1,/^set -e/p' "$0" | sed -n '2,/^$/p'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

WT_ROOT="$(cd "$WT_ROOT" && pwd -P)"

PYTHON_BIN="$(command -v python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "python is required to validate Gateway teardown identity" >&2
  exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../src" && pwd)"

gateway_process_snapshot() {
  local pid=$1
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$pid" <<'PY'
from dataclasses import asdict
import json
import sys

from personal_assistant.main import read_gateway_process_snapshot

snapshot = read_gateway_process_snapshot(int(sys.argv[1]))
if snapshot is None:
    raise SystemExit(1)
print(json.dumps(asdict(snapshot), sort_keys=True))
PY
}

gateway_process_status() {
  local pid=$1 process_stat
  process_stat="$(LC_ALL=C LANG=C TZ=UTC ps -p "$pid" -o stat= 2>/dev/null | tr -d '[:space:]')"
  if [[ -z "$process_stat" || "$process_stat" == Z* ]]; then
    echo exited
  else
    echo alive
  fi
}

validate_gateway_identity() {
  local gw_pid=$1 require_live=$2 identity_file internal_pid snapshot_json
  identity_file="$WT_ROOT/gateway.identity.json"
  if [[ ! -f "$identity_file" || -L "$identity_file" \
    || ! -f "$WT_ROOT/gateway.pid" || -L "$WT_ROOT/gateway.pid" ]]; then
    return 1
  fi
  internal_pid="$(tr -d '[:space:]' < "$WT_ROOT/gateway.pid")"
  [[ "$internal_pid" == "$gw_pid" ]] || return 1
  if ! "$PYTHON_BIN" - \
    "$identity_file" "$WT_ROOT/.gateway-state.json" "$gw_pid" \
    "$WT_ROOT/.gateway-config.yaml" <<'PY'
import json
from pathlib import Path
import sys

identity_path, state_path, pid, config_path = sys.argv[1:]
pid = int(pid)
config_path = str(Path(config_path).resolve())
payload = json.loads(Path(identity_path).read_text(encoding="utf-8"))
argv = payload.get("argv")
config_indexes = (
    [index for index, value in enumerate(argv) if value == "--config"]
    if isinstance(argv, list)
    else []
)
valid = (
    payload.get("schema_version") == 1
    and payload.get("pid") == pid
    and payload.get("config_path") == config_path
    and payload.get("entry_module") == "personal_assistant.main"
    and isinstance(payload.get("process_start"), str)
    and bool(payload["process_start"].strip())
    and len(config_indexes) == 1
    and config_indexes[0] + 1 < len(argv)
    and Path(argv[config_indexes[0] + 1]).resolve() == Path(config_path)
    and argv.count("--foreground") == 1
    and argv.count("--auto-bind") == 1
)
state = Path(state_path)
if valid and state.exists():
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    valid = state_payload.get("pid") == pid
    if state_payload.get("config_path") is not None:
        valid = valid and Path(state_payload["config_path"]).resolve() == Path(config_path)
raise SystemExit(0 if valid else 1)
PY
  then
    return 1
  fi
  [[ "$require_live" == 1 ]] || return 0

  snapshot_json="$(gateway_process_snapshot "$gw_pid")" || return 1
  "$PYTHON_BIN" - "$snapshot_json" "$identity_file" <<'PY'
import json
from pathlib import Path
import sys

snapshot_json, identity_path = sys.argv[1:]
snapshot = json.loads(snapshot_json)
payload = json.loads(Path(identity_path).read_text(encoding="utf-8"))
normalized_start = " ".join(snapshot["process_start"].split())
expected_start = " ".join(payload["process_start"].split())
raise SystemExit(
    0
    if snapshot.get("pid") == payload.get("pid")
    and normalized_start == expected_start
    else 1
)
PY
}

clear_matching_gateway_lifecycle() {
  local gw_pid=$1
  "$PYTHON_BIN" - "$WT_ROOT" "$gw_pid" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
pid = int(sys.argv[2])
valid = True
for name in (".gateway.pid", "gateway.pid"):
    path = root / name
    if not path.exists():
        continue
    try:
        current = int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        valid = False
        continue
    if current == pid:
        path.unlink(missing_ok=True)
    else:
        valid = False
for name in ("gateway.identity.json", ".gateway-state.json"):
    path = root / name
    if not path.exists():
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        valid = False
        continue
    if payload.get("pid") == pid:
        path.unlink(missing_ok=True)
    else:
        valid = False
raise SystemExit(0 if valid else 1)
PY
}

# Step 1: Signal Gateway and wait for graceful exit before touching IM.
# Gateway's shutdown drains in-flight runs before closing IM transport;
# sending SIGTERM to both at once would close IM before runs settle.
gateway_pid_file="$WT_ROOT/.gateway.pid"
gateway_internal_evidence=0
for evidence in \
  "$WT_ROOT/gateway.pid" \
  "$WT_ROOT/gateway.identity.json" \
  "$WT_ROOT/.gateway-state.json" \
  "$WT_ROOT/.gateway-identity.json"; do
  [[ -e "$evidence" ]] && gateway_internal_evidence=1
done
if [[ -e "$gateway_pid_file" && ( ! -f "$gateway_pid_file" || -L "$gateway_pid_file" ) ]]; then
  echo "Gateway lifecycle evidence has no regular external PID owner; retaining stack" >&2
  exit 1
fi
if [[ ! -e "$gateway_pid_file" && $gateway_internal_evidence -eq 1 ]]; then
  echo "Gateway lifecycle evidence exists without external PID owner; retaining stack" >&2
  exit 1
fi
if [[ -f "$gateway_pid_file" ]]; then
  gw_pid=$(tr -d '[:space:]' < "$gateway_pid_file")
  if [[ ! "$gw_pid" =~ ^[1-9][0-9]*$ ]]; then
    echo "gateway external PID is malformed; retaining stack" >&2
    exit 1
  fi
  gateway_exit_confirmed=0
  gateway_status="$(gateway_process_status "$gw_pid")"
  require_live=1
  [[ "$gateway_status" == exited ]] && require_live=0
  if ! validate_gateway_identity "$gw_pid" "$require_live"; then
    echo "gateway identity mismatch for pid=$gw_pid; refusing to signal or tear down stack" >&2
    exit 1
  fi
  if [[ "$gateway_status" == "alive" ]]; then
    if ! validate_gateway_identity "$gw_pid" 1; then
      echo "gateway identity changed before SIGTERM; retaining stack" >&2
      exit 1
    fi
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
        if ! validate_gateway_identity "$gw_pid" 1; then
          echo "gateway identity changed before SIGKILL; retaining stack" >&2
          exit 1
        fi
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
    # Never signal internal evidence; clear it only while every file still
    # names the externally validated process instance.
    if ! clear_matching_gateway_lifecycle "$gw_pid"; then
      echo "gateway lifecycle evidence changed during cleanup; retaining stack" >&2
      exit 1
    fi
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
