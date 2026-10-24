# Verification Report: refactor-655

> Validation snapshot: `063b0742f → 0d3a762fed52fe14a93fcb03ba4de72532a5887a`

## Round 1 metadata

- reviewer: independent `/root/review655`; did not implement this change.
- review_round: 1
- verification_mode: full, including corrected-delta reconciliation.
- review_mode: full static code review of the complete `063b0742f..0d3a762fe` implementation diff (41 files), related callers and current contracts.
- validated_at: `0d3a762fed52fe14a93fcb03ba4de72532a5887a`
- executed_base: `063b0742f`
- branch/worktree: `codex/refactor-655-work-recovery`, `/Users/czj/.codex/worktrees/refactor-655-work-recovery/nano-multiagent`.
- effective_base: `648e263d2373985a088cce55222901ef7c420cb5` assessed for retention in Round 2; final merge tree SHA remains caller-owned.
- effective_through: frozen implementation `0d3a762fe` plus the reviewed main increment and two non-semantic delta-link corrections; no claim that execution occurred on a not-yet-created integration commit.
- requires_full_verification: false; Round 1 full review retained, Round 2 closes its evidence items and checks the bounded main/document delta.

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | Scoped implementation and M1 product/migration evidence complete; remaining integration/PR/remote-CI closeout is caller-owned |
| Correctness | No actionable static implementation defect found; focused native, token, persistence and client evidence supports the mapped behavior |
| Coherence | Followed; public DSH boundary, processing/ACK separation and retained usage paths match approved design |

Final verdict (Round 2): **PASS — 0 CRITICAL, 0 WARNING, 0 SUGGESTION.** Static code-review findings: `[]`; corrected delta outcome: **aligned**. Round 1 was INCONCLUSIVE with two evidence items; both are closed by the evidence and retention assessment recorded below. This verifies the scoped gate, not production deployment or future remote CI.

## Completeness

- Tasks: first four implementation blocks are present; actual product journey is now supported by `acceptance.md` and independent `review.md` Round 2. Any unchecked journey checkbox is superseded by that explicit evidence. Final sync, canonical merge, archive and remote CI remain subsequent caller-owned closeout activities; their absence at this implementation snapshot is not a code finding.
- Spec coverage: cumulative APIs/producers retired; Work journal, bubble usage and workflow budget retained; durable metadata/checkpoints, lazy root recovery, HTTP completeness and Web/iOS explanations are implemented.
- Prototype / Reference coverage: source/component/decoding tests and independent `review.md` Round 2 cover each explicit contract. Actual 1440×900 desktop and 390×844 narrow product rendering, running→completed updates, catching_up→current, real API pagination interaction and native main/child detail are recorded. UI response injection is identified separately from the later real catching_up observation.
- Read-only architecture verification independently executed here: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_runtime_dependency_contract.py` → **13 passed in 0.27s** at the frozen implementation tree. No services were started or stopped by this reviewer.

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试 / evidence | 状态 |
|---|---|---|---|
| Retire unused cumulative scan/report/query without changing existing data | `apps/node/src/main.ts:117`; removed integration/PA usage modules; `apps/im-server/src/gateway.ts:759`; `apps/im-server/src/work.ts:850`; schema/NodeStore remove only CREATE and helpers | `apps/im-server/tests/e2e/usage.test.ts:4`; production-source search finds no usage RPC/report/table consumers; no DROP introduced | covered; old-copy upgrade/rollback evidence verified in Round 2 |
| Main/child Work usage, bubble accounting and workflow budget remain independent | `packages/personal-assistant/src/work-projection.ts:29`; `packages/dsh-integration/src/workflow/engine.ts:184`; Work API still reads product tables | `/tmp/refactor655-token-e2e.log`: 1 passed; bubble and Global Work context=31001/output=1/cache_read=1000; native Workflow test retains spent=15 | covered, including independent product journey in review.md Round 2 |
| Completed saved history is read from center; normal restart skips unchanged native bodies | `packages/dsh-integration/src/descendants.ts:76,132,141`; `src/index.ts:395`; `packages/personal-assistant/src/global-agent.ts:305` | `packages/dsh-integration/tests/workflow-native.test.ts:140` onward: real DSH, four completed children restart body reads=0, one changed child=1, grown history restart=0; `/tmp/refactor655-native.log`: 2 files/4 tests passed | covered, including restart/pagination and bootstrap-copy evidence |
| Native persistence → receive ledger → product journal → central ACK recover independently | `global-agent.ts:638,646,670,695`; `inbox.ts:346,357`; `work-sync.ts:85` | `global-work-recovery.test.ts:6,56`; `inbox.test.ts:200`; WorkSync tests; native changed-branch seam | covered for mapped crash boundaries; no ACK used as processing position |
| Open logical attempts preserve pairing, usage and context carry-forward | `work-projection.ts:62,79`; `global-agent.ts:647,703`; existing `presentation.ts:82` | `global-work-recovery.test.ts:56`; existing `global-agent.test.ts:435` fallback completion at same native cursor; `descendants.test.ts:55` model cut capture | covered |
| Child ownership survives live ancestor unloading; cold models do not appear empty | `descendants.ts:47,58,61`; `src/index.ts:127,213`; `model-fallback.ts:126,170` | persisted-catalog restart test in `descendants.test.ts:83`; real native restart checks include saved model versions | covered; both session.event and model.changed use boundRoot |
| Catch-up/unknown state is tied to current registered connection and processing/upload completion | `apps/im-server/src/work.ts:20,33,502`; `work-sync.ts:95,109,123`; PA `work-sync.ts:89` | IM `work-sync.test.ts:195,221`; PA `work-sync.test.ts:157` (pending clear with no new event) | covered; stale connection declarations cannot mark replacement current |
| Web/iOS retain reported counts, display one state explanation and suppress duplicate offline line | Web `agent-work-panel.tsx:164`; iOS `AgentWorkView.swift:31` and optional model field | Web five state cases in `agent-work-panel.test.tsx:223`; iOS `AgentContractsTests.swift:78`; `/tmp/nano-refactor655-ios-test.log`: 8 tests, TEST SUCCEEDED | covered; actual desktop/narrow evidence in review.md Round 2 |
| Existing controls, new input, history pagination and raw native detail stay usable during recovery | root and child drains remain separate (`global-agent.ts:627,675`); existing Work/trajectory read routes retained | existing `global-agent.test.ts:407` protects source checks independent of pending child reads; no changed trajectory retrieval implementation | covered by combined review.md Round 2 journey and existing control/WorkSync regression seams |

Evidence reuse is bounded to the methods actually shown. `/tmp/refactor655-native.log` proves the public persistence-handle body-read calls asserted by the committed native test; it does not measure physical storage I/O. Changed-branch JSONL can still decode the full inherited/native body. The returned slice, checkpoint suffix and an in-memory cache are not represented as O(delta) file I/O.

The initial unconstrained parallel backend/frontend run had resource-contention timeouts. Subsequent bounded logs now show backend **131 files / 703 tests passed**, frontend **107 files / 1022 tests passed**, and Python **65 passed / 31 deselected**. `/tmp/refactor655-ios-full.log` records **24 tests in 5 suites passed**; `/tmp/refactor655-ios-archive.log` records **ARCHIVE SUCCEEDED**. No timeouts/assertions were weakened. Build/typecheck, frontend build/audit, ruff and iOS runtime gates are recorded in `acceptance.md`; this reviewer inspected the final backend/frontend/Python/iOS/typecheck log endings and reused the versioned evidence instead of rerunning full suites.

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| Only public DSH exports; PA/IM have no DSH imports | yes | integration imports package roots; dependency contract independently passes 13 tests |
| Persist relation/catalog metadata without a second native-body repository | yes | `descendants.ts:11-24,47`; domain stores root/cursor/children/active/witness only |
| Cross-restart witness uses immutable header + size/count; revision limited to current service | yes | `descendants.ts:26-35,41,132-138`; revisions map is process-local, excluded from persisted Catalog |
| Certify the observed cut with flush and same-instance stat checks | yes | `descendants.ts:145-167`; missing/unstable witness remains conservative after restart |
| Read cold ModelRun and workflow ownership without budget history scans | yes | `model-fallback.ts:126,170`; `workflow/engine.ts:184`; `src/index.ts:430` |
| Processing checkpoint and display facts atomically commit in InboxStore; ACK is separate | yes | `inbox.ts:357`; `global-agent.ts:670,711`; WorkSync retains independent acknowledge logic |
| Root runtime hydration is delayed only after metadata checks and no pending execution obligations | yes | `global-agent.ts:305-323`; settled native catalog/model/inbox checks in `src/index.ts:395` and `descendants.ts:76` |
| Pending processing survives crash and is not inferred from central ACK | yes | `inbox.ts:27,367`; constructor marks existing global bindings pending; reconciliation clears only after drains succeed |
| UI change is a status line with existing counts/navigation preserved | yes | one added Web paragraph and one iOS text branch; no layout/list/usage calculation changes |

The installed public `@deepseek-ai/dsh-session-persistence@0.2.1-alpha.1` type contract confirms append-only storage and revision comparability only within the same service instance/session. Source inspection did not find private runtime imports, a fork/patch or a second execution loop.

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| catching_up / unknown distinguishable; current hidden; offline only one explanation | M1 UI/sync task | Web line 165; iOS lines 32-38; five Web cases and optional iOS decoding | `acceptance.md`; independent `review.md` Round 2 screenshots/observations | covered |
| Latest reported main context semantics and numeric values retained | M1 retained counters | Work usage projection and existing latest usage calculation; real token E2E | `acceptance.md`; `review.md` main40/18/cache60 and child40/9/cache30; token E2E locator | covered |
| Main/child process, pagination, native trajectory remain usable | M1 product journey | existing routes/components retained; incremental reconciler changes reviewed | `review.md` Round 2 pagination/native detail journey | covered |

## Issues

### CRITICAL（提 PR 前必须修）

None open. Round 1 E1 (real-product evidence) and E2 (upgrade/rollback-copy evidence) are closed; see Round 2 closure matrix below.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Gateway service-lifecycle: reconnect example uses an existing conversation.query request | cumulative node.report handler and producer removed; Channels test examples now use an existing delivery receipt request | `packages/channels/tests/web-relay.test.ts`; generic reconnect semantics remain unchanged | aligned |
| IM auth-tenancy: remove cumulative metrics examples and owner-query scenario | endpoint deleted, no broadened access paths; existing Work qualification retained | `apps/im-server/tests/e2e/usage.test.ts` requires retired query 404 and report unsupported | aligned |
| IM agent-work: saved history and normal restart | center product-table read unchanged; catalog witnesses and checkpoint-driven lazy recovery added | real DSH 0/1/0 body-read assertions; Inbox persistence tests | aligned |
| IM agent-work: crash-gap recovery | receive ledger and transactional Work checkpoint are distinct; existing journal upload ACK retained | Global recovery crash and open-turn tests; Inbox rollback and WorkSync tests | aligned |
| IM agent-work: catch-up/unknown, continuing updates and latest reported usage | current-connection progress declaration; pending marker; Web/iOS states and existing usage | IM/PA WorkSync, Web state cases, iOS decode, token E2E and review.md Round 2 | aligned |
| IM auth-tenancy: two canonical link corrections after frozen implementation | only personal-agent and gateway-relay Markdown targets changed; requirement/scenarios unchanged | both targets independently resolved to existing docs/specs/im files | aligned |

### Uncovered Observable Behavior

None found in the unit diff. Optional `record_sync_state` and its client fallback are covered by the added Work requirement. Removal of cumulative usage.read/node.report/query is documented by the unit motivation/design and the two retirement deltas. Canonical specs deliberately still contain the old metrics/reconnect examples at this pre-merge stage; merge the approved deltas during closeout, rather than treating the unmerged current text as an implementation defect.

Outcome: **aligned**. No delta-mismatch, implementation-mismatch or uncovered observable behavior found. The two canonical link corrections are non-semantic and do not invalidate the implementation mapping.


## Round 2 — Targeted closure and integration retention

- verification_mode: targeted-closure plus corrected-delta update; review_round: 2.
- validated_at remains `0d3a762fed52fe14a93fcb03ba4de72532a5887a`; executed_base remains `063b0742f`. These describe where the implementation was actually inspected and evidence executed.
- Scope: new `acceptance.md`, independent `review.md` final pass, copy/restart artifacts, two auth-tenancy link corrections, and `063b0742f..648e263d2` invalidation assessment. Git confirmed no source/test/config/runtime delta from frozen implementation in the candidate worktree.
- Verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**. No further full test run required for this unchanged implementation.

| Round 1 issue | Checked evidence | Closure |
|---|---|---|
| E1: M1 actual product/viewport journey absent | Independent `review.md` Round 2: real main/child read success/failure with parameters/results, real second message running→completion, saved old content during real catching_up and delivery then current, browser forwarding to the real `limit=1` API and clicking Earlier turns, main/child native detail, desktop1440/narrow390; `acceptance.md` identifies candidate/services/limits | closed; product pass, 0 issues. No claim of a manually induced network outage: retry/ACK/control separation retains existing tests, combined user-visible result observed live |
| E2: first-upgrade/rollback-copy evidence absent | `/tmp/refactor655-upgrade-copy/evidence.json` and producer script: pre-change Node/Inbox/IM classes create old databases, candidate opens copies, stable replay does not duplicate, old entries reopen upgraded copies with cumulative samples and journal identity/content/ACK retained | closed; schema/data compatibility and coordinated old-entry reopening, explicitly not production/full deployment rollback |
| E2 bootstrap/normal-restart distinction | `/tmp/refactor655-bootstrap-copy-2/evidence.json` and script: copied completed native histories excluding nano_work_catalog; actual public DSH handle.read observes root43/child29 once; second cold runtime reads 0 bodies, settled/rootSettled true | closed; public persistence seam measurements, not physical I/O; source runtime untouched and no Agent execution |
| M1 saved-count invariance across actual Gateway restart | `/tmp/nano-refactor655-browser/restart-evidence.json`; `acceptance.md` records strict equality checks for main/child turns and usage, revision35 unchanged | covered; main context40/output18/cache60 and child context40/output9/cache30 retained |

### Main increment invalidation assessment

Inspected the complete changed-file list and relevant runtime-harness/skill diffs for `063b0742f..648e263d2373985a088cce55222901ef7c420cb5` (origin/main verified at that SHA). It adds the daily acceptance template/configuration/seeding script, harness tests, documentation/skill routing, and archived feat-654 reports. **No apps/, packages/, src/, dependency lockfile, package manifest or CI runtime change** occurs in this increment. `scripts/e2e-up.sh` adds explicit daily branching while retaining the default fixture path. The new seeding module is used by that harness, not by the application runtime.

Therefore the full static review, verifier implementation mapping, native/body-read tests, token E2E, independent product acceptance and client/build evidence are **retained** for a conflict-free merge of exactly this increment. The recorded product run used the frozen implementation and approved specialized deterministic-provider fixture; adopting a later daily default does not invalidate its observed Work/recovery behavior or require an unrelated business rerun. New main harness tests belong to final integrated local checks, owned by caller; this report does not claim they ran at the old implementation snapshot.

The caller must bind effective_through to the actual resulting integration commit and ensure no additional runtime edits/conflict resolutions alter this assessed tree. Only a later material delta would require another affected-scope review; a Git merge without conflict is not itself the retained-evidence rationale.
