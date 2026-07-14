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
#   ./scripts/e2e-up.sh                                  # use defaults
#   ./scripts/e2e-up.sh --main-config /path/to/cfg.yaml  # alt source config
#   ./scripts/e2e-up.sh --wt /custom/worktree/path       # alt target worktree
#
# Side effects in $WT_ROOT (default = $PWD):
#   .e2e-ports.env            (source this in your shell to expose ports)
#   .e2e-jwt-secret           (random IM JWT secret for this run)
#   .gateway-config.yaml      (isolated copy of main config)
#   .gateway-workspace/       (per-agent workspaces, replacing ~/nano-assistant/workspace)
#   .im.pid / .im.identity.json / .gateway.pid
#   gateway.identity.json  (public PID/config/argv start identity for safe teardown)
#   .im.log / .gateway.log

set -euo pipefail

# ─── arg parsing ─────────────────────────────────────────────────────────────

WT_ROOT="${PWD}"
MAIN_CFG="${HOME}/.nano-assistant/config.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) WT_ROOT="$(cd "$2" && pwd -P)"; shift 2 ;;
    --main-config) MAIN_CFG="$2"; shift 2 ;;
    -h|--help) sed -n '1,/^set -e/p' "$0" | sed -n '2,/^$/p'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Bash preserves a logical symlink PWD. Lifecycle identity and argv comparisons
# use one physical root regardless of whether --wt was explicit or defaulted.
WT_ROOT="$(cd "$WT_ROOT" && pwd -P)"

if [[ ! -f "$MAIN_CFG" ]]; then
  echo "main config not found: $MAIN_CFG" >&2
  echo "create ~/.nano-assistant/config.yaml first (see AGENTS.md) or pass --main-config" >&2
  exit 1
fi

# Resolve the checkout runtime before the first lifecycle preflight so up/down
# can hold one external generation lock across every check, spawn and rollback.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd 2>/dev/null)"
REPO_ROOT="${REPO_ROOT:-$(git -C "$WT_ROOT" rev-parse --show-toplevel 2>/dev/null || dirname "$WT_ROOT")}"
SRC_DIR="$REPO_ROOT/src"
FREE_PORTS_SH="$REPO_ROOT/scripts/free-ports.sh"
[[ -x "$FREE_PORTS_SH" ]] || FREE_PORTS_SH="$SCRIPT_DIR/free-ports.sh"
PYTHON_BIN="$(command -v python || true)"
if [[ -z "$PYTHON_BIN" ]] || ! "$PYTHON_BIN" -c "import yaml" 2>/dev/null; then
  echo "python with project dependencies (including PyYAML) not found on PATH" >&2
  exit 1
fi
# shellcheck source=scripts/e2e-lifecycle-lock.sh
source "$SCRIPT_DIR/e2e-lifecycle-lock.sh"
e2e_acquire_lifecycle_lock "$WT_ROOT" "$PYTHON_BIN"
# shellcheck source=scripts/e2e-owned-processes.sh
source "$SCRIPT_DIR/e2e-owned-processes.sh"

# ─── liveness check (refuse to clobber) ──────────────────────────────────────

external_gateway_pid="$WT_ROOT/.gateway.pid"
if [[ ( -e "$external_gateway_pid" || -L "$external_gateway_pid" ) \
  && ( ! -f "$external_gateway_pid" || -L "$external_gateway_pid" ) ]]; then
  echo "non-regular external Gateway PID evidence: $external_gateway_pid" >&2
  exit 1
fi
if [[ -f "$external_gateway_pid" ]]; then
  existing_gateway_pid="$(tr -d '[:space:]' < "$external_gateway_pid")"
  if [[ ! "$existing_gateway_pid" =~ ^[1-9][0-9]*$ ]]; then
    echo "external Gateway PID evidence is malformed: $external_gateway_pid" >&2
    exit 1
  fi
  if kill -0 "$existing_gateway_pid" 2>/dev/null; then
    echo "service still running: $external_gateway_pid (pid=$existing_gateway_pid)" >&2
    echo "run ./scripts/e2e-down.sh first" >&2
    exit 1
  fi
fi

# Internal runtime evidence remains authoritative even when the external wrapper
# PID file is missing. Never erase it during start: down owns validated cleanup.
if ! internal_gateway_status="$(
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$WT_ROOT" <<'PY'
import json
from pathlib import Path
import stat
import sys

from personal_assistant.main import read_gateway_process_snapshot

root = Path(sys.argv[1]).resolve()
pid_path = root / "gateway.pid"
identity_path = root / "gateway.identity.json"
state_path = root / ".gateway-state.json"
legacy_path = root / ".gateway-identity.json"
evidence = (pid_path, identity_path, state_path, legacy_path)
if not any(path.exists() or path.is_symlink() for path in evidence):
    print("absent")
    raise SystemExit(0)
for path in evidence:
    if not (path.exists() or path.is_symlink()):
        continue
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise SystemExit(1)
if legacy_path.exists() or not pid_path.exists() or not identity_path.exists():
    raise SystemExit(1)
try:
    pid_text = pid_path.read_text(encoding="ascii").strip()
    if not pid_text.isdigit() or pid_text.startswith("0"):
        raise ValueError
    pid = int(pid_text)
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    argv = identity.get("argv")
    config_path = (root / ".gateway-config.yaml").resolve()
    config_indexes = (
        [index for index, value in enumerate(argv) if value == "--config"]
        if isinstance(argv, list)
        else []
    )
    valid = (
        identity.get("schema_version") == 1
        and identity.get("pid") == pid
        and Path(identity.get("config_path", "")).resolve() == config_path
        and identity.get("entry_module") == "personal_assistant.main"
        and isinstance(identity.get("process_start"), str)
        and bool(identity["process_start"].strip())
        and len(config_indexes) == 1
        and config_indexes[0] + 1 < len(argv)
        and Path(argv[config_indexes[0] + 1]).resolve() == config_path
        and argv.count("--foreground") == 1
        and argv.count("--auto-bind") == 1
    )
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        valid = valid and state.get("pid") == pid
        if state.get("config_path") is not None:
            valid = valid and Path(state["config_path"]).resolve() == config_path
    if not valid:
        raise ValueError
except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
    raise SystemExit(1) from None
snapshot = read_gateway_process_snapshot(pid)
if snapshot is None:
    print("stale")
elif " ".join(snapshot.process_start.split()) == " ".join(
    identity["process_start"].split()
):
    print("live")
else:
    raise SystemExit(1)
PY
)"; then
  echo "Gateway lifecycle evidence is invalid; retaining it for validated teardown" >&2
  exit 1
fi
case "$internal_gateway_status" in
  absent) ;;
  live)
    echo "service still running: $WT_ROOT/gateway.pid" >&2
    echo "run ./scripts/e2e-down.sh first" >&2
    exit 1
    ;;
  stale)
    echo "stale Gateway lifecycle evidence requires validated teardown" >&2
    echo "run ./scripts/e2e-down.sh first" >&2
    exit 1
    ;;
  *)
    echo "Gateway lifecycle evidence is invalid; retaining it for validated teardown" >&2
    exit 1
    ;;
esac

# IM ownership is a PID plus durable birth identity. A reused PID, partial pair,
# or stale complete pair must go through down instead of being overwritten.
if ! im_evidence_status="$(
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$WT_ROOT" <<'PY'
import json
from pathlib import Path
import stat
import sys

from personal_assistant.main import read_gateway_process_snapshot

root = Path(sys.argv[1]).resolve()
pid_path = root / ".im.pid"
identity_path = root / ".im.identity.json"
evidence = (pid_path, identity_path)
if not any(path.exists() or path.is_symlink() for path in evidence):
    print("absent")
    raise SystemExit(0)
if not all(path.exists() and not path.is_symlink() for path in evidence):
    raise SystemExit(1)
if not all(stat.S_ISREG(path.lstat().st_mode) for path in evidence):
    raise SystemExit(1)
try:
    pid_text = pid_path.read_text(encoding="ascii").strip()
    if not pid_text.isdigit() or pid_text.startswith("0"):
        raise ValueError
    pid = int(pid_text)
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    argv = identity.get("argv")
    valid = (
        identity.get("schema_version") == 1
        and identity.get("pid") == pid
        and isinstance(identity.get("process_start"), str)
        and bool(identity["process_start"].strip())
        and Path(identity.get("cwd", "")).resolve() == root
        and isinstance(argv, list)
        and argv[:6]
        == ["-m", "uvicorn", "IM.app:app", "--host", "127.0.0.1", "--port"]
        and len(argv) == 7
        and isinstance(argv[6], str)
        and argv[6].isdigit()
    )
    if not valid:
        raise ValueError
except (OSError, TypeError, ValueError, json.JSONDecodeError):
    raise SystemExit(1) from None
snapshot = read_gateway_process_snapshot(pid)
if snapshot is None:
    print("stale")
elif " ".join(snapshot.process_start.split()) == " ".join(
    identity["process_start"].split()
):
    print("live")
else:
    raise SystemExit(1)
PY
)"; then
  echo "IM lifecycle evidence is invalid; retaining it for validated teardown" >&2
  exit 1
fi
case "$im_evidence_status" in
  absent) ;;
  live)
    echo "service still running: $WT_ROOT/.im.pid" >&2
    echo "run ./scripts/e2e-down.sh first" >&2
    exit 1
    ;;
  stale)
    echo "stale IM lifecycle evidence requires validated teardown" >&2
    echo "run ./scripts/e2e-down.sh first" >&2
    exit 1
    ;;
  *)
    echo "IM lifecycle evidence is invalid; retaining it for validated teardown" >&2
    exit 1
    ;;
esac

# A dead external wrapper claim is not signal authority and is safe to discard
# only after both runtime-owned evidence sets are proven absent.
rm -f "$external_gateway_pid"

# ─── port allocation ─────────────────────────────────────────────────────────

IM_PID=""
IM_PROCESS_START=""
GW_PID=""
GW_PROCESS_START=""
ROLLBACK_ACTIVE=1

capture_spawned_process_start() {
  local pid=$1
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$pid" <<'PY'
import sys

from personal_assistant.main import read_gateway_process_snapshot

snapshot = read_gateway_process_snapshot(int(sys.argv[1]))
if snapshot is None:
    raise SystemExit(1)
print(snapshot.process_start)
PY
}

spawned_process_status() {
  local pid=$1 expected_start=$2
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - \
    "$pid" "$expected_start" <<'PY'
import sys

from personal_assistant.main import read_gateway_process_snapshot

snapshot = read_gateway_process_snapshot(int(sys.argv[1]))
if snapshot is None:
    print("exited")
elif " ".join(snapshot.process_start.split()) == " ".join(sys.argv[2].split()):
    print("alive")
else:
    print("mismatch")
PY
}

spawned_process_liveness() {
  local pid=$1 process_stat
  process_stat="$(ps -p "$pid" -o stat= 2>/dev/null | tr -d '[:space:]')"
  if [[ -z "$process_stat" || "$process_stat" == Z* ]]; then
    printf '%s\n' exited
  else
    printf '%s\n' alive
  fi
}

stop_spawned_pid() {
  local pid=$1 expected_start=$2 status
  [[ -n "$pid" ]] || return 0
  status="$(spawned_process_status "$pid" "$expected_start")" || return 1
  [[ "$status" == exited ]] && return 0
  [[ "$status" == alive ]] || return 1
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    status="$(spawned_process_status "$pid" "$expected_start")" || return 1
    [[ "$status" == exited ]] && return 0
    [[ "$status" == alive ]] || return 1
    sleep 0.05
  done
  status="$(spawned_process_status "$pid" "$expected_start")" || return 1
  [[ "$status" == exited ]] && return 0
  [[ "$status" == alive ]] || return 1
  kill -9 "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    status="$(spawned_process_status "$pid" "$expected_start")" || return 1
    [[ "$status" == exited ]] && return 0
    [[ "$status" == alive ]] || return 1
    sleep 0.05
  done
  return 1
}

stop_spawned_gateway() {
  local pid=$1 expected_start=$2 owned status
  [[ -n "$pid" ]] || return 0
  status="$(spawned_process_status "$pid" "$expected_start")" || return 1
  [[ "$status" == exited ]] && return 0
  [[ "$status" == alive ]] || return 1
  owned="$(e2e_freeze_gateway_owned_processes \
    "$SRC_DIR" "$PYTHON_BIN" "$pid" "$expected_start")" || return 1
  if ! e2e_signal_gateway_owned_groups \
    "$SRC_DIR" "$PYTHON_BIN" "$owned" TERM 0; then
    e2e_signal_gateway_owned_groups \
      "$SRC_DIR" "$PYTHON_BIN" "$owned" CONT 0 || true
    return 1
  fi
  e2e_signal_gateway_owned_groups \
    "$SRC_DIR" "$PYTHON_BIN" "$owned" CONT 0 || true
  for _ in $(seq 1 20); do
    [[ "$(e2e_gateway_owned_status \
      "$SRC_DIR" "$PYTHON_BIN" "$owned")" == exited ]] && return 0
    sleep 0.05
  done
  e2e_signal_gateway_owned_groups \
    "$SRC_DIR" "$PYTHON_BIN" "$owned" KILL 1 || return 1
  for _ in $(seq 1 20); do
    [[ "$(e2e_gateway_owned_status \
      "$SRC_DIR" "$PYTHON_BIN" "$owned")" == exited ]] && return 0
    sleep 0.05
  done
  return 1
}

clear_spawned_lifecycle_evidence() {
  local kind=$1 expected_pid=$2 expected_start=$3
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - \
    "$WT_ROOT" "$kind" "$expected_pid" "$expected_start" <<'PY'
import json
from pathlib import Path
import stat
import sys

from personal_assistant.main import read_gateway_process_snapshot

root = Path(sys.argv[1]).resolve()
kind = sys.argv[2]
expected_pid = int(sys.argv[3])
expected_start = " ".join(sys.argv[4].split())
if read_gateway_process_snapshot(expected_pid) is not None:
    raise SystemExit(1)
names = (
    (".im.pid", ".im.identity.json")
    if kind == "im"
    else (".gateway.pid", "gateway.pid", "gateway.identity.json", ".gateway-state.json")
)
paths = [root / name for name in names]
for path in paths:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        continue
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise SystemExit(1)
    if path.suffix == ".pid":
        try:
            actual_pid = int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            raise SystemExit(1) from None
        if actual_pid != expected_pid:
            raise SystemExit(1)
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit(1) from None
    if payload.get("pid") != expected_pid:
        raise SystemExit(1)
    if path.name.endswith("identity.json"):
        actual_start = payload.get("process_start")
        if not isinstance(actual_start, str) or " ".join(actual_start.split()) != expected_start:
            raise SystemExit(1)
for path in paths:
    path.unlink(missing_ok=True)
PY
}

clear_ephemeral_config_lock() {
  local lock_path="$WT_ROOT/.gateway-config.yaml.lock"
  [[ -e "$lock_path" || -L "$lock_path" ]] || return 0
  "$PYTHON_BIN" - "$lock_path" <<'PY'
import fcntl
import os
from pathlib import Path
import stat
import sys

path = Path(sys.argv[1])
before = path.lstat()
if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
    raise SystemExit(1)
fd = os.open(path, os.O_RDWR)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    held = os.fstat(fd)
    current = path.lstat()
    if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
        raise SystemExit(1)
    path.unlink()
finally:
    os.close(fd)
PY
}

rollback_spawned_stack() {
  local exit_code=$?
  [[ $ROLLBACK_ACTIVE -eq 1 && $exit_code -ne 0 ]] || return "$exit_code"
  trap - EXIT
  set +e
  if [[ -n "$GW_PID" ]]; then
    if ! stop_spawned_gateway "$GW_PID" "$GW_PROCESS_START"; then
      echo "rollback could not stop Gateway pid=$GW_PID; retaining complete stack evidence" >&2
      exit "$exit_code"
    fi
    if ! clear_spawned_lifecycle_evidence gateway "$GW_PID" "$GW_PROCESS_START"; then
      echo "rollback could not clear Gateway evidence; retaining complete stack evidence" >&2
      exit "$exit_code"
    fi
  fi
  if [[ -n "$IM_PID" ]]; then
    if ! stop_spawned_pid "$IM_PID" "$IM_PROCESS_START"; then
      echo "rollback could not stop IM pid=$IM_PID; retaining remaining evidence" >&2
      exit "$exit_code"
    fi
    if ! clear_spawned_lifecycle_evidence im "$IM_PID" "$IM_PROCESS_START"; then
      echo "rollback could not clear IM evidence; retaining remaining evidence" >&2
      exit "$exit_code"
    fi
  fi
  if ! clear_ephemeral_config_lock; then
    echo "rollback could not exclusively remove ephemeral config lock; retaining it" >&2
  fi
  exit "$exit_code"
}

trap rollback_spawned_stack EXIT
# The agent runtime is in-process; only the IM service needs a port.
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
  WT_CFG_PY="$WT_CFG" NODE_ID="$NODE_ID" IM_PORT="$IM_PORT" WORKSPACE_DIR="$WORKSPACE_DIR" \
    "$PYTHON_BIN" - <<'PY'
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
"$PYTHON_BIN" - "$WT_CFG" "$WORKSPACE_DIR" <<'PY'
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
  "$PYTHON_BIN" -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" \
  > "$WT_ROOT/.im.log" 2>&1 9>&- &
IM_PID=$!
IM_PROCESS_START="$(capture_spawned_process_start "$IM_PID")" || {
  echo "IM exited before process identity capture" >&2
  exit 1
}
PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - \
  "$WT_ROOT" "$IM_PID" "$IM_PORT" <<'PY'
import json
from pathlib import Path
import sys

from personal_assistant.main import (
    _atomic_write_gateway_file,
    read_gateway_process_snapshot,
)

root = Path(sys.argv[1]).resolve()
pid = int(sys.argv[2])
port = sys.argv[3]
snapshot = read_gateway_process_snapshot(pid)
if snapshot is None:
    raise SystemExit("IM exited before identity publication")
payload = {
    "schema_version": 1,
    "pid": pid,
    "process_start": snapshot.process_start,
    "cwd": str(root),
    "argv": [
        "-m",
        "uvicorn",
        "IM.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        port,
    ],
}
_atomic_write_gateway_file(
    root / ".im.identity.json",
    json.dumps(payload, indent=2, sort_keys=True).encode(),
)
PY
echo "$IM_PID" > "$WT_ROOT/.im.pid"

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
LOGIN_JSON="$(
  curl -sf -X POST "http://127.0.0.1:$IM_PORT/im/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"nano","password":"nano1234"}' 2>/dev/null
)" || true
NANO_USER_ID="$(
  printf '%s' "$LOGIN_JSON" \
    | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); print(d.get('user',{}).get('id') or d.get('id',''))" 2>/dev/null
)" || true
NANO_ACCESS_TOKEN="$(
  printf '%s' "$LOGIN_JSON" \
    | "$PYTHON_BIN" -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null
)" || true
if [[ -n "$NANO_USER_ID" ]]; then
  if command -v yq >/dev/null 2>&1; then
    yq -i ".node.user_id = \"$NANO_USER_ID\"" "$WT_CFG"
  else
    NANO_USER_ID="$NANO_USER_ID" WT_CFG_PY="$WT_CFG" "$PYTHON_BIN" - <<'PY'
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

if ! "$PYTHON_BIN" -c "import yaml; cfg=yaml.safe_load(open('$WT_CFG')); exit(0 if 'llm' in cfg else 1)" 2>/dev/null; then
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

PYTHONPATH="$SRC_DIR" "$PYTHON_BIN" -c \
  'import os,sys; os.setsid(); os.execv(sys.argv[1], sys.argv[1:])' \
  "$PYTHON_BIN" -m personal_assistant.main \
  --config "$WT_CFG" \
  --im-service-url "http://127.0.0.1:$IM_PORT" \
  --foreground \
  --auto-bind \
  > "$WT_ROOT/.gateway.log" 2>&1 9>&- &
GW_PID=$!
GW_PROCESS_START="$(capture_spawned_process_start "$GW_PID")" || {
  echo "Gateway exited before process identity capture" >&2
  exit 1
}
echo "$GW_PID" > "$WT_ROOT/.gateway.pid"

# The external shell PID alone is not sufficient signal ownership. Foreground
# runtime publishes the same public identity used by operator stop; wait within
# the configured launcher budget and require both PID claims + exact argv schema.
GW_IDENTITY_TICKS="$($PYTHON_BIN - "$WT_CFG" <<'PY'
import math
import sys
import yaml

payload = yaml.safe_load(open(sys.argv[1])) or {}
gateway = payload.get("gateway") if isinstance(payload.get("gateway"), dict) else {}
legacy = payload.get("kernel") if isinstance(payload.get("kernel"), dict) else {}
timeout = gateway.get("startup_timeout_seconds", legacy.get("startup_timeout_seconds", 15))
print(max(1, math.ceil(float(timeout) / 0.1)))
PY
)"
GW_IDENTITY_READY=0
for _ in $(seq 1 "$GW_IDENTITY_TICKS"); do
  if [[ -f "$WT_ROOT/gateway.pid" ]]; then
    INTERNAL_GW_PID=$(tr -d '[:space:]' < "$WT_ROOT/gateway.pid")
    if [[ "$INTERNAL_GW_PID" != "$GW_PID" ]]; then
      echo "Gateway identity mismatch: external=$GW_PID internal=$INTERNAL_GW_PID" >&2
      exit 1
    fi
    if [[ -f "$WT_ROOT/gateway.identity.json" ]]; then
      if ! "$PYTHON_BIN" - \
        "$WT_ROOT/gateway.identity.json" "$GW_PID" "$WT_CFG" \
        "http://127.0.0.1:$IM_PORT" <<'PY'
import json
from pathlib import Path
import sys

identity_path, pid, config_path, im_url = sys.argv[1:]
payload = json.loads(Path(identity_path).read_text(encoding="utf-8"))
expected_config = str(Path(config_path).resolve())
expected_argv = [
    "--config",
    expected_config,
    "--im-service-url",
    im_url,
    "--foreground",
    "--auto-bind",
]
raise SystemExit(
    0
    if payload.get("schema_version") == 1
    and payload.get("pid") == int(pid)
    and payload.get("config_path") == expected_config
    and payload.get("entry_module") == "personal_assistant.main"
    and payload.get("argv") == expected_argv
    and isinstance(payload.get("process_start"), str)
    and payload["process_start"].strip()
    else 1
)
PY
      then
        echo "Gateway public process identity mismatch for pid=$GW_PID" >&2
        exit 1
      fi
      GW_PGID="$(ps -p "$GW_PID" -o pgid= 2>/dev/null | tr -d '[:space:]')"
      if [[ "$GW_PGID" != "$GW_PID" ]]; then
        echo "Gateway must be its exclusive process-group leader: pid=$GW_PID pgid=$GW_PGID" >&2
        exit 1
      fi
      GW_IDENTITY_READY=1; break
    fi
  fi
  if [[ "$(spawned_process_liveness "$GW_PID")" == exited ]]; then
    echo "Gateway process died before identity confirmation; see $WT_ROOT/.gateway.log" >&2
    exit 1
  fi
  sleep 0.1
done
if [[ $GW_IDENTITY_READY -eq 0 ]]; then
  echo "Gateway did not establish teardown identity; see $WT_ROOT/.gateway.log" >&2
  exit 1
fi

# Wait for the Gateway process to stay alive and its node to become online in IM.
# This is transport-level startup evidence only; user-visible journeys remain the
# end-to-end readiness evidence.
GW_READY=0
for _ in $(seq 1 60); do
  if [[ -n "$NANO_ACCESS_TOKEN" ]] \
    && curl -sf "http://127.0.0.1:$IM_PORT/im/v1/nodes" \
      -H "Authorization: Bearer $NANO_ACCESS_TOKEN" 2>/dev/null \
      | NODE_ID="$NODE_ID" "$PYTHON_BIN" -c '
import json, os, sys
nodes = json.load(sys.stdin)
raise SystemExit(0 if any(
    item.get("node_id") == os.environ["NODE_ID"] and item.get("status") == "online"
    for item in nodes
) else 1)
'; then
    GW_READY=1; break
  fi
  if ! kill -0 "$GW_PID" 2>/dev/null; then
    echo "Gateway process died during startup; see $WT_ROOT/.gateway.log" >&2
    tail -30 "$WT_ROOT/.gateway.log" >&2 || true
    exit 1
  fi
  sleep 0.5
done
if [[ $GW_READY -eq 0 ]]; then
  echo "Gateway node did not become online within 30s; see $WT_ROOT/.gateway.log" >&2
  tail -30 "$WT_ROOT/.gateway.log" >&2 || true
  exit 1
fi

# ─── persist port map for follow-up curl / tests ─────────────────────────────

cat > "$WT_ROOT/.e2e-ports.env" <<EOF
# Generated by scripts/e2e-up.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# The agent runtime is in-process; no separate service port is exported.
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

ROLLBACK_ACTIVE=0
trap - EXIT
