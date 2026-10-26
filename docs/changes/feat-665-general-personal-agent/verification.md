# Verification Report: feat-665-general-personal-agent

Current verification: **Round 5 CR-04 closure at `d2a6f53d2`: 1 CRITICAL evidence gap, 0 WARNING, 0 SUGGESTION**. R1 and its original snapshot remain below; see the final round for the current issue disposition.

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

## Round 3 — focused delta at d41425170

- verification_mode: `delta`; review_round: `3`; fix_delta_range: `4d5ef9c9c..d41425170f0f1226ce51b71d77072cee040bd9d3`.
- Scope: direct-reply attention identity/publication feedback; first cold runtime catalog; evaluation settlement with live children.
- requires_full_verification: `false`. The finite delta changes these seams without replacing the prior full unit architecture/contract review. R1 and R2 source conclusions remain outside the focused changes.
- verdict: **incomplete overall**; delta itself aligned; critical **1**, warning **0**, suggestion **0**. Latest code findings remain `[]`.

| Focus / contract | Implementation and independent validation | Disposition |
|---|---|---|
| PA-1 original real Web dismiss failure; design.md:58,80 | Item/revision validation precedes trusted ordinary-reply exemptions, and all exemptions preserve item identity for publication. Native IM test covers direct reply card duplicate feedback and stale cards; 10 attention tests pass as part of 11-test affected run. | Implementation seam fixed; original acceptance fail preserved; actual repaired Web journey pending. |
| New PA optional tools discoverable from first catalog; design.md:100-104 | Built-ins mount before extension HMR yield; real subprocess starts with zero Agents, first catalog asserts four personal tools, then applies config and executes tools/Schedule. | Independently passed affected native test. |
| Real delivery capture cannot treat an early ack as completed child work; design.md:137-139 | Latest visible child turn is read before settling, active/permission wait blocks, root revision change resets stable period. Direct function probes prove no return during running and ≥5s after final revision; protocol 11/11 passes. | Harness mechanism verified; real D08 rerun/classification remains pending. |

Independent validation locators and clock-probe outputs are recorded in code-review.md Round 3. Context review reused that focused patch trace; no second full Context audit or new gate was introduced.

V-01 remains **pending**. The caller-owned acceptance R1 reports actual successes for draft adoption without send, private file bytes/version availability and correction to the original executor, but also the original card dismiss failure and extensive inconclusive scenario coverage. Those local successes can support their exact claims; they do not satisfy all M1/M2/M3 exits. Preserve R1's failed actual journey, then append a separately versioned real Web regression result when available. Final serialized outbound HTTP capture, model consumption/adjudication, all required checkpoint coverage, repeated/core comparable baseline evidence and applicable final CI must remain honestly classified. Proposed isolated Node capture after shared logging ceased is not yet observed evidence and is not proof of upstream provider receipt.

No source/test/design/runtime was altered by this verifier. The pre-existing untracked acceptance report was preserved and not staged. No reviewer-created service requires cleanup.

## Round 4 — focused delta at 085b1b896

- verification_mode: `delta`; review_round: `4`; fix_delta_range: `d41425170..085b1b89611c642162e577e30dbdb268cbb7206f` (intervening reports excluded).
- requires_full_verification: `false`; the prior full review is retained outside this finite delta. Focused Context review is reused from code-review.md Round 4.
- verdict: **fail / incomplete**; critical **1** (existing V-01), warning **1** (new V-05/CR-04), suggestion **0**.

| Focus / contract | Implementation and direct evidence | Disposition |
|---|---|---|
| Source withdrawal rejects future reads; spec I06/S03 | Excluded source projection returns ID/flag only before Messaging content/title/last preview is read; post-revocation sentinel regression passes. | Aligned |
| Cold execution after canonical Task removal; W05/W06 and design Task recovery | Real restart + accepted late native input; withdrawn child does not call model, canonical empty snapshot retained. | Regression passes; natural model behavior remains separately scoped |
| Memory maintenance correction race and private/global method boundary; M09/M11 | Frozen real native revision-1 read cannot overwrite revision-2 correction; global private Skill write denied. | Regression passes |
| Review failure meaning/actionability; Context error semantics | owner_authorization_changed stays a blocking review failure and now explains snapshot staleness without asserting user revocation; re-read/new review remains required. | Aligned |
| PA-5 mixed-request continuation; design.md added continuity paragraph | Clean remaining-work summary with verified owner message ID and fixed owner DM survives actual rollover; records identity excludes transient summary. | Continuity seam implemented; actual product reviewer retest pending |
| No erased bodies in controlled active context; spec.md:42-44, design.md:70 and added continuation paragraph | Independent native probe puts exact selected record body into continuation: post-rollover messages still contain it even though recordCount=0 and pendingForgets=0. | **Implementation mismatch, V-05/CR-04** |

### WARNING — V-05 / CR-04: continuation can restore erased controlled content

Contract: the existing erasure requirement and new design both require a handoff without the forgotten fact/values; cleanup must report actual completed layers. At `knowledge/runtime.ts:177-190`, only summary type/length are checked before persistence. At `personal-memory-context.ts:56-67`, the unchecked string enters the new native checkpoint, followed by completeForget. Independent native assembled-input capture confirms exact body reintroduction with a complete receipt. This is a directly verified interface failure, not an assertion that a real model will necessarily make that mistake.

Action: ensure the new handoff cannot carry the known erased body before it is persisted/consumed, with an actionable clean-summary retry or actual pending state when cleanup cannot complete. Preserve continuity for clean summaries and add narrow protection for this exact erasure path. Do not change spec to permit silent erased-data retention.

Independent affected tests: **33/33**, `/tmp/pa665-independent-round4.log`; exact command and isolated native reproduction appear in code-review.md. The working clean-summary fixture and these tests do not refute CR-04, because they supply a summary without the erased value.

V-01 remains pending. Caller-reported final build/typecheck/iOS-runtime, broad Web/docs/Python/lint checks and narrowed timeout rechecks can be retained against their actual version/commands. They do not replace the still-collected provider/actual model/product/checkpoint/core replay/comparison evidence; this focused review does not prematurely close that item or rewrite R1 real failures. No new full-suite rerun or production action was performed. Reviewer-created repro subprocess/workspace was cleaned; only review reports are modified.

## Round 5 — targeted-closure of V-05 / CR-04

- verification_mode: `targeted-closure`; review_round: `5`.
- fix_delta_range: `3dca27c23..d2a6f53d2c666e6c06b05c89ece6a377abd1e489`; finding_origin_head: `085b1b89611c642162e577e30dbdb268cbb7206f`.
- focus_issues: `V-05/CR-04`; requires_full_verification: `false`. Prior full review/source boundary conclusions remain where unaffected.
- verdict: **incomplete overall**; focused implementation issue **closed**. critical **1** (V-01 still pending), warning **0**, suggestion **0**; latest code findings `[]`.

| Focus | Independent evidence | Disposition |
|---|---|---|
| Current exact erased body cannot survive in continuation | Validation occurs inside the existing memory lock, before the handoff callback and erase authority commit. Direct original-marker case and updated real native unsafe-current path reject the call; record remains and no pending receipt is created. | V-05 current-body path closed |
| Associated prior exact body cannot survive | Tombstone normalized hash/length matches substring without storing old body. Direct prior-body and native unsafe-prior paths reject; no handoff callback. | V-05 historical-body path closed |
| Historical missing lengths and safe recovery | Nonempty summary explicitly fails closed; empty summary can finish after other actions. Direct synthetic state check passes. | Aligned with revised design, no silent unsafe fallback |
| Persisted handoff and complete replay | Callback runs only after validated/applicable erase and before authority publication; complete replay does not prepare a new handoff. Independent callback count remains one after completed replay. | Closed at reviewed boundary |
| Legitimate continuity and restart | Updated native test retains clean remaining-work summary and fixed DM, removes secret from assembled messages and passes restart fence. Independent affected run 15/15 (`/tmp/pa665-independent-round5.log`). | Existing good path retained |

Context evidence reuses code-review.md Round 5's exact-body Store and native request/receipt checks. It proves the confirmed deterministic erasure-handoff defect is fixed, without claiming complete semantic erasure or that every real model continuation is correct.

The independent product `acceptance.md` Round 4 supplies versioned real evidence for the original PA-5 mixed forget/correct request: correction committed before empty-continuation forget, actual private erasure receipt, and later cross-chat 10–12 candidates. This closes that original actual journey and supports retention of the successful empty-summary path. The acceptance report still has its broader fail/inconclusive/recovery and scenario evidence gaps. **V-01 remains pending** for the full-unit package already being collected; this targeted closure does not waive or expand those exits. Original real failures and all prior review rounds remain recorded.

Only review reports were modified. No unrelated full-suite rerun, production action, new live service or test/source/design change was made. Synthetic Store reproduction data was cleaned.
