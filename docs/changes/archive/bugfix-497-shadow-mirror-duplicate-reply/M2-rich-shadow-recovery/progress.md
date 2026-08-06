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
- Durable external live frames are discarded rather than replayed after a disconnect;
  the terminal snapshot is the sole reconnect convergence owner. Each queued business
  waiter starts its ACK budget only after obtaining wire ownership.
- Recovery orders every saga by its durable inbound position even when an earlier user
  anchor already exists, so a later fully-offline turn cannot overtake that earlier
  Agent snapshot. Steer-bubble reconcile failures wake the same retry owner.

## Automated evidence

- Focused post-review Gateway/IM regression: `171 passed` for observer, relay
  lifecycle, terminal reconciliation, recovery ordering, inbound streaming and IM
  wire liveness/ACK ownership.
- Final concurrency regression: `79 passed` across runtime event forwarding, steer
  admission and rich shadow observer behavior, including batched steers, failed bubble
  rolls and pending follower anchors.
- Full Python non-E2E suite: `2876 passed, 20 deselected`.
- Frontend full suite: `59 files passed, 556 tests passed`.
- Frontend production build passed (`tsc -b && vite build`).
- `ruff check`, `scripts/docs-check` and `git diff --check` passed.

## Baseline comparison

- The implementation baseline had eight pre-existing Feishu worker/startup timing
  failures in the full parallel Python run; none recurred in the final full run.
- The frontend baseline had two unrelated five-second timeouts. The final full
  frontend rerun passed all `556` tests.

## Remaining acceptance evidence

The exact online, fully-offline plus Gateway restart, and mid-run IM disconnect journeys
were run in an isolated real Feishu P2P listener window on 2026-08-04. All three
reconciled one rich Agent bubble with its terminal thinking, token and elapsed fields;
the mid-run case disconnected IM four seconds into a 26,031 ms run and recovered without
a refresh or plain duplicate. The nonce, Feishu message ids, IM/history cross-check and
cleanup boundary are in
[`evidence/real-feishu-acceptance-20260804.md`](evidence/real-feishu-acceptance-20260804.md).

The isolated agent initially had an explicit empty tool allowlist, so those first actual
channel rows contained no structured tool event. The final isolated test profile enabled only
the isolated `read` and `bash` tools: a real `bash` tool then appeared in the process
timeline, with one intermediate rich bubble retaining `token_usage = null` and the
in-run follower's final bubble holding the cumulative 4,453-token total. The same
runtime-only tool profile also completed the full IM-offline journey: Feishu returned the
`BUGFIX497-OFFLINE-TOOL-RESTART-20260804-1811` terminal tool result before IM recovery;
Gateway restarted while IM remained offline; the restored same-port/database IM reconciled
one terminal row with ordered thinking plus completed `bash` tool, 3,504 total tokens,
15,026 ms and kernel id `msg_18d0de01d4dbee81`. Web IM opened directly to that terminal
state, and reload retained the one bubble.

For M2-C2, the open page displayed the partial Agent row
`098717ccdade45a68f1b90cb069ebfc2` before IM was stopped. Gateway stayed online and
Feishu received the terminal reply while IM was still down. Restoring IM on the same port
and SQLite database automatically reconciled that exact row to `completed` with 1
thinking item, 16,126 total tokens, 27,037 ms and kernel id `msg_daba1196ad809592`.
The open page converged without reload and a later reload retained one bubble. The full
real-channel evidence is linked above.
