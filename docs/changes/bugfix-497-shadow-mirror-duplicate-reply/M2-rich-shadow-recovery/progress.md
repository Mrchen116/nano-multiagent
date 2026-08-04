# M2 Progress

## Scope delivered

- The existing Gateway shadow saga SQLite now stores one presentation-ready rich
  projection per logical Agent bubble: body, ordered thinking/tools, online-compatible
  token ownership, source elapsed, terminal status and Kernel message id.
- Only terminal snapshots enter recovery. Recovery preserves user-anchor-first order,
  then reconciles rich Agent snapshots, then drains upgrade-era legacy pending output.
- IM atomically creates or replaces the same terminal Agent row and emits a complete
  replayable `message.reconciled` projection. The browser reducer upserts it by
  `message_id` without entering a running/typing state.
- External messages without provider-stable event identity skip the entire shadow path
  while leaving the external run/reply path intact and recording a contract diagnostic.

## Automated evidence

- Focused Gateway/IM regression after implementation: 85 passed for observer,
  relay lifecycle, terminal reconciliation and inbound streaming; 30 passed for the
  IM reconcile API, EventBridge and Gateway protocol contract.
- Full Python non-E2E suite: `2850 passed`.
- Frontend focused reducer/settings reruns: `44 passed` for reducer/user-stream and
  `19 passed` for the unrelated cases that timed out under the concurrent full run.
- Frontend production build passed (`tsc -b && vite build`).
- `ruff check`, `scripts/docs-check` and `git diff --check` passed.

## Baseline comparison

- The implementation baseline had eight pre-existing Feishu worker/startup timing
  failures in the full parallel Python run; the final full run has no failures.
- The frontend baseline had two unrelated five-second timeouts. The post-change full
  run had three unrelated timing/environment failures, and all three passed when
  rerun directly; changed reducer/user-stream coverage is green.

## Remaining acceptance evidence

The exact online, fully-offline plus Gateway restart, and mid-run IM disconnect journeys
still require the design runbook's exclusive real Feishu listener window. The local
machine has no isolated Feishu channel in its E2E config, while its previous credentials
were moved to the production Mac mini; this progress file does not treat API or mock
coverage as a substitute for that product journey.
