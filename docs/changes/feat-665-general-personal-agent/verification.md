# Verification Report: feat-665-general-personal-agent

Current verification: **Round 2 targeted closure at `860eb4ecb`: 1 CRITICAL evidence gap, 0 WARNING, 0 SUGGESTION**. R1 and its original snapshot remain below; see the final round for the current issue disposition.

> Validation snapshot: `85910853e → 783ff080f4a110780d78473e95d0bc391c64c50f`

## Round 1 — full

- verification_mode: `full`
- review_round: `1`
- requires_full_verification: `false` (this round already covers the full requested unit)
- verdict: **fail / incomplete**
- critical: **1** (required exit evidence incomplete)
- warning: **3** (confirmed implementation deviations, CR-01–CR-03)
- suggestion: **0**

## Summary

| Dimension | Result |
|---|---|
| Completeness | All 6 Requirements and all 15 Scenario groups have implementation routes; 0/3 milestones have demonstrated all exit criteria |
| Correctness | Three deterministic deviations independently reproduced; other listed tests support bounded claims, not universal model behavior |
| Coherence | Existing Task/Knowledge/Global/IM/native DSH owners retained; no architecture-contract failure found |

This is an implementation/spec/design verification, not a product-experience acceptance. Source alignment and native scripted-provider tests are not substitutes for the required real-model/browser evidence. Implementation defects, unproven behavior, and design concerns are separated below; no new design defect is asserted.

## Completeness

| Milestone | Implemented | Demonstrated exit criteria | Remaining |
|---|---|---|---|
| M1-memory | Records, sources, migration, projections/query, revision refresh, forget fence/rollover, maintenance integration | Store/native memory tests; explicit offline migration and repeat receipt; current/context cleanup fixtures | CR-01/02; all M01–M12/S01/S02 behavioral assertions and appropriate final serialized provider-input evidence, including combined maintenance/forget lifecycle |
| M2-proactive | Query/coverage/cursors, attention/settings/budget, trusted owner delivery, versioned feedback, native snooze | IM source/receipt/revision/quiet/interaction tests; native selected tools/Schedule and creation-source restart test | CR-03; P01–P14/I01–I06/U01–U04/S03 actual journeys, real browser feedback/old-card/draft adoption evidence |
| M3-delivery | Canonical execution references, native binding/running/withdrawal, child roles, artifact bytes/version/permissions, defaults/12 Skills, 58 adapters | Native child/Task tests; artifact/media tests; collect=58; protocol/architecture tests | W01–W10/D01–D08/S04 behavior, actual failure/restart/correction and child role cold-restore evidence, file open/external approved-copy browser journey, core ≥3 replays and same-config old baseline comparison, applicable final CI |

No tasks/progress files are required by this simplified workflow. Existing `.gitkeep` milestone directories do not constitute acceptance evidence. No prototype/new frontend component exists; the explicit contract is to exercise the reused real browser flows (`design.md:58,126-129,136-137`).

## Correctness

Paths below are repository-relative; code findings have exact lines in `code-review.json`. “Implemented; behavior pending” never means accepted.

| Requirement / Scenario | Implementation evidence | Test/evidence | Status |
|---|---|---|---|
| Memory / cross-chat use M01–M05/M08/M12 | `knowledge/personal-memory.ts:87-95,193-209`; `features/memory-curation.ts:22-30`; `personal_context` | Store tests; native assembled request fixture; candidate M01 raw journey | Implemented; real behavior pending |
| Memory / correction and maintenance M02/M09/M11 | `knowledge/runtime.ts:158-200`; `ReviewFiles.memoryRecordsRead`; record revision transaction | concurrent/stale-revision tests; candidate M02 raw journey | **CR-01 deviation**; remaining behavior pending |
| Memory / forget and disabled M06/M07/M10 | `personal-memory.ts:245-259`; `personal-memory-context.ts:24-91`; configuration filtering | forget/old-source/receipt tests; native notes/history/restart fixture | **CR-02 deviation**; full failure-layer and model consumption evidence pending |
| Proactivity / commitments/conflict/opportunities P01–P04/P13/W09 | `personal-attention.ts:128-186`; proactivity Feature and domain Skills | private attention tests and source/Task-link checks | Implemented; actual preparation and model choice pending |
| Proactivity / quiet/partial/urgency P05/P09–P12/P14 | `personal-attention.ts:223-269`; `personal-assistant.ts:175-183`; `personal-delivery-evidence.ts` | missing attention, quiet, source revoke, direct/schedule exemption tests | Implemented; representative real behavior pending |
| Proactivity / snooze/dismiss/suppression P06–P08 | `personal-context.ts:25-34`; settings/command/snoozeComplete | real native snooze fixture; IM dismissal/settings tests | **CR-03 deviation** |
| Observation / batches and direct requests I01–I04 | existing Global Inbox + `personal-attention.ts:64-97` separate query receipts | pagination/non-consumption test; existing unchanged batching | Implemented; full multi-actor journey pending |
| Observation / research and revoke I05/I06/S03 | root-private product guard; query policy revisions/message access | policy revoke and child denial tests | Implemented; actual source-revoke journey pending |
| Multiple work / parallel/correction/recovery W01–W05 | `task-native-execution.ts:29-99`; canonical `task-graphs.ts:274-290,312`; Task driver | native bind/running suppression/needs_coordination fixture | Implemented; actual child correction execution, failure and cold-recovery proof incomplete |
| Multiple work / stop/wait/unknown W06–W08 | `task-native-execution.ts:100-112`; canonical Task/waiting and existing stop flow | native withdrawal and existing Task tests | Implemented; full real cancellation/independent-work/unknown-side-effect journey pending |
| General service / domains and missing connections D01–D08 | 12 bundled Skills, editable PA default, context returns external status unknown | PA default tests; D08 raw journey; catalog/protocol | Implemented; domain behavior assertions pending; live external correctly remains separate |
| General service / actual files and revisions | `personal-artifacts.ts:19-59`; `global-agent.ts:426-435`; `media.ts:148-252`; existing reviewed copy | path/bytes/hash/version/idempotency/access tests | Implemented; actual browser open and approved-copy journey pending |
| General service / suggestions/draft/old cards U01–U04 | `interactions.ts:140-158`; publication binding in Messaging; existing ComposeMessage | old-card/cross-key duplicate feedback test | Implemented; actual browser journey pending |
| Control / identity/minimal context S01/S02/S04 | binding/source authority; `personal-delegations.ts:28-80`; bridge root guard | real native scripted task/observer scoped schemas and denials | Implemented; provider wire input, grep/role recovery and representative real child behavior pending |
| Control / config and legacy W10 | `agent-config.ts:149-176`; default only on PA creation; `migrate-personal-memory.ts`; authoritative records | preserved custom/empty prompt tests; migration/replay/failure tests | Implemented; full compatibility/rollback acceptance evidence incomplete |

### Delta-spec reconciliation

All four active deltas are considered: gateway/personal-agent (records, attention, query, artifact), gateway/task-graphs (execution), gateway/agent-capabilities (selection, roles, migration and modified maintenance lifecycle), im/personal-agent (chat control, modes and delivery). They map to the implementation above. No additional unmatched outward behavior was found requiring a fifth delta. CR-01/02 are implementation mismatches with scoped memory and correction/forget requirements; CR-03 mismatches versioned retryable feedback. Do not amend deltas to accommodate these defects.

## Coherence

| Design decision | Evidence | Result |
|---|---|---|
| DSH public exports only; no second runtime/loop | imports remain in integration; independent dependency-contract tests | Aligned |
| Task/Work remains execution truth | execution object is canonical Task data; storage domain retains only native references | Aligned at reviewed scope |
| Private attention is not an execution engine/scheduler | IM SQLite owns candidates; snooze calls native schedule | Aligned, except retry mismatch CR-03 |
| Records are memory authority; projections disposable | locked transaction, binding match, projections rebuilt from records | Aligned, except identity/replay logic CR-01/02 |
| Trusted roles, minimal handoff, ordinary tools cannot self-upgrade | host delegation domain, tool allowlist + execution guard, no private root tool access | Source/native fixture aligned; cold recovery/provider proof pending |
| All owner-private deliveries classified using current trusted evidence | native and external paths route through attention prepare; current live IDs/Schedule grants/Task checked | Source and tested receipt seams aligned; full model behavior pending |
| Preserve old custom prompt, Skill choices and production boundaries | creation-only default; existing selection/bootstrap; offline migration entry/runbook | Aligned in reviewed changes; no production work performed |

### Prototype / Reference Contract

N/A for new prototype. Reused real browser contract remains **unverified**, covering rendered advice/feedback, draft adoption without send, stale cards and opening the delivered file version. This report does not judge visual quality from source.

## Issues

### CRITICAL — V-01: required milestone exits are not demonstrated

Contract: `design.md:135-139`, `spec.md:94`, and `docs/development/agent-context-engineering.md:94-98` require actual final Context/model behavior, all scenario adapters/classification, core at least three independent replays against a comparable old baseline, browser and applicable CI evidence.

Observed at report capture: `collect --cases all` resolves 58 adapters (zero live actions). Nine `/tmp/pa665-runs-v2/*/results/result.json` raw results (baseline/candidate M01/M02/D08) are execution-complete but explicitly `not_run/evidence_needs_review`; none had an adjacent independent adjudication. The remaining scenario checkpoints/behavior and final provider wire/browser claims are not proven. Worker facts about native scripted providers cannot fill those exits. The provided all-Vitest run is 785/789; four-file recheck is 19/19, which shows the previous failures did not repeat there but does not establish final complete CI.

Action: finish the already-required isolated journeys/checkpoints, independent assertion-level adjudication, provider input checks, browser flows, repeated/core baseline comparison and final applicable gates. Preserve actual failed/blocked/not_run classifications; unavailable external accounts only block their live-external parts. A later report may retain these code findings while updating evidence coverage for the actual version; absence of evidence is not itself a claim of product failure.

### WARNING — V-02 / CR-01: supersession permanently blocks new owner correction

Contract: `spec.md:35-41`; `design.md:64-68`. Actual: `personal-memory.ts:236`, independent R1 in code-review.md. Fresh verified source and correct current revision cannot restore A after A→B. Use version/source-aware supersession protection without rejecting legitimate new owner correction; add the narrow regression and patch review.

### WARNING — V-03 / CR-02: selected forget deletes unrelated same-text subjects

Contract: `spec.md:38,43-44`; `design.md:64,70`. Actual: `personal-memory.ts:253`; independent R2. owner/partner distinct facts are both deleted. Preserve fact subject/applicability identity when recognizing actual copies; verify only the selected fact and its true historical copies are erased.

### WARNING — V-04 / CR-03: pending attention retry changes identity across turns

Contract: `spec.md:53-55`; `design.md:76,80`; tool description promises stable retryable pending handling. Actual: `personal-context.ts:26` and `personal-attention.ts:135-139`; independent R3. Host turn-specific batch alters canonical payload. Separate budget metadata from retry identity or retain the first batch; verify a real pending snooze can finish on a later turn with the same key.

### SUGGESTION

None.

## Evidence and boundaries

Independently rerun: `python -m tests.e2e.general_personal_agent collect --cases all` → 58 / live_actions=0; `python -m pytest -q tests/contract/test_runtime_dependency_contract.py tests/e2e/general_personal_agent/test_protocol.py` → 24 passed. Three isolated deterministic reproductions are recorded in code-review.md; temporary workspaces were removed and SQLite closed.

Reused frozen-version build/test locators supplied by implementation owner: `/tmp/pa665-build-all.log`, affected `/tmp/pa665-build10.log`, `/tmp/pa665-build8.log`, `/tmp/pa665-external-build.log`; `/tmp/pa665-full-vitest.log` (785/789), `/tmp/pa665-failed-recheck.log` (19/19); native fixture logs listed in code-review.md; `/tmp/pa665-external-test.log` (33/33). Offline `/tmp/pa665-migration-first.json` and `/tmp/pa665-migration-replay.json` both show revision 1, record_count 1, legacy_source_count 1 and the same migration-v1 receipt. These are synthetic isolated facts, not production state.

No self-created live service/worktree requires cleanup. Reports are the only reviewer edits. Existing caller evidence stacks remain owned by the caller; this reviewer did not stop or mutate them. **1 critical issue and 3 warnings: fix/complete before declaring the unit ready.**

## Round 2 — targeted-closure at 860eb4ecb

- verification_mode: `targeted-closure`; review_round: `2`.
- prior_verification_path: this file, Round 1.
- fix_delta_range: `783ff080f4a110780d78473e95d0bc391c64c50f..860eb4ecbfee8982dafa2a7c50afe5ab3b30fd65`.
- focus_issues: `V-02/CR-01`, `V-03/CR-02`, `V-04/CR-03`.
- requires_full_verification: `false`; retained R1 full source/contract coverage still applies outside the focused delta.
- verdict: **incomplete**; critical **1**, warning **0**, suggestion **0**.

| Issue | Independent closure evidence | Status |
|---|---|---|
| V-02 / CR-01 | Scope/source-aware supersession permits fresh current-revision A→B→A, but the old source replay is still refused. Narrow regression independently passes. | closed |
| V-03 / CR-02 | Scope hash on tombstones and duplicate deletion preserves same-text partner and distinct-applicability records; real duplicate/old-version forget regressions remain green. | closed |
| V-04 / CR-03 | Host batch is excluded from canonical idempotent operation payload; same pending snooze replay across turns returns its existing receipt and can complete the Schedule. | closed |
| V-01 | No new final provider/browser/adjudicated 58-case/repeated-baseline/CI package was included in this focused dispatch. It remains the required outstanding exit-evidence item from R1, not a newly inferred code failure. | pending |

Validation: `pnpm exec vitest run packages/dsh-integration/tests/personal-memory.test.ts apps/im-server/tests/personal-attention.test.ts` independently **22 passed**, `/tmp/pa665-independent-closure.log`. Context findings reuse this reviewer's code closure above; no duplicate complete Context audit was run. No remaining code finding, no asserted design defect. Caller continues the already-running real acceptance collection; retain truthful results and close V-01 only against adequate version-bound evidence.
