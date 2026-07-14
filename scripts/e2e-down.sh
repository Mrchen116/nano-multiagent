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
# shellcheck source=scripts/e2e-lifecycle-lock.sh
source "$SCRIPT_DIR/e2e-lifecycle-lock.sh"
e2e_acquire_lifecycle_lock "$WT_ROOT" "$PYTHON_BIN"
# shellcheck source=scripts/e2e-owned-processes.sh
source "$SCRIPT_DIR/e2e-owned-processes.sh"

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

capture_gateway_lifecycle_snapshot() {
  local gw_pid=$1
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - \
    "$WT_ROOT" "$gw_pid" <<'PY'
from dataclasses import asdict
import json
from pathlib import Path
import sys

from personal_assistant.main import capture_gateway_lifecycle_evidence

snapshot = capture_gateway_lifecycle_evidence(Path(sys.argv[1]), int(sys.argv[2]))
print(json.dumps(asdict(snapshot), sort_keys=True))
PY
}

gateway_lifecycle_snapshot_matches() {
  local expected_json=$1 gw_pid=$2 current_json
  current_json="$(capture_gateway_lifecycle_snapshot "$gw_pid")" || return 1
  [[ "$current_json" == "$expected_json" ]]
}

clear_gateway_lifecycle_snapshot() {
  local expected_json=$1
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - \
    "$WT_ROOT" "$expected_json" <<'PY'
import json
from pathlib import Path
import sys

from personal_assistant.main import (
    GatewayLifecycleEvidenceFile,
    GatewayLifecycleEvidenceSnapshot,
    clear_gateway_lifecycle_evidence,
)

payload = json.loads(sys.argv[2])
expected = GatewayLifecycleEvidenceSnapshot(
    pid=payload["pid"],
    files=tuple(GatewayLifecycleEvidenceFile(**item) for item in payload["files"]),
)
clear_gateway_lifecycle_evidence(
    Path(sys.argv[1]), expected, allow_runtime_cleared=True
)
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

capture_im_pid_snapshot() {
  "$PYTHON_BIN" - "$WT_ROOT" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

root = Path(sys.argv[1]).resolve()
pid_path = root / ".im.pid"
identity_path = root / ".im.identity.json"


def capture_file(path: Path, label: str) -> tuple[dict[str, int | str], bytes]:
    try:
        before = path.lstat()
    except FileNotFoundError:
        raise SystemExit(f"{label} evidence is missing") from None
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise SystemExit(f"{label} evidence is non-regular")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        held_before = os.fstat(fd)
        chunks = []
        while chunk := os.read(fd, 4096):
            chunks.append(chunk)
        held_after = os.fstat(fd)
        current = path.lstat()
    finally:
        os.close(fd)
    content = b"".join(chunks)
    revision = (
        held_before.st_dev,
        held_before.st_ino,
        held_before.st_mode,
        held_before.st_size,
        held_before.st_mtime_ns,
    )
    if (
        revision
        != (
            held_after.st_dev,
            held_after.st_ino,
            held_after.st_mode,
            held_after.st_size,
            held_after.st_mtime_ns,
        )
        or revision
        != (
            current.st_dev,
            current.st_ino,
            current.st_mode,
            current.st_size,
            current.st_mtime_ns,
        )
        or held_before.st_nlink != 1
        or held_after.st_nlink != 1
        or current.st_nlink != 1
    ):
        raise SystemExit(f"{label} evidence changed during snapshot")
    return (
        {
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "device": held_before.st_dev,
            "inode": held_before.st_ino,
            "mode": held_before.st_mode,
            "mtime_ns": held_before.st_mtime_ns,
            "size": held_before.st_size,
        },
        content,
    )


if not (pid_path.exists() or pid_path.is_symlink()):
    print(json.dumps({"exists": False}, sort_keys=True))
    raise SystemExit(0)
pid_file, pid_content = capture_file(pid_path, "IM PID")
identity_file, identity_content = capture_file(identity_path, "IM identity")
try:
    pid_text = pid_content.decode("ascii").strip()
except UnicodeDecodeError as exc:
    raise SystemExit("IM PID evidence is malformed") from exc
if not pid_text.isdigit() or pid_text.startswith("0"):
    raise SystemExit("IM PID evidence is malformed")
pid = int(pid_text)
try:
    identity = json.loads(identity_content.decode("utf-8"))
except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    raise SystemExit("IM identity evidence is malformed") from exc
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
    raise SystemExit("IM identity evidence is malformed")
print(
    json.dumps(
        {
            "exists": True,
            "identity": identity,
            "identity_file": identity_file,
            "pid": pid,
            "pid_file": pid_file,
        },
        sort_keys=True,
    )
)
PY
}

im_pid_snapshot_matches() {
  local current
  current="$(capture_im_pid_snapshot)" || return 1
  [[ "$current" == "$im_pid_snapshot" ]]
}

im_owned_process_status() {
  local expected_json=$1
  PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - \
    "$expected_json" <<'PY'
import json
import sys

from personal_assistant.main import read_gateway_process_snapshot

expected = json.loads(sys.argv[1])
if not expected.get("exists"):
    print("exited")
    raise SystemExit(0)
snapshot = read_gateway_process_snapshot(expected["pid"])
if snapshot is None:
    print("exited")
    raise SystemExit(0)
expected_start = " ".join(expected["identity"]["process_start"].split())
if " ".join(snapshot.process_start.split()) != expected_start:
    raise SystemExit(1)
print("alive")
PY
}

clear_im_lifecycle_snapshot() {
  local expected_json=$1
  "$PYTHON_BIN" - "$WT_ROOT" "$expected_json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
expected = json.loads(sys.argv[2])
if not expected.get("exists"):
    raise SystemExit(0)
paths = {
    "pid_file": root / ".im.pid",
    "identity_file": root / ".im.identity.json",
}
for key, path in paths.items():
    try:
        current = path.lstat()
        content = path.read_bytes()
    except OSError:
        raise SystemExit(1) from None
    revision = expected[key]
    if (
        current.st_dev != revision["device"]
        or current.st_ino != revision["inode"]
        or current.st_mode != revision["mode"]
        or current.st_size != revision["size"]
        or current.st_mtime_ns != revision["mtime_ns"]
        or current.st_nlink != 1
        or hashlib.sha256(content).hexdigest() != revision["content_sha256"]
    ):
        raise SystemExit(1)
for path in paths.values():
    path.unlink()
PY
}

# IM evidence is part of the same full-stack generation. Reject malformed or
# non-regular ownership before any Gateway signal can partially tear down it.
if [[ ! -e "$WT_ROOT/.im.pid" && ! -L "$WT_ROOT/.im.pid" ]]; then
  stack_evidence=0
  for evidence in \
    "$WT_ROOT/.im.identity.json" \
    "$WT_ROOT/.gateway.pid" \
    "$WT_ROOT/gateway.pid" \
    "$WT_ROOT/gateway.identity.json" \
    "$WT_ROOT/.gateway-state.json" \
    "$WT_ROOT/.gateway-identity.json" \
    "$WT_ROOT/.gateway-config.yaml" \
    "$WT_ROOT/.gateway-config.yaml.lock" \
    "$WT_ROOT/.e2e-ports.env" \
    "$WT_ROOT/.e2e-jwt-secret"; do
    [[ -e "$evidence" || -L "$evidence" ]] && stack_evidence=1
  done
  if [[ $stack_evidence -eq 1 ]]; then
    echo "IM PID evidence is missing; retaining complete stack" >&2
    exit 1
  fi
fi
im_pid_snapshot="$(capture_im_pid_snapshot)" || {
  echo "IM PID evidence is invalid; retaining complete stack" >&2
  exit 1
}
if ! im_owned_process_status "$im_pid_snapshot" >/dev/null; then
  echo "IM process identity mismatch; refusing to signal or tear down stack" >&2
  exit 1
fi

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
  [[ -e "$evidence" || -L "$evidence" ]] && gateway_internal_evidence=1
done
if [[ ( -e "$gateway_pid_file" || -L "$gateway_pid_file" ) \
  && ( ! -f "$gateway_pid_file" || -L "$gateway_pid_file" ) ]]; then
  echo "Gateway lifecycle evidence has no regular external PID owner; retaining stack" >&2
  exit 1
fi
if [[ ! -e "$gateway_pid_file" && ! -L "$gateway_pid_file" \
  && $gateway_internal_evidence -eq 1 ]]; then
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
  gateway_lifecycle_snapshot="$(capture_gateway_lifecycle_snapshot "$gw_pid")" || {
    echo "gateway lifecycle evidence is incomplete or malformed; retaining stack" >&2
    exit 1
  }
  if [[ "$gateway_status" == "alive" ]]; then
    gateway_expected_start="$($PYTHON_BIN -c \
      'import json,sys; print(json.load(open(sys.argv[1]))["process_start"])' \
      "$WT_ROOT/gateway.identity.json")"
    if ! validate_gateway_identity "$gw_pid" 1 \
      || ! gateway_lifecycle_snapshot_matches "$gateway_lifecycle_snapshot" "$gw_pid" \
      || ! im_pid_snapshot_matches \
      || ! im_owned_process_status "$im_pid_snapshot" >/dev/null; then
      echo "gateway identity changed before SIGTERM; retaining stack" >&2
      exit 1
    fi
    gateway_owned_snapshot="$(e2e_freeze_gateway_owned_processes \
      "$SRC_DIR" "$PYTHON_BIN" "$gw_pid" "$gateway_expected_start")" || {
      echo "gateway descendant ownership is unstable; retaining stack" >&2
      exit 1
    }
    if ! gateway_lifecycle_snapshot_matches "$gateway_lifecycle_snapshot" "$gw_pid" \
      || ! im_pid_snapshot_matches \
      || ! im_owned_process_status "$im_pid_snapshot" >/dev/null; then
      e2e_signal_gateway_owned_groups \
        "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot" CONT 0 || true
      echo "gateway evidence changed while freezing descendants; retaining stack" >&2
      exit 1
    fi
    if ! e2e_signal_gateway_owned_groups \
      "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot" TERM 0; then
      e2e_signal_gateway_owned_groups \
        "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot" CONT 0 || true
      echo "gateway owned groups cannot be signalled; retaining stack" >&2
      exit 1
    fi
    e2e_signal_gateway_owned_groups \
      "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot" CONT 0 || true
    # Wait for graceful exit, then force-kill on timeout.
    # bugfix-402-M6: elapsed was incremented by 1 per 0.2s sleep, so the loop
    # exited after GATEWAY_GRACE_SECONDS × 0.2s (≈ 1s) instead of the intended
    # GATEWAY_GRACE_SECONDS (5s).  Track ticks at 0.2s granularity.
    elapsed_ticks=0
    max_ticks=$(( GATEWAY_GRACE_SECONDS * 5 ))
    while [[ "$(e2e_gateway_owned_status \
      "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot")" != "exited" ]]; do
      if [[ $elapsed_ticks -ge $max_ticks ]]; then
        echo "gateway owned set did not exit within ${GATEWAY_GRACE_SECONDS}s — force-killing" >&2
        if ! e2e_signal_gateway_owned_groups \
          "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot" KILL 1; then
          echo "gateway owned set changed before SIGKILL; retaining stack" >&2
          exit 1
        fi
        # SIGKILL is asynchronous. Do not erase lifecycle evidence until the
        # owned external PID is observably gone.
        for _ in $(seq 1 10); do
          if [[ "$(e2e_gateway_owned_status \
            "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot")" == "exited" ]]; then
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
    if [[ "$(e2e_gateway_owned_status \
      "$SRC_DIR" "$PYTHON_BIN" "$gateway_owned_snapshot")" == "exited" ]]; then
      gateway_exit_confirmed=1
    fi
  else
    gateway_exit_confirmed=1
  fi
  if [[ $gateway_exit_confirmed -eq 1 ]]; then
    # Never signal internal evidence; clear it only while every file still
    # names the externally validated process instance.
    if ! clear_gateway_lifecycle_snapshot "$gateway_lifecycle_snapshot"; then
      echo "gateway lifecycle evidence changed during cleanup; retaining stack" >&2
      exit 1
    fi
  else
    echo "gateway owned process set still appears alive; retaining lifecycle state" >&2
    exit 1
  fi
fi

# Step 2: Now that Gateway is gone, stop and confirm IM before cleanup commit.
if ! im_pid_snapshot_matches; then
  echo "IM PID evidence changed during Gateway teardown; retaining generated state" >&2
  exit 1
fi
im_pid="$($PYTHON_BIN -c 'import json,sys; print(json.loads(sys.argv[1]).get("pid", ""))' "$im_pid_snapshot")"
if [[ -n "$im_pid" ]]; then
  if ! im_process_status="$(im_owned_process_status "$im_pid_snapshot")"; then
    echo "IM process identity mismatch; retaining generated state" >&2
    exit 1
  fi
  if [[ "$im_process_status" == alive ]]; then
    if ! kill "$im_pid" 2>/dev/null; then
      if ! im_process_status="$(im_owned_process_status "$im_pid_snapshot")"; then
        echo "IM process identity mismatch; retaining generated state" >&2
        exit 1
      fi
      if [[ "$im_process_status" == alive ]]; then
        echo "IM pid=$im_pid cannot be signalled; retaining generated state" >&2
        exit 1
      fi
    fi
    sleep 0.5
    im_process_status="$(im_owned_process_status "$im_pid_snapshot")" || {
      echo "IM process identity mismatch; retaining generated state" >&2
      exit 1
    }
    if [[ "$im_process_status" == alive ]]; then
      if ! im_pid_snapshot_matches; then
        echo "IM PID evidence changed before SIGKILL; retaining generated state" >&2
        exit 1
      fi
      kill -9 "$im_pid" 2>/dev/null || true
      for _ in $(seq 1 10); do
        im_process_status="$(im_owned_process_status "$im_pid_snapshot")" || {
          echo "IM process identity mismatch; retaining generated state" >&2
          exit 1
        }
        [[ "$im_process_status" == exited ]] && break
        sleep 0.05
      done
    fi
  fi
  im_process_status="$(im_owned_process_status "$im_pid_snapshot")" || {
    echo "IM process identity mismatch; retaining generated state" >&2
    exit 1
  }
  if [[ "$im_process_status" == alive ]]; then
    echo "IM pid=$im_pid still appears alive; retaining generated state" >&2
    exit 1
  fi
  if ! im_pid_snapshot_matches; then
    echo "IM PID evidence changed during teardown; retaining generated state" >&2
    exit 1
  fi
  if ! clear_im_lifecycle_snapshot "$im_pid_snapshot"; then
    echo "IM lifecycle evidence changed during cleanup; retaining generated state" >&2
    exit 1
  fi
fi

# The sidecar inode coordinates every project config writer. Remove this
# worktree-ephemeral lock only after both services exited and an exclusive,
# non-blocking advisory lock proves that no cooperative writer remains.
if ! clear_ephemeral_config_lock; then
  echo "ephemeral config lock is busy or non-regular; retaining generated state" >&2
  exit 1
fi

# Remove generated state. .gateway-workspace/ is preserved for post-mortem.
rm -f "$WT_ROOT/.e2e-ports.env"
rm -f "$WT_ROOT/.e2e-jwt-secret"
rm -f "$WT_ROOT/.gateway-config.yaml"
rm -f "$WT_ROOT/.gateway-config.yaml.pre-refactor-461.bak"

echo "e2e stack stopped (wt=$WT_ROOT)"
