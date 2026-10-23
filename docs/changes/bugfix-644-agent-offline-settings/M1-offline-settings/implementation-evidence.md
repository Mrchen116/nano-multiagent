# M1 implementation evidence

Implementation baseline: `1ef49808ffd2618c275b6e38683f93f74ff8455d`; backend commit `96531637748af069f999479e725277237d2f80f1`, channels commit `f04730f780475427582cd7b94c62f00158677925`. Web settings and native error classification are included with this report's commit.

## Behavior and focused validation

- IM settings reads preserve committed configuration and finite last-success display snapshots. New offline writes reject before side effects; accepted operations retain recovery. Backend route evidence: [backend-evidence.md](backend-evidence.md).
- Web uses the settings response and independent section reads. Disconnection cancels stale requests, disables writes and preserves drafts. Current reads are required before recovery unlocks; version conflicts retain the existing discard-and-reedit interaction. Unknown sections are distinct from successful empty results. Features, Skills, tools, model/reasoning, PA controls and channel dialogs retain the existing UI.
- Native shared writes classify `agent_node_offline` separately from version conflicts; online response shapes are unchanged.
- Meaningful frontend red: old behavior left configuration input enabled after offline read (`/tmp/bugfix644-frontend-red.log`). Focused green: 9 agent-edit + 8 PA tests (`/tmp/bugfix644-final-narrow.log`); 25 detail tests (`/tmp/bugfix644-existing-tests.log`); channel worker reports 23 existing lifecycle tests and 5 new offline cases passed. Assertions cover stale response cancellation, stream recovery, drafts, config version conflict, pending confirmation and inherited null reasoning.

## Real browser self-check, 2026-10-23

Actual isolated IM + Node + DSH at IM port 59021 / Vite port 59020, private runtime `/tmp/nano-bugfix644-impl.ltEdBj`; dedicated Feishu identity verified by `e2e-up.sh --feishu`. No production service or external message used.

Edited display name to `Offline draft 644`, selected `codexOAuth:gpt-6.1-sol` / `high`, stopped only this Node using its explicit temporary config, and asserted the original name/model/effort controls retained the draft while disabled. Restarted the same Node without recreating IM data; asserted name/model remained unchanged and editing unlocked after current reads. No save was sent. An earlier developer-server hot reload interrupted the draft trial; only the repeat without file edits supplies this evidence.

- [Desktop offline](evidence/bugfix644-offline-desktop.png), [mobile offline](evidence/bugfix644-offline-mobile.png), [tablet offline](evidence/bugfix644-offline-tablet.png), [tablet recovered](evidence/bugfix644-recovered-tablet.png).
- Compared the actual existing cards, field order, navigation and model controls against the revised R3 prototype. The offline notice and disabled states are the relevant additions. Full R1–R11 product acceptance remains a separate independent gate.

## Broader checks at handoff

Backend/frontend build passed. Python non-E2E: 65 passed / 31 deselected; ruff check and format passed. Full Web: 969 passed / 4 failed across 104 files; the failures are being investigated with a narrow rerun, so this is not a full-suite pass. Backend full suite, native tests/archive and final docs/type checks remain to be recorded before delivery.

## Independent review corrections — 2026-10-24

The first static and product review found real gaps; their original reports remain intact. This patch preserves `enabled: null` in historical Skill projections, separates content-read failures from node presence, retains missing configured catalog entries with an explicit correction requirement, and keeps accepted pending operations visible after reopening offline. Saved fallback lists remain expandable in read-only mode. Bodyless channel actions now use the existing `authFetch` body-aware headers, and offline channel guidance matches the write gate. The settings capability guard accepts the same optional `features` payload as the existing capabilities API.

- W1 backend regression: the new optional-features test failed before the correction; all 17 `agent-settings` tests passed afterward (`/tmp/bugfix644-review-w1-red.log`, `...-green.log`).
- Frontend regressions: four failures for pending reopen, collapsed fallback reading, missing catalog entries, and unconfirmed inherited Skills; the API bodyless request regression also failed before correction (`/tmp/bugfix644-review-front-red.log`, `...-api-red.log`).
- Related frontend validation: 4 files / 67 tests passed, including independent prompt/heartbeat capture retention after online read failure and retained usage history (`/tmp/bugfix644-review-front-green3.log`). Production frontend build passed (`/tmp/bugfix644-review-front-build.log`). Subsequent notice visibility/retry markup is included in the next final validation.
- A serial full backend run on the pre-sync revision was interrupted for final-main integration; it is not a passing gate. It had reported failures in workspace-tools, knowledge, native-human-source, and realtime-window. Earlier broad runs were also affected by severe host load; final revision checks must establish their actual status.
- No merge or deployment to production has been performed. Independent closure review and missing real-fixture coverage are still required.
