# M1 implementation evidence

- Baseline: 2e9c83df9 (code baseline 499774a56 plus this unit's approved documents).
- Implemented concrete ShadowReplyPublisher; composition shares the existing saga store explicitly. MessageDelivery retains frozen projection and ledger. Sync passes typed saga/output/snapshot instead of itself; removed unused _project_images.
- Tests: keep all existing shadow behavior assertions. Rewrite shared fixture construction only; existing tests own HTTP payloads, identity, rotated token, retry and frozen-image admission ordering. No parallel implementation-mirroring suite added.
- Baseline narrow suite: 43 passed before refactor.
- Implemented narrow suite plus composition: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_shadow_sync.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_shadow_auth.py tests/integration/test_shadow_reply_images.py tests/unit/personal_assistant/test_gateway_build_runtime.py` → 54 passed (5.55s).
- Ruff affected files and git diff --check passed. Full CI-equivalent checks and independent gates follow on the frozen implementation commit.

## Full CI-equivalent checks at a3c6e819c

- `./scripts/docs-check`: passed (242 maintained Markdown sources, 73 routes).
- `ruff check .`, `ruff format --check .`: passed (1086 formatted files).
- `pytest -m 'not e2e' -n 4 --dist worksteal tests/unit/agent tests/unit/personal_assistant`: 1976 passed, 82.47s; `/tmp/refactor570-tests-agent-pa.log`.
- `pytest -m 'not e2e' -n 4 --dist worksteal --ignore=tests/unit/agent --ignore=tests/unit/personal_assistant`: 2045 passed, 153.66s; `/tmp/refactor570-tests-remaining.log`.
- Frontend `npm ci` and `npm audit --audit-level=critical`: passed. Initial full Vitest run during parallel Python execution: 769 passed, one `findByRole(Core Planner)` timeout in unchanged agents-list-page.test.tsx. No frontend diff. Isolated file: 4/4 passed; full rerun after Python completed: 770/770 passed, 35.87s (`/tmp/refactor570-frontend-focused.log`, `/tmp/refactor570-frontend-tests-rerun.log`). Observed intermittent failure; load sensitivity is a hypothesis, not a proved root cause. No unrelated test/product changes made.

## Product environment

Isolated IM/Gateway at `/tmp/refactor-570-e2e`, initial IM port 60291. Gateway source uses this worktree. Temporary provider fixture follows the real ChannelAdapter callback contract and retains real kernel, HTTP, saga store and delivery composition. Driver setup corrected missing `image_account_id` before reviewer handoff; no product code change. Product reviewer independently drives its own chats via fixture and checks real IM REST history. Production Feishu is not exercised or modified.
