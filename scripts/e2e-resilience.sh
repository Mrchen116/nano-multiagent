#!/usr/bin/env bash
# Real TypeScript IM + Node recovery with the same durable identity and data.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WT_ROOT=""
MAIN_CFG="$REPO_ROOT/config/e2e/gateway.yaml"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) WT_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    --main-config) MAIN_CFG="$2"; shift 2 ;;
    -h|--help) echo "usage: $0 [--wt directory] [--main-config file]"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$WT_ROOT" ]] || WT_ROOT="$(mktemp -d)"
cleanup() { "$SCRIPT_DIR/e2e-down.sh" --wt "$WT_ROOT"; }
trap cleanup EXIT
"$SCRIPT_DIR/e2e-up.sh" --wt "$WT_ROOT" --main-config "$MAIN_CFG"
source "$WT_ROOT/.e2e-ports.env"
CFG="$WT_ROOT/.gateway-config.yaml"
stop_im() {
  local pid
  pid="$(cat "$WT_ROOT/.im.pid")"
  [[ "$(ps -p "$pid" -o lstart=)" == "$(cat "$WT_ROOT/.im.process-start")" ]] || return 1
  kill "$pid"
  for _ in $(seq 1 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
  ! kill -0 "$pid" 2>/dev/null
}
start_im() {
  IM_PUBLIC_URL="$IM_URL" IM_DB_PATH="$WT_ROOT/data/im_service.sqlite3" IM_UPLOAD_DIR="$WT_ROOT/data/uploads" IM_PUBLIC_MODE=0 \
    node --input-type=module - "$REPO_ROOT/apps/im-server/lib/main.js" "$IM_PORT" "$WT_ROOT" <<'JS'
import {spawn,execFileSync} from 'node:child_process';
import {openSync,closeSync,writeFileSync} from 'node:fs';
const root=process.argv[4],log=openSync(root+'/.im.log','a');
const child=spawn(process.execPath,[process.argv[2],'serve','--host','127.0.0.1','--port',process.argv[3]],{cwd:root,env:process.env,detached:true,stdio:['ignore',log,log]});
writeFileSync(root+'/.im.pid',String(child.pid));
writeFileSync(root+'/.im.process-start',execFileSync('ps',['-p',String(child.pid),'-o','lstart=']));
closeSync(log);child.unref();
JS
}
online() {
  python - "$IM_URL" "$NODE_ID" <<'PY'
import sys,time,httpx
with httpx.Client(base_url=sys.argv[1],trust_env=False,timeout=3) as client:
    for _ in range(90):
        try:
            login=client.post('/im/v1/auth/login',json={'username':'nano','password':'nano1234'})
            login.raise_for_status()
            pair=login.json()
            nodes=client.get('/im/v1/nodes',headers={'Authorization':'Bearer '+pair['access_token']})
            nodes.raise_for_status()
            if any(n['node_id']==sys.argv[2] and n['owner_id']==pair['user']['owner_id'] and n['status']=='online' for n in nodes.json()):
                break
        except httpx.HTTPError:
            pass
        time.sleep(.5)
    else:
        raise SystemExit('Node did not recover online')
PY
}
echo "Scenario A: IM restart"
NODE_PID="$(cat "$WT_ROOT/.gateway.pid")"
stop_im
sleep 2
kill -0 "$NODE_PID"
start_im
online
kill -0 "$NODE_PID"
echo "Scenario B: bound Node starts before IM"
node "$REPO_ROOT/apps/node/lib/cli.js" stop --config "$CFG"
stop_im
node "$REPO_ROOT/apps/node/lib/cli.js" start --config "$CFG"
node -e 'const fs=require("fs");fs.writeFileSync(process.argv[2],String(JSON.parse(fs.readFileSync(process.argv[1])).pid))' "$WT_ROOT/.gateway-state.json" "$WT_ROOT/.gateway.pid"
sleep 2
kill -0 "$(cat "$WT_ROOT/.gateway.pid")"
start_im
online
echo "RESILIENCE E2E PASS"
