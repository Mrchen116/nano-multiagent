# M2 headed browser and runtime evidence

## Environment

- Date: 2026-07-15 (Asia/Shanghai)
- Entry: `http://127.0.0.1:56189/settings/agents/default-agent` via the production frontend served by the real IM process.
- Runtime: `scripts/e2e-up.sh`, isolated node `wt-feat-464-M2-47896`, headed Chrome, 1440×1000 viewport.
- Isolation: worktree-local SQLite, Gateway config/workspaces, credential key and encrypted manifest cache. `e2e-down.sh` removed both PIDs plus `channel-credentials-v1.pem` and `channel-manifest-v1.json`; no service process remained.

## Prototype anchor reconciliation

| Anchor | Real journey and durable evidence | Result |
|---|---|---|
| `#channel-pending` | Pause Gateway, project the node offline, create a channel through the real wizard. The card says “Waiting for node / Configuration saved / Applies automatically when the node returns”; [screenshot](output/playwright/channel-pending-offline-create.png). | PASS |
| `#channel-actions` | Bootstrapped legacy Feishu channel reached real Connected state and exposed Edit/Reconnect/Disable/Delete; [screenshot](output/playwright/channel-actions-connected.png). | PASS |
| `#channel-disabling` | Disable confirmation persisted desired state while the node was paused; card remained Disabling instead of claiming runtime stop; [confirmation](output/playwright/channel-disable-confirm.png), [state](output/playwright/channel-disabling-offline.png). | PASS |
| `#channel-disabled` | Resume delivered the unchanged manifest, worker stopped, observed disabled arrived, credentials remained available for re-enable; [screenshot](output/playwright/channel-disabled.png), [re-enable connecting](output/playwright/channel-reenabled-connecting.png). | PASS |
| `#channel-deleting` | Offline delete retained a receipt across full reload; [pending](output/playwright/channel-deleting-offline.png), [after reload](output/playwright/channel-deleting-after-reload.png). A controlled cache-commit failure exposed its reason and Retry action; [failed/retry](output/playwright/channel-deleting-failed-retry.png). Retry called the real action endpoint with the same revision and converged to empty. | PASS |
| `#channel-reconnecting` | Real Reconnect action returned the pre-command snapshot; headed QA found and fixed the flash-back defect. The stable action projection is visible in [screenshot](output/playwright/channel-reconnecting.png), followed by a fresh Connected status. | PASS |
| `#channel-failed` | A real invalid Feishu application caused the worker to exit and report `runtime_start_failed`; headed QA found and fixed `sync_state=failed` being masked as Connecting. Final actionable state is in [screenshot](output/playwright/channel-failed-actionable.png). | PASS |

The existing IM card/token system was intentionally retained for the reference's may-adapt icon, shadow, and transition details. No internal manifest/channel revision is visible, and Web IM is not presented as a managed external provider.

## Offline create-delete and removal proof

The browser created `ch_ef5f1ead8df14a4587c0ebd8c55532de` while the Gateway process was paused, then deleted it before the first manifest could be consumed. SQLite showed `deleted_channel_revision=1`, `deletion_manifest_revision=9`, `apply_state=pending`, and zero active rows while the [removal card](output/playwright/channel-offline-create-delete-before-sync.png) remained visible. After resuming the same Gateway, the receipt became `applied`, head/applied revisions both became 9, and the UI entered [empty only after that result](output/playwright/channel-offline-create-delete-converged-empty.png).

For the retry journey, the controlled failure set the persisted head to applied revision 8 and receipt revision 9 to `failed/cache_commit_failed`. Clicking Retry produced:

```text
POST /im/v1/agents/default-agent/channel-removals/ch_ef5f1ead8df14a4587c0ebd8c55532de/actions/retry -> 200
receipt.apply_state = applied
manifest_revision = applied_manifest_revision = 9
```

Permanent integration coverage provides the destructive-path proof not safe to synthesize in the UI journey: runtime stop and encrypted-cache commit both gate removal success, same-revision retry is accepted, newer revision does not consume older token ACK, retention reaches a terminal outcome, and conversations/history are not cascade-deleted.

## Security, network, console, and cleanup

- The live credential key and encrypted manifest cache were both mode 0600. The encrypted manifest contained no `appSecret`, `app_secret`, or browser test credential value.
- Network evidence included create 201, update 200, reconnect 200, delete 200, removal retry 200, and repeated GET 200 projections.
- Console errors were limited to the expected capabilities 503 while the Gateway was deliberately paused/offline. No lifecycle request failed unexpectedly after the node resumed.
- The final real-stack state was zero active channels, zero nonterminal removals, and manifest head/applied revision 9.
- Cleanup proof: `.im.pid`, `.gateway.pid`, `channel-credentials-v1.pem`, and `channel-manifest-v1.json` were absent after `e2e-down.sh`; both service PIDs were gone.

## Regression gates

- Frontend: `65 files / 612 tests passed`; production `tsc -b && vite build` passed (443 modules).
- M2-focused backend: `123 passed`.
- Ruff: `All checks passed`.
- Full non-e2e first pass: `3379 passed, 1 skipped, 20 deselected`; its only three failures were stale capability golden dictionaries after `channel_bootstrap` became negotiated. The three expectations were updated and the focused rerun passed; the final post-rebase full run is recorded in `progress.md`.
