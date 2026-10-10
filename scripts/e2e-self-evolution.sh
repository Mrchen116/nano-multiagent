#!/usr/bin/env bash
# Native DSH profile and product handoff regression; not a full IM E2E substitute.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
exec pnpm test packages/dsh-integration/tests/knowledge.test.ts packages/personal-assistant/tests/knowledge.test.ts
