#!/usr/bin/env bash
# Stop only the isolated stack owned by scripts/e2e-up.sh; retain runtime evidence.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WT_ROOT="${PWD}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) WT_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    -h|--help) echo "usage: $0 [--wt /isolated/runtime/root]"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
if [[ -f "$WT_ROOT/.gateway-config.yaml" && -f "$WT_ROOT/.gateway-state.json" ]]; then
  node "$REPO_ROOT/apps/node/lib/cli.js" stop --config "$WT_ROOT/.gateway-config.yaml"
fi
rm -f "$WT_ROOT/.gateway.pid"
if [[ -f "$WT_ROOT/.im.pid" ]]; then
  pid="$(cat "$WT_ROOT/.im.pid")"
  if kill -0 "$pid" 2>/dev/null; then
    if [[ ! -f "$WT_ROOT/.im.process-start" ]] || [[ "$(ps -p "$pid" -o lstart=)" != "$(cat "$WT_ROOT/.im.process-start")" ]]; then
      echo "Refusing to stop IM: process birth does not match this stack" >&2
      exit 1
    fi
    kill "$pid"
    for _ in $(seq 1 50); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "$pid" 2>/dev/null && [[ "$(ps -p "$pid" -o lstart=)" == "$(cat "$WT_ROOT/.im.process-start")" ]]; then kill -9 "$pid"; fi
  fi
  rm -f "$WT_ROOT/.im.pid" "$WT_ROOT/.im.process-start"
fi
if [[ -f "$WT_ROOT/.e2e-ports.env" ]]; then
  feishu_lock_dir="$(sed -n 's/^export E2E_FEISHU_LISTENER_LOCK=//p' "$WT_ROOT/.e2e-ports.env" | head -1)"
  if [[ -n "$feishu_lock_dir" && -f "$feishu_lock_dir/owner" ]] && grep -Fqx "worktree=$WT_ROOT" "$feishu_lock_dir/owner"; then
    rm -f "$feishu_lock_dir/owner"
    rmdir "$feishu_lock_dir" 2>/dev/null || true
  fi
fi
# Keep config/key together with state so failed or finished runs remain inspectable.
echo "e2e stack stopped (wt=$WT_ROOT)"
