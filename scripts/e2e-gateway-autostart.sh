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
  node "$REPO_ROOT/apps/node/lib/cli.js" stop --config "$AUTOSTART_CONFIG" >/dev/null 2>&1
  [[ -n "${PLIST:-}" ]] && rm -f "$PLIST"
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

node "$REPO_ROOT/apps/node/lib/cli.js" stop --config "$AUTOSTART_CONFIG"
rm -f "$AUTOSTART_ROOT/.gateway.pid"

AUTOSTART_CONFIG="$AUTOSTART_CONFIG" "$AUTOSTART_PYTHON" - <<'PY'
import os
from pathlib import Path

import yaml

path = Path(os.environ["AUTOSTART_CONFIG"])
payload = yaml.safe_load(path.read_text(encoding="utf-8"))
payload.setdefault("gateway", {})["autostart"] = True
path.write_text(
    yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
)
PY

START_OUTPUT=$(node "$REPO_ROOT/apps/node/lib/cli.js" start --config "$AUTOSTART_CONFIG" --im-service-url "$IM_URL")
grep -Fq "Autostart: enabled" <<<"$START_OUTPUT"
LABEL=$(node --input-type=module - "$REPO_ROOT/apps/node/lib/lifecycle.js" "$AUTOSTART_CONFIG" <<'JS'
const lifecycle=await import(process.argv[2]);console.log(lifecycle.gatewayLabel(process.argv[3]));
JS
)
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl print "gui/$(id -u)/$LABEL" >/dev/null
FIRST_PID=$(wait_for_new_gateway)
"$AUTOSTART_PYTHON" - "$PLIST" "$AUTOSTART_CONFIG" "$REPO_ROOT" "$(command -v node)" <<'PYCHECK'
import plistlib,sys
from pathlib import Path
payload=plistlib.loads(Path(sys.argv[1]).read_bytes())
args=payload['ProgramArguments']
assert payload['KeepAlive'] is True
assert Path(args[0]).resolve()==Path(sys.argv[4]).resolve()
assert args[1]==str(Path(sys.argv[3])/'apps/node/lib/cli.js')
assert '--foreground' in args
assert args[args.index('--config')+1]==sys.argv[2]
assert '--im-service-url' not in args
assert payload['WorkingDirectory']==sys.argv[3]
PYCHECK
assert_node_online "$IM_URL" "$NODE_ID"

# A crash must produce a new process while the same job remains loaded.
kill -9 "$FIRST_PID"
SECOND_PID=$(wait_for_new_gateway "$FIRST_PID")
launchctl print "gui/$(id -u)/$LABEL" >/dev/null
assert_node_online "$IM_URL" "$NODE_ID"

# Manual stop pauses this login but preserves the stable definition.
cd "$REPO_ROOT"
node "$REPO_ROOT/apps/node/lib/cli.js" stop \
  --config "$AUTOSTART_CONFIG" >/dev/null
launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 \
  && { echo "LaunchAgent reloaded after manual stop" >&2; exit 1; }
[[ -f "$PLIST" ]]

# Re-bootstrap the stable plist to model the next login, then disable permanently.
launchctl bootstrap "gui/$(id -u)" "$PLIST"
THIRD_PID=$(wait_for_new_gateway "$SECOND_PID")
assert_node_online "$IM_URL" "$NODE_ID"
node "$REPO_ROOT/apps/node/lib/cli.js" stop \
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

DISABLED_OUTPUT=$(node "$REPO_ROOT/apps/node/lib/cli.js" start --config "$AUTOSTART_CONFIG")
grep -Fq "Autostart: disabled" <<<"$DISABLED_OUTPUT"
[[ ! -f "$PLIST" ]]
launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 \
  && { echo "disabled LaunchAgent remained loaded" >&2; exit 1; }
node "$REPO_ROOT/apps/node/lib/cli.js" stop \
  --config "$AUTOSTART_CONFIG" >/dev/null

echo "GATEWAY AUTOSTART E2E PASS first=$FIRST_PID crash_recovery=$SECOND_PID login=$THIRD_PID"
