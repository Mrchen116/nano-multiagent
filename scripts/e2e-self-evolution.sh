#!/usr/bin/env bash
# Deterministic real-stack acceptance for private self-evolution reviews.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GIT_COMMON_DIR="$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)"
COMMON_ROOT="$(cd "$GIT_COMMON_DIR/.." && pwd)"
RUNTIME_ROOT="$(mktemp -d "$REPO_ROOT/.e2e-self-evolution.XXXXXX")"

cleanup() {
  local status=$?
  trap - EXIT
  case "$RUNTIME_ROOT" in
    "$REPO_ROOT"/.e2e-self-evolution.*) rm -rf -- "$RUNTIME_ROOT" ;;
    *) echo "refusing to remove unexpected runtime path: $RUNTIME_ROOT" >&2; status=1 ;;
  esac
  if [[ -e "$RUNTIME_ROOT" ]]; then
    echo "self-evolution E2E runtime cleanup failed: $RUNTIME_ROOT" >&2
    status=1
  else
    echo "self-evolution E2E runtime cleaned: $RUNTIME_ROOT"
  fi
  exit "$status"
}
trap cleanup EXIT

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
elif [[ -x "$COMMON_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$COMMON_ROOT/.venv/bin/python"
else
  PYTHON_BIN=python
fi

echo "self-evolution E2E runtime: $RUNTIME_ROOT"
cd "$REPO_ROOT"
PYTHONPATH=src "$PYTHON_BIN" -m pytest -q -m e2e \
  --basetemp "$RUNTIME_ROOT" \
  tests/e2e/critical_paths/test_self_evolution_visibility_critical_path.py \
  tests/e2e/critical_paths/test_self_evolution_skill_activation_critical_path.py
