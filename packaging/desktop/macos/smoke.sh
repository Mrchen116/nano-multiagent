#!/bin/bash
set -euo pipefail
APP=$1
SHA=$2
ISO_ROOT="$(mktemp -d "${RUNNER_TEMP:-/tmp}/crewden-mac-smoke.XXXXXX")"
HOST_PID=""
cleanup_smoke() {
  if [ -n "$HOST_PID" ] && kill -0 "$HOST_PID" 2>/dev/null; then
    "$APP/Contents/MacOS/crewden-desktop" --isolated-root "$ISO_ROOT" --stop 2>/dev/null || true
    kill "$HOST_PID" 2>/dev/null || true
    wait "$HOST_PID" 2>/dev/null || true
  fi
  rm -rf "$ISO_ROOT"
}
trap cleanup_smoke EXIT
PATH="/usr/bin:/bin:/usr/sbin:/sbin" "$APP/Contents/MacOS/crewden-desktop" --isolated-root "$ISO_ROOT" --headless-host &
HOST_PID=$!
HOST_READY=0
for _ in $(seq 1 300); do
  if ! kill -0 "$HOST_PID" 2>/dev/null; then
    echo "Crewden.app headless host exited prematurely" >&2
    exit 1
  fi
  if python3 -c 'import json, pathlib, sys; p = pathlib.Path(sys.argv[1]); data = json.loads(p.read_text()) if p.is_file() else {}; raise SystemExit(0 if data.get("ready") is True and data.get("port") else 1)' "$ISO_ROOT/desktop/host-state.json" 2>/dev/null; then
    HOST_READY=1
    break
  fi
  sleep 0.5
done
test "$HOST_READY" = "1"
NODE_BIN="$ISO_ROOT/desktop/versions/$SHA/runtime/bin/node"
test "$("$NODE_BIN" -v)" = "v24.22.1"
"$NODE_BIN" "$ISO_ROOT/desktop/versions/$SHA/apps/node/lib/cli.js" --help >/dev/null
mkdir -p "$ISO_ROOT/tmp"
HOME="$ISO_ROOT" TMPDIR="$ISO_ROOT/tmp" "$NODE_BIN" "$(dirname "$0")/runtime-smoke.mjs" "$ISO_ROOT/desktop/versions/$SHA" "$ISO_ROOT/dsh-smoke"
"$APP/Contents/MacOS/crewden-desktop" --isolated-root "$ISO_ROOT" --stop
wait "$HOST_PID" || true
HOST_PID=""
