#!/usr/bin/env bash
# Shared structured Gateway descendant ownership helpers for e2e up/down.

e2e_capture_gateway_owned_processes() {
  local src_dir=$1 python_bin=$2 leader_pid=$3 expected_start=${4-}
  PYTHONPATH="$src_dir${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" - \
    "$leader_pid" "$expected_start" <<'PY'
from dataclasses import asdict
import json
import sys

from personal_assistant.main import capture_gateway_owned_process_set

expected_start = sys.argv[2] or None
owned = capture_gateway_owned_process_set(
    int(sys.argv[1]), expected_process_start=expected_start
)
print(json.dumps(asdict(owned), sort_keys=True))
PY
}

e2e_gateway_owned_groups() {
  local src_dir=$1 python_bin=$2 expected_json=$3 allow_reparented=$4
  "$python_bin" - "$expected_json" "$allow_reparented" <<'PY'
import json
import os
import subprocess
import sys

payload = json.loads(sys.argv[1])
allow_reparented = sys.argv[2] == "1"
expected = {item["pid"]: item for item in payload["processes"]}
result = subprocess.run(
    ["ps", "-axo", "pid=,ppid=,pgid=,stat=,lstart="],
    capture_output=True,
    text=True,
    check=False,
    env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
)
if result.returncode != 0:
    raise SystemExit("cannot read owned process topology")
rows = {}
for line in result.stdout.splitlines():
    parts = line.split()
    if len(parts) < 9:
        continue
    try:
        pid, ppid, pgid = map(int, parts[:3])
    except ValueError:
        continue
    rows[pid] = {
        "ppid": ppid,
        "pgid": pgid,
        "start": " ".join(parts[4:9]),
        "zombie": parts[3].startswith("Z"),
    }
live = {}
for pid, item in expected.items():
    row = rows.get(pid)
    if row is None or row["zombie"]:
        continue
    if row["start"] != " ".join(item["process_start"].split()):
        raise SystemExit(f"Gateway descendant pid={pid} birth identity changed")
    if row["pgid"] != item["pgid"]:
        raise SystemExit(f"Gateway descendant pid={pid} PGID changed")
    live[pid] = row
for pid, row in live.items():
    expected_ppid = expected[pid]["ppid"]
    if row["ppid"] == expected_ppid:
        continue
    if not (
        allow_reparented
        and expected_ppid in expected
        and expected_ppid not in live
    ):
        raise SystemExit(f"Gateway descendant pid={pid} PPID changed")
groups = {row["pgid"] for row in live.values()}
for pid, row in rows.items():
    if row["zombie"] or row["pgid"] not in groups or pid in expected:
        continue
    raise SystemExit(f"Gateway owned process group gained foreign pid={pid}")
leader_pid = payload["leader_pid"]
if leader_pid in live:
    descendants = {leader_pid}
    while True:
        additions = {
            pid
            for pid, row in rows.items()
            if not row["zombie"] and row["ppid"] in descendants
        } - descendants
        if not additions:
            break
        descendants.update(additions)
    foreign = descendants - expected.keys()
    if foreign:
        raise SystemExit(f"Gateway gained unfrozen descendant pid={min(foreign)}")
leader_group = expected[leader_pid]["pgid"]
for pgid in sorted(groups - {leader_group}):
    print(pgid)
if leader_group in groups:
    print(leader_group)
PY
}

e2e_gateway_owned_status() {
  local src_dir=$1 python_bin=$2 expected_json=$3
  "$python_bin" - "$expected_json" <<'PY'
import json
import os
import subprocess
import sys

payload = json.loads(sys.argv[1])
expected = {
    item["pid"]: " ".join(item["process_start"].split())
    for item in payload["processes"]
}
result = subprocess.run(
    ["ps", "-axo", "pid=,stat=,lstart="],
    capture_output=True,
    text=True,
    check=False,
    env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
)
if result.returncode != 0:
    raise SystemExit("cannot read owned process status")
for line in result.stdout.splitlines():
    parts = line.split()
    if len(parts) < 7:
        continue
    try:
        pid = int(parts[0])
    except ValueError:
        continue
    if pid not in expected or parts[1].startswith("Z"):
        continue
    if " ".join(parts[2:7]) == expected[pid]:
        print("alive")
        break
else:
    print("exited")
PY
}

e2e_signal_gateway_owned_groups() {
  local src_dir=$1 python_bin=$2 expected_json=$3 sent_signal=$4
  local allow_reparented=$5 groups pgid remaining
  groups="$(e2e_gateway_owned_groups \
    "$src_dir" "$python_bin" "$expected_json" "$allow_reparented")" || return 1
  while IFS= read -r pgid; do
    [[ -n "$pgid" ]] || continue
    case "$sent_signal" in
      KILL) kill -9 -- "-$pgid" 2>/dev/null && continue ;;
      STOP) kill -STOP -- "-$pgid" 2>/dev/null && continue ;;
      CONT) kill -CONT -- "-$pgid" 2>/dev/null && continue ;;
      TERM) kill -- "-$pgid" 2>/dev/null && continue ;;
      *) return 1 ;;
    esac
    remaining="$(e2e_gateway_owned_groups \
      "$src_dir" "$python_bin" "$expected_json" 1)" || return 1
    if printf '%s\n' "$remaining" | grep -qx "$pgid"; then
      return 1
    fi
  done <<< "$groups"
}

e2e_freeze_gateway_owned_processes() {
  local src_dir=$1 python_bin=$2 leader_pid=$3 expected_start=${4-}
  PYTHONPATH="$src_dir${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" - \
    "$leader_pid" "$expected_start" <<'PY'
from dataclasses import asdict
import json
import sys

from personal_assistant.main import freeze_gateway_owned_process_set

expected_start = sys.argv[2] or None
owned = freeze_gateway_owned_process_set(
    int(sys.argv[1]), expected_process_start=expected_start
)
print(json.dumps(asdict(owned), sort_keys=True))
PY
}
