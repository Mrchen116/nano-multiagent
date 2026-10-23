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


## Final integrated local validation — 2026-10-24

Source tree: `acf0c72f2e799775311cca501dfb934d9174472f` (report-only HEAD `f226eb2b2b177b2d9aa4f64b54ec85431e3a488f`), with main `51072cb581a5aa6cd518ba012e3e19449f0cfecc` integrated. Commands used the pinned local Node 24.22.1 runtime. These results distinguish successful checks from environmental limitations; remote CI must establish the complete delivery gate.

- Frozen runtime install, backend build, package typecheck and `check:ios-runtime`: passed (`/tmp/bugfix644-final-install.log`, `/tmp/bugfix644-final-sync-build.log`, `/tmp/bugfix644-final-typecheck.log`, `/tmp/bugfix644-final-ios-runtime.log`).
- Python non-E2E: 65 passed / 31 deselected; ruff lint and formatting passed (`/tmp/bugfix644-final-python.log`, `/tmp/bugfix644-final-ruff.log`).
- Full Web before the final usage-envelope parameter: 104 files / 980 tests, 979 passed and one timed-out bind-confirm assertion. Its unchanged file passed both tests in a focused rerun (`/tmp/bugfix644-final-web-recheck.log`). The final usage transport/envelope regression passed both cases separately. This combined coverage is not represented as a single all-green full-suite run.
- Full backend: 126 files / 638 tests, 623 passed and 15 failed (`/tmp/bugfix644-final-backend.log`). Failures were native runtime/Node timing cases (13 explicit timeouts and two polling assertions), including one IM node-connection timeout. The actual node-connection file then passed all 5 tests alone (`/tmp/bugfix644-final-node-connection-recheck.log`). Host load was observed at 143.67 / 174.28 / 148.45 after the broad run; that supports a contention hypothesis, not a proven cause for every failure. No unrelated tests or timeouts were changed.
- Native Release archive succeeded with the unchanged native patch at the earlier source; unsigned IPA is a private build artifact in `/tmp/nano-ios-bugfix644-archive/`. Two simulator attempts stalled during installation before tests executed. No native test success is claimed locally; the required iOS CI gate remains authoritative.
- Static Round 2 and corrected delta: passed at `acf0c72f2`, with no open findings. Product Round 2 and remote CI are reported separately.

- Final frontend typecheck and production build passed (`/tmp/bugfix644-final-front-build.log`). Dependency audit exited successfully at the repository's critical threshold; it still reports 5 low, 2 moderate and 1 high finding (`/tmp/bugfix644-final-audit.log`). Those dependency versions were not changed by this unit.

## Final sync validity assessment

Final sync integrates `origin/main` `55376c1112ff870837a6ee65febf52e1f3686a9b` in merge `c2c6503f731c164e8759126c1af5b0cb91bf747a`. The increment after already-reviewed main `51072cb58` contains only skill/deployment documentation and the CI iOS path filter (now also used on main pushes). No runtime, IM, Web, native source, tests or current behavior spec changed. PR iOS detection retains the full-branch diff; this unit's Swift changes still require the native job. Static review, corrected delta, final builds and real product source remain valid for their stated scope. Canonical spec merging and archive path changes are documentary and will be checked separately.


## Product I6 correction — unknown discovery count

Round 2 independently reproduced a no-snapshot `explicit_denylist=[]` profile displaying `0 selected`. The selector now receives whether discovery was actually confirmed, so an unknown discovered set cannot produce a numeric enabled count. Explicit configured names remain visible; a confirmed empty result still displays zero. This is a local read presentation change, with no API, persistence, save or recovery changes.

- Meaningful red: the real page test expected an unconfirmed count and received `0 selected` (`/tmp/bugfix644-i6-red.log`).
- Green: both affected files, 23 tests passed, including empty/nonempty denylist before confirmation and confirmed empty discovery after recovery (`/tmp/bugfix644-i6-green.log`). Frontend TypeScript build passed (`/tmp/bugfix644-i6-typecheck.log`).
- Independent revalidation is restricted to I6 and the related unknown/confirmed-empty boundaries. Round 2's other real journeys and static source scopes retain their stated evidence; this patch does not invalidate channel, pending operation, PA, preview or backend coverage.
