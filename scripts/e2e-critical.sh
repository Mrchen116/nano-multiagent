#!/usr/bin/env bash
# Run deterministic critical-path regressions through real IM + Node/DSH.
# Providers are local recording fixtures; no proxy or model credentials required.
# Usage: scripts/e2e-critical.sh [-k pattern] [-m "not slow"]
# macOS LaunchAgent coverage retains its explicit platform opt-in.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$REPO_ROOT/src"
cd "$REPO_ROOT"
exec python -m pytest tests/e2e/critical_paths "$@"
