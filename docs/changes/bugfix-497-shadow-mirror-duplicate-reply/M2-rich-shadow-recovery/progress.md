# M2 Progress

## Scope delivered

- The existing Gateway shadow saga SQLite now stores one presentation-ready rich
  projection per logical Agent bubble: body, ordered thinking/tools, online-compatible
  token ownership, source elapsed, terminal status and Kernel message id.
- Only terminal snapshots enter recovery. Recovery preserves user-anchor-first order,
  interleaves each fully offline turn's Agent snapshots before the next user anchor,
  then drains upgrade-era legacy pending output.
- IM atomically creates or replaces the same terminal Agent row and emits a complete
  replayable `message.reconciled` projection. The browser reducer upserts it by
  `message_id` without entering a running/typing state.
- External messages without provider-stable event identity skip the entire shadow path
  while leaving the external run/reply path intact and recording a contract diagnostic.
- Normal and abnormal terminal paths now share the ordered ACK/reconcile contract.
  Failed immediate reconcile wakes one retry owner on the current connection; detached
  completion captures terminal facts before the run context can be discarded.
- IM business send/ACK ownership fails closed within one second on a half-open socket,
  so the external reply path does not wait for heartbeat recovery before switching to
  durable offline convergence.

## Automated evidence

- Focused post-review Gateway/IM regression: `163 passed` for observer, relay
  lifecycle, terminal reconciliation, recovery ordering, inbound streaming and IM
  wire liveness/ACK ownership.
- Full Python non-E2E suite: `2860 passed`; the two baseline Feishu worker-process
  timing cases failed in the loaded full run and both passed on direct rerun.
- Frontend full suite: `59 files passed, 556 tests passed`.
- Frontend production build passed (`tsc -b && vite build`).
- `ruff check`, `scripts/docs-check` and `git diff --check` passed.

## Baseline comparison

- The implementation baseline had eight pre-existing Feishu worker/startup timing
  failures in the full parallel Python run; the final full run has no failures.
- The frontend baseline had two unrelated five-second timeouts. The final full
  frontend rerun passed all `556` tests.

## Remaining acceptance evidence

The exact online, fully-offline plus Gateway restart, and mid-run IM disconnect journeys
still require the design runbook's exclusive real Feishu listener window. The local
machine has no isolated Feishu channel in its E2E config, while its previous credentials
were moved to the production Mac mini; this progress file does not treat API or mock
coverage as a substitute for that product journey.
