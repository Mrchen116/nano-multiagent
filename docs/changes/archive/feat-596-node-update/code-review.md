# Code Review: feat-596-node-update

- Review mode: initial `full`, followed by bounded `patch` reviews through the frozen product head below.
- `validated_at`: `56f1f577691db6a4046eaefca3dff1f7200c0c9f`.
- `executed_base`: `0e0c567978a89b33248cf1c342fb3311df45025b` (main at this execution).
- `effective_base`: `0e0c567978a89b33248cf1c342fb3311df45025b` (current integrated main baseline).
- `effective_through`: `56f1f577691db6a4046eaefca3dff1f7200c0c9f` (full conclusion retained by the bounded reviews).
- `delta_from`: `f5fcb1da95182a4867cd145ae59114f6a8a2e738`.
- Original full-review range start: `0b2bab6cf30ebad2fd1ee0915019913d529deea1` (`a9fc640^`); this historical implementation range is distinct from the current main baseline.
- Integrated main baseline: `0e0c56797`, merged by `40a60f9`; caller's final-sync check reports it unchanged.
- Additional repairs reviewed before and after their commit: `apps/im-server/src/server.ts`, `apps/im-server/tests/node-updates.test.ts`, `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`, `src/IM/frontend/src/i18n/zh.json`. `a9fc640..2690627` contains exactly these four reviewed patches.
- Independent reviewer did not implement the change, change source/tests/design, commit files, or operate the shared acceptance services.

## Surviving findings

```json
[]
```

No confirmed or still-plausible actionable code defect remains in the reviewed implementation and bounded repairs. Static code review passes; the completed product/evidence reconciliation is recorded in [verification.md](verification.md).

## Scope and evidence

Reviewed all 57 files in `a9fc640^..a9fc640`, including installer/build/publisher, immutable release parsing, runtime authentication, persisted authorization and cancellation, updater lock/lease/handoff, independent process switching and rollback, native DSH admission/idle/Cron seams, PA durable-work ownership, relay recovery, and Web settings/chat/state projections. Read the unit spec/design/deltas, current Gateway lifecycle and IM node/relay contracts, `SPEC.md`, and repository testing guidance.

- Owner and epoch isolation, stable click receipts and target version/hash: `apps/im-server/src/node-updates.ts:62`, `:88`, `:104`; corresponding database-seam tests in `apps/im-server/tests/node-updates.test.ts`.
- Runtime reporting stays independent of browser sessions and live WS: route authentication in `apps/im-server/src/node-updates.ts:202`; both server hooks exclude only the exact runtime-report path, while that route authenticates the durable runtime token. Independently ran `pnpm exec vitest run apps/im-server/tests/node-updates.test.ts`: **7 passed**, including the new full `createServer` hook regression and refusal of runtime credentials at the normal nodes endpoint.
- Prepared package integrity before old-process stop, cancellation/switch arbitration, renewed handoff checks, actual process/release and IM online verification: `apps/node/src/update-worker.ts:19`, `:89`, `:124`, `:138`, `:149`.
- Native idle/inbox/child coverage and durable model/workflow/knowledge continuation ownership: `packages/dsh-integration/src/update-barrier.ts:41`, `packages/dsh-integration/src/index.ts:124`, PA busy seams and existing focused tests. Native barrier tests cover true idle, Cron preservation, admission rejection and cold durable inbox; Workflow and model-setup tests add busy assertions at the native seam.
- Durable relay keys, message wait projection, current membership and epoch revalidation: `apps/im-server/src/messaging.ts:507`, `:523`, `:529`; `apps/im-server/src/node-updates.ts:155`, `:160`, `:180`.
- UI separates update actions from alias saving, derives live fields separately from drafts, and preserves current contact name precedence after the reviewed repair.
- Independently ran `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_runtime_dependency_contract.py`: **13 passed**. `git diff --check a9fc640^ a9fc640` and working-tree `git diff --check` passed.
- Independently ran `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check`: **passed**, 238 maintained Markdown sources / 64 required routes (checker inventories Git-tracked documents; these newly written reports were not yet tracked at that run).
- Reused caller's version-scoped build and focused test handoff. Did not repeat the whole CI suite or treat caller's still-running real installation/browser acceptance as already passed.

## Repairs incorporated during review

1. The caller's real E2E found that the committed server's `onSend` hook reapplied browser/gateway-principal authentication after the runtime route had correctly authenticated the persistent runtime token. The resulting 401 could prevent the updater from advancing. The reviewed exact-path exemption at `apps/im-server/src/server.ts:144` matches `preHandler`; the new `createServer` regression independently passed. **Closed in `2690627`; not closed in the original commit alone.**
2. The caller's frontend regression found that the settings nodes query could overwrite a newer contact node name in the chat header. `chat-workspace-page.tsx:485` now retains contact-name precedence and uses the owned node only as fallback; ownership still supplies the update link/state. **Closed in `2690627`.**

## Bounded patch review: `2690627d6..e5cbeec26`

Prior static conclusion: **retained**. Surviving patch findings: `[]`.

- `6d025ab81`: `.gitignore` adds the config-local updater journal, handoff and lock. These are private runtime state already prohibited from version control. No runtime behavior or reviewed safety contract changes.
- `40a60f9`: inspected the merge's affected-file set and its integration impact, without re-reviewing the already-reviewed bugfix-595 implementation. CSS changes are scoped to onboarding and membership classes, membership markup stays in its page, and the current IM spec adds the first-setup short-window scrolling scenario. None changes NodeUpdatePanel, chat, update authorization, updater/barrier, or relay persistence. Prior runtime/static evidence remains applicable.
- `e5cbeec26`: `src/IM/frontend/src/features/settings/nodes/node-update-panel.tsx:39` stops projecting an old `succeeded` result when the server says a new release is available. The existing available branch then shows the current → target version (`:50`), release notes (`:52`) and update action (`:57`). Successful current-version results, failure/retry, active cancellation and recovery precedence retain their existing behavior. The new regression at `node-update-panel.test.tsx:31` asserts the visible available heading/version and release notes after a prior success; this protects a user-visible repeated-release failure rather than an internal branch.
- Reused caller's patch-scoped **4 frontend tests passed** and **frontend build passed**; `git diff --check 2690627d6 e5cbeec26` independently passed. No repeated whole-suite or product-journey validation was performed.

## Bounded patch review: `e5cbeec26..f5fcb1da9`

Prior static conclusion: **retained**. Surviving patch findings: `[]`.

- `fcb4524b0` strengthens the existing native Knowledge test at its semantic owner. A real review child pauses at the model fixture; the public `update.prepare` returns busy before the fixture is released, then the same memory/skill facts complete. No Node/IM/DSH product code changed. Reused caller's **4 Knowledge tests passed**.
- `eba3f5cfc` corrects stale UI history at `node-update-panel.tsx:39`: when the server's current version is the recommended release, an obsolete non-success terminal result no longer masks `current`. Active state and gated recovery retain precedence (`:40`), and a fresh success remains visible. The regression at `node-update-panel.test.tsx:36` checks the visible current-version heading and absence of Retry after manual recovery. Reused caller's **5 panel tests passed** and frontend build.
- `f5fcb1da9` adds `min-w-0` to the panel's grid item (`node-update-panel.tsx:45`), allowing its existing horizontally scrollable command `pre` to shrink within the 390px layout. This is a layout containment repair; update actions and runtime semantics are unchanged. Reused successful build; independent product reviewer owns the real narrow-screen recheck.
- `ce1863e1a` adds operation guidance and its two documentation-map entries, plus the durable M1 evidence record. Guidance agrees with the reviewed staged-update, terminal-result, legacy bridge and source-deployment behavior. It does not overwrite current specs before delta merge.
- Independently ran `git diff --check e5cbeec26 f5fcb1da9`: passed. Read `M1-update/evidence.md` and checked the tail summaries of the stated final backend/frontend logs: **79 files / 294 tests**, **93 files / 863 tests**. No shared runtime was changed and no whole-suite validation was repeated.

The reviewed snapshot for that patch was `f5fcb1da9`. Formal [acceptance.md](acceptance.md) subsequently handed off R3 pass, all required scenarios, A1/A2 closure and 390/820 guide/recovery checks. Their validity is retained through the final patch below. Screenshots are preserved under `/Users/czj/Movies/Nano-Node-Update-20261014/independent-review/`; final V1 closure follows below.

## Bounded patch review: `f5fcb1da9..56f1f5776`

Prior full/static conclusions: **retained**. Surviving patch findings: `[]`.

The caller's real recording found a response-order race: `message.created` echo could insert the user bubble before POST returned; `append_optimistic` then returned early for the existing id, losing the POST's final `update_wait`. The patch removes only that early return at `chat-workspace-page.tsx:224` and retains the existing conversation guard, `mergeTimelineItems` durable-id replacement/sort (`chat-stream-reducer.ts:51`) and message projection. It restores the existing send/wait contract without adding another message or changing Node/IM behavior. Later duplicate WS `message.created` still uses the existing duplicate-id guard.

The regression at `chat-workspace.integration.test.tsx:1694` deliberately delays POST, emits the self-message echo first, resolves the POST with `update_wait: updating`, and asserts both the visible waiting label and exactly one bubble. Caller observed this test fail before the fix, then the complete workspace integration file **55 passed** and Web build passed; reused that scoped evidence. `git diff --check f5fcb1da9 56f1f5776` independently passed.

Final reviewed product snapshot: `56f1f5776`. Prior acceptance at `f5fcb1da9` remains valid for unaffected journeys. Independent acceptance R4 at `56f1f5776` now passes actual no-refresh waiting at 1280/390, refreshed persistence and one recovered reply. Its six durable `review596-r4-*.png` files were located. The final frontend rerun is **93 files / 865 passed**, independently checked from `/tmp/nano596-final-frontend-race-tests.log`.

The final continuous real-operation video is `/Users/czj/Movies/Nano-Node-Update-20261014/01-node-update-overall.mp4`. Independently checked H.264 **1280×900 / 78.480 seconds** with ffprobe and inspected its contact sheet; committed M1 evidence at `5464927b0` records the runtime operation/message/relay identities and no-edit recording boundary. V1 is closed in verification. `5464927b0` changes only the evidence document, so the reviewed product head stays `56f1f5776`. No surviving findings and no further implementation review required.
