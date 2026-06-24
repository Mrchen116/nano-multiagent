#!/usr/bin/env bash
# scripts/e2e-critical.sh — one command to run the critical-path real-LLM e2e suite.
#
# Starts a real IM + real Gateway process stack (via the session fixture, which
# subprocess-calls scripts/e2e-up.sh into a pytest tmp dir) and drives 真正的用户
# 旅程 black-box through IM's public HTTP + WebSocket interface against a real LLM.
#
# feat-421-M1. Design: docs/changes/feat-421-critical-path-e2e-suite/design.md
# Catalog:      docs/e2e-critical-paths.md
#
# Prerequisites (else the suite cleanly SKIPS, never errors):
#   - local LLM proxy reachable at http://127.0.0.1:4000/health
#   - ~/.nano-assistant/config.yaml exists and includes the llm: section
#
# Usage:
#   scripts/e2e-critical.sh                 # run all critical paths
#   scripts/e2e-critical.sh -m "not slow"   # skip time-driven (cron/heartbeat) paths
#   scripts/e2e-critical.sh -k tool_call    # run one path
#   (any extra args are forwarded to pytest)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Gate env: the suite's fixture also re-checks this and skips if unset, but we
# set it here so the one command "just runs" without the caller exporting it.
export NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1
export PYTHONPATH="$REPO_ROOT/src"

cd "$REPO_ROOT"
exec python -m pytest tests/e2e/critical_paths "$@"
