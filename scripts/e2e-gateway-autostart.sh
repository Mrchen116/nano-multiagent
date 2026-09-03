#!/usr/bin/env bash
# Exercise the macOS Gateway LaunchAgent against an isolated IM and config.

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Gateway autostart e2e requires macOS" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AUTOSTART_ROOT="${PWD}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) AUTOSTART_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    -h|--help) echo "usage: $0 [--wt /isolated/runtime/root]"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

AUTOSTART_PYTHON="${NANO_MULTIAGENT_E2E_PYTHON:-$(command -v python)}"
AUTOSTART_CONFIG="$AUTOSTART_ROOT/.gateway-config.yaml"
AUTOSTART_STATE="$AUTOSTART_ROOT/.gateway-state.json"
export PATH="$(dirname "$AUTOSTART_PYTHON"):$PATH"

cleanup() {
  trap - EXIT INT TERM
  set +e
  if [[ -f "$AUTOSTART_CONFIG" ]]; then
    PYTHONPATH="$REPO_ROOT/src" "$AUTOSTART_PYTHON" \
      -m personal_assistant.main stop --config "$AUTOSTART_CONFIG" \
      >/dev/null 2>&1
    PYTHONPATH="$REPO_ROOT/src" "$AUTOSTART_PYTHON" -c \
      'from personal_assistant.gateway.macos_launch_agent import permanently_remove; import sys; permanently_remove(config_path=sys.argv[1])' \
      "$AUTOSTART_CONFIG" >/dev/null 2>&1
  fi
  "$SCRIPT_DIR/e2e-down.sh" --wt "$AUTOSTART_ROOT" >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

wait_for_new_gateway() {
  local old_pid="${1:-0}"
  local candidate=""
  for _ in $(seq 1 160); do
    if [[ -f "$AUTOSTART_STATE" ]]; then
      candidate=$("$AUTOSTART_PYTHON" -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["pid"])' \
        "$AUTOSTART_STATE" 2>/dev/null || true)
      if [[ "$candidate" =~ ^[0-9]+$ ]] && [[ "$candidate" != "$old_pid" ]] \
        && kill -0 "$candidate" 2>/dev/null; then
        echo "$candidate"
        return 0
      fi
    fi
    sleep 0.25
  done
  echo "Gateway did not publish a replacement live state" >&2
  return 1
}

assert_node_online() {
  local im_url="$1"
  local node_id="$2"
  local token=""
  token=$(curl -fsS -X POST "$im_url/im/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"username":"nano","password":"nano1234"}' \
    | "$AUTOSTART_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  for _ in $(seq 1 80); do
    if curl -fsS "$im_url/im/v1/nodes" -H "Authorization: Bearer $token" \
      | "$AUTOSTART_PYTHON" -c \
        'import json,sys; expected=sys.argv[1]; nodes=json.load(sys.stdin); raise SystemExit(0 if any(n.get("node_id") == expected and n.get("status") == "online" for n in nodes) else 1)' \
        "$node_id"; then
      return 0
    fi
    sleep 0.25
  done
  echo "isolated IM never reported node $node_id online" >&2
  return 1
}

"$SCRIPT_DIR/e2e-up.sh" --wt "$AUTOSTART_ROOT" >/dev/null
IM_URL=$(sed -n 's/^export IM_URL=//p' "$AUTOSTART_ROOT/.e2e-ports.env")
NODE_ID=$(sed -n 's/^export NODE_ID=//p' "$AUTOSTART_ROOT/.e2e-ports.env")

# Replace e2e-up's foreground Gateway with the product's background entry.
SEED_PID=$(cat "$AUTOSTART_ROOT/.gateway.pid")
kill "$SEED_PID"
for _ in $(seq 1 80); do
  kill -0 "$SEED_PID" 2>/dev/null || break
  sleep 0.25
done
kill -0 "$SEED_PID" 2>/dev/null && { echo "seed Gateway did not stop" >&2; exit 1; }
rm -f "$AUTOSTART_ROOT/.gateway.pid"

AUTOSTART_CONFIG="$AUTOSTART_CONFIG" "$AUTOSTART_PYTHON" - <<'PY'
import os
from pathlib import Path

import yaml

path = Path(os.environ["AUTOSTART_CONFIG"])
payload = yaml.safe_load(path.read_text(encoding="utf-8"))
payload["gateway"] = {
    "autostart": True,
    "environment": {"NANO_MULTIAGENT_AUTO_BIND": "0"},
}
path.write_text(
    yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
)
PY

START_OUTPUT=$(cd "$REPO_ROOT" && PYTHONPATH=src "$AUTOSTART_PYTHON" \
  -m personal_assistant.main --config "$AUTOSTART_CONFIG" \
  --im-service-url "$IM_URL" --auto-bind)
grep -Fq "Autostart:       enabled" <<<"$START_OUTPUT"

LABEL=$(cd "$REPO_ROOT" && PYTHONPATH=src "$AUTOSTART_PYTHON" -c \
  'from personal_assistant.gateway.macos_launch_agent import launch_agent_label; import sys; print(launch_agent_label(sys.argv[1]))' \
  "$AUTOSTART_CONFIG")
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl print "gui/$(id -u)/$LABEL" >/dev/null
FIRST_PID=$(wait_for_new_gateway)

"$AUTOSTART_PYTHON" - "$PLIST" "$AUTOSTART_CONFIG" "$REPO_ROOT" "$AUTOSTART_PYTHON" "$IM_URL" <<'PY'
import plistlib
import sys
from pathlib import Path

plist_path = Path(sys.argv[1])
config_path = Path(sys.argv[2])
repo_root = Path(sys.argv[3])
python = Path(sys.argv[4])
transient_url = sys.argv[5]
payload = plistlib.loads(plist_path.read_bytes())
arguments = payload["ProgramArguments"]
assert payload["KeepAlive"] is True
assert payload["Program"] == str(python.resolve())
assert payload["WorkingDirectory"] == str(repo_root.resolve())
assert payload["EnvironmentVariables"] == {"PYTHONPATH": str((repo_root / "src").resolve())}
assert str(config_path.resolve()) in arguments
assert "--auto-bind" not in arguments
assert transient_url not in arguments
PY
assert_node_online "$IM_URL" "$NODE_ID"

# A crash must produce a new process while the same job remains loaded.
kill -9 "$FIRST_PID"
SECOND_PID=$(wait_for_new_gateway "$FIRST_PID")
launchctl print "gui/$(id -u)/$LABEL" >/dev/null
assert_node_online "$IM_URL" "$NODE_ID"

# Manual stop pauses this login but preserves the stable definition.
cd "$REPO_ROOT"
PYTHONPATH=src "$AUTOSTART_PYTHON" -m personal_assistant.main stop \
  --config "$AUTOSTART_CONFIG" >/dev/null
launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 \
  && { echo "LaunchAgent reloaded after manual stop" >&2; exit 1; }
[[ -f "$PLIST" ]]

# Re-bootstrap the stable plist to model the next login, then disable permanently.
launchctl bootstrap "gui/$(id -u)" "$PLIST"
THIRD_PID=$(wait_for_new_gateway "$SECOND_PID")
assert_node_online "$IM_URL" "$NODE_ID"
PYTHONPATH=src "$AUTOSTART_PYTHON" -m personal_assistant.main stop \
  --config "$AUTOSTART_CONFIG" >/dev/null

AUTOSTART_CONFIG="$AUTOSTART_CONFIG" "$AUTOSTART_PYTHON" - <<'PY'
import os
from pathlib import Path

import yaml

path = Path(os.environ["AUTOSTART_CONFIG"])
payload = yaml.safe_load(path.read_text(encoding="utf-8"))
payload["gateway"]["autostart"] = False
path.write_text(
    yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
)
PY

DISABLED_OUTPUT=$(PYTHONPATH=src "$AUTOSTART_PYTHON" \
  -m personal_assistant.main --config "$AUTOSTART_CONFIG")
grep -Fq "Autostart:       disabled" <<<"$DISABLED_OUTPUT"
[[ ! -f "$PLIST" ]]
launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 \
  && { echo "disabled LaunchAgent remained loaded" >&2; exit 1; }
PYTHONPATH=src "$AUTOSTART_PYTHON" -m personal_assistant.main stop \
  --config "$AUTOSTART_CONFIG" >/dev/null

echo "GATEWAY AUTOSTART E2E PASS first=$FIRST_PID crash_recovery=$SECOND_PID login=$THIRD_PID"
