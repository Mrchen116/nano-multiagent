# Verification Report: feat-676-role-memory-dreaming

> **2026-10-29 设计 R8 实施重开：下列旧版本结论是历史证据。** 前台单写、连续原文、child 两阶段提炼、共享历史回查与输入协议迁移已经改变，相关旧门禁不再覆盖当前实现；本轮新报告完成前不能按旧 pass 交付。未受影响的 UI/旧模式等只可按具体证据继承。

> **Latest targeted verdict: Round 5 pass / aligned** at `e207a51b6e8313083cff05ccebfcca7196b8653d`, **0 CRITICAL / 0 WARNING / 0 SUGGESTION**. The original M1 signoff below remains valid outside the affected native trajectory entry; S18's earlier Work-only evidence is superseded and actual native product reacceptance is separate. See Round 5 for the fixed delta and current evidence limits.

> Historical M1 final verdict: pass at `5a123bae760d429c84bc2a3f72814009a69836f0`; independent product acceptance `8b28b00dd` recorded S01-S20 and the persisted-pending→applied UI state. All prior implementation findings and C1 were closed. The original snapshot and rounds below are preserved, subject to the Round 5 native-entry correction.

- `validated_at`: `5a123bae760d429c84bc2a3f72814009a69836f0`
- `executed_base`: `6b4213c205db04adcebc950fe539a5a759e57391`
- `effective_base`: `6b4213c205db04adcebc950fe539a5a759e57391`
- `effective_through`: `5a123bae760d429c84bc2a3f72814009a69836f0`
- Final origin/main fetch remains effective_base, with no new upstream implementation delta. Caller-owned subsequent report/canonical/archive-only changes can retain this snapshot with their actual range recorded.

> Validation snapshot: `6b4213c20 → be1fec6c9075ffafe402c7387f3cde25546ae95d`

- Round: 1. Mode: full, including corrected-delta reconciliation.
- Independent reviewer; code review and Agent Context Implementation Review reused from `code-review.md`.
- Verdict: **fail / incomplete M1**. Four confirmed implementation warnings and outstanding exit-criterion evidence prevent pass. `requires_full_verification: false`: this was already a full review; subsequent review can target the actual fixes and missing evidence.

## Summary

| Dimension | Result |
|---|---|
| Completeness | All seven W criteria and five R criteria assessed; several only partially evidenced |
| Correctness | Ownership, current-file refresh, mode/tool exclusion and atomic per-file publication present; recovery, budget continuation, checkpoint scope and retired UI tool have defects |
| Coherence | Core package/DSH public-export boundary followed; four deviations described below |

## Evidence snapshot

- `/tmp/feat676-validation.txt` records implementation commands and locators. Runtime/PA aggregate was 425/426 followed by the affected 55/55 rerun (`/tmp/feat676-remaining.log`). Boundary suites: 16/16 (`/tmp/feat676-boundaries6.log`). Native request capture/scheduling/review: 8/8 (`/tmp/feat676-coretests4.log`). These are mechanism/provider-stub evidence, not model comprehension.
- Current-head build: `/tmp/feat676-build-be1fec6c9.log`, installer SHA `be1fec6c9075ffafe402c7387f3cde25546ae95d`. The older all6 log identifies the earlier commit and is not used to assert the final version.
- Caller reports build, typecheck and `check:ios-runtime` passed. `/tmp/feat676-python-ci.log`: 124 passed, 28 deselected. This includes the synthetic offline migration and dependency contract gate, but does not prove a production migration.
- At this review cutoff the caller's root TypeScript CI and native iOS build were still running. `/tmp/feat676-root-ci.log` already contained failures in personal-agent/control/personal-attention/providers/global-inbox-native without a final disposition. `/tmp/feat676-ruff-format.log` reported two files requiring formatting. `/tmp/feat676-docs-check.log` contained a missing-yaml execution failure, not a successful docs check. The caller must attach final commands/results and classify/fix failures before closing W7.
- PA live save/correction message locators are supplied in `/tmp/feat676-validation.txt`; the caller owns ongoing real product acceptance. No product scenario is marked passed solely from that summary.

## Completeness

| M1 exit criterion (`design.md:274`) | Available direct evidence | Status / remaining work |
|---|---|---|
| W1 certified live/cold source, own prefix, pairing, dedup/revision, budgets, crash boundaries | `memory-sources.test.ts:21-79`: second-flush cut, failure, inherited prefix, open calls, fragments, revisions and verified child tool evidence | Partial. Large-unit continuation is broken (F2). No final evidence of persistence restart at the source/cursor boundary or actual same-root multiwindow source export was supplied. Add only the missing meaningful seam coverage. |
| W2 conflicts, Git failure, every apply/cursor crash point; consumed/revoked source while off/restart/sync failure; child next decision | `memory-documents.test.ts:20-94`: body freshness, third version, Git failure, generation restart and lost atomic receipt | Partial. Library-level tests do not exercise Dreaming's full plan/entry/cursor recovery; F1 demonstrates a missed recovery failure. No supplied actual child request after revocation/sync failure or complete consumed-source cleanup evidence. |
| W3 injected timing, no increment, off/pause/resource/modes; creation and no F3/F4/combined | `dreaming-scheduling.test.ts:24-49`, `capabilities.test.ts:191-249`, `knowledge-review.test.ts`, config/PA tests | Substantial partial. Timing/admission, cancellation, legacy Memory-only review and fixed built-in Skill loading across selections covered. Real foreground Skill creation/discovery, no-increment actual provider count and both-direction live mode switching are not established by the cited subset. |
| W4 actual root/child/maintenance request, role/freshness/disabled tools/nonrecursive source; real model use | `memory-runtime.test.ts:6-43`, `dreaming-runtime.test.ts:6-31`; inspected actual adapter output/assembly and Skill provider | Partial. Root+maintenance capture exists, but applicable ordinary child request/refresh and real model scenario coverage remain with the caller. F3 is a deterministic model-facing control defect. |
| W5 Work binding/receipt, quiet success, refresh/recovery | `knowledge.test.ts:84` host receipt/link projection; native trajectory registration `trajectory-runs.ts:145-155`; native maintenance test | Partial. Projection/stub evidence exists. Reopened real authorized Work and no external notification in the full stack need the caller's acceptance evidence. |
| W6 Web1280/390 prototype, failure/pending/effective; native iOS build/shared config | frontend detail/config tests; iOS shared-selection tests/code; caller's current live UI observation | Pending screenshots/real contrast and native build. F4 exposes a retired memory control. Runtime TS compile is distinct from native Swift build. |
| W7 offline copies/repeat/interruption/back-switch; scenario table; build/contracts/docs | `test_role_memory_migration.py` covers 7 persistent-write interruption points, bytes/hash/permissions, preserved tool/Skill selections, progress and both stored mode choices; Python 124 passed and final-head build | Partial. Script reentry is proved, but saved mode choices are not a live runtime exclusivity demonstration. S01-S20 acceptance, final complete CI/native build/format/docs results outstanding. |
| R1-R5 actual product scenarios | Initial PA save/correction locators only; ongoing caller acceptance | Not independently accepted by this verifier. Product reviewer owns the journeys and must record every S01-S20 as passed/failed/blocked/not_run. |

## Correctness

| Requirement / scenarios | Implementation | Direct protection / conclusion |
|---|---|---|
| Role ownership, knowledge entry/details, S01-S04 | `document-memory.ts:35-53,99-112`, `memory-documents.ts:55-75`, bundled nano-memory | Trusted role/fixed owner root and blank initialization present. Behavioral scope/uncertainty remains real-model validation. |
| Immediate save/correction/manual save, S05-S07 | `document-memory.ts:54-94,130-134`, `memory-documents.ts:137-166` | Next-root-request stale-basis capture covered; F3 blocks ordinary scoped checkpoint. Original child behavior not established. |
| Actual outcomes/counterexamples, S08-S09 | `memory-sources.ts:77-133,155-177`, Dreaming prompt `dreaming.ts:214` | Failed call/result survives; assistant self-report labeled; own/inherited separation covered. Real synthesis still unverified. |
| Continuous increments/dedup/observation, S10-S12 | `memory-sources.ts:46-150`, `dreaming.ts:86-101,135-145` | Persistent step prefix and source cut covered; F2 prevents progress for a large unit. Actual cross-window journey pending. |
| Concurrent/partial/restart/Git/budget, S13-S16 | `memory-documents.ts:188-244`, `dreaming.ts:133-178,298-316` | Atomic third-version protection and lost receipt supported. F1 prevents later recovery; per-plan cursor crash coverage incomplete. |
| Controls/quiet work/permissions, S17-S18 | `document-memory.ts:116-156`, `dreaming.ts:109-121,204-291`, `knowledge.ts:51-72` | Status/control/tool result semantics and restricted maintenance present. No acceptance from assistant prose; host receipts projected. Actual Work/no-notification verification pending. |
| Migration/default/legacy/import, S19 | `migrate_role_memory.py`, Node configuration/capabilities, tool selection | Offline preservation/normalization/reentry supported; no automatic semantic import. F4 violates UI invisibility. Natural-language import/live mode exclusivity pending. |
| Source revocation/stop-use, S20 | `global-agent.ts:275-293,398-406,446-450`, `memory-documents.ts:169-188` | Complete authority sync precedes cache revoke; generation/pending suppresses entry and is persisted. Full consumed-source cleanup and child behavior still require evidence; registration alone does not establish cleanup. |

## Coherence

- DSH runtime operations remain in dsh-integration using declared public dependencies/exports; Node/PA retain their bridge boundaries. No runtime fork/private import or second agent loop introduced.
- `document` and `legacy` model tool/prompt paths are exclusive; the old writable root is separate. Existing explicit selections stay restricted. Built-in skill-creator is supplied from the package and cannot be shadowed by a user copy; the actual tool allowlist is not expanded.
- Dreaming starts an empty native handle with explicit input files and six allowed tools, no inherited normal sections/contexts, no model-managed catalog entry; Work uses trusted parent/session registration and host outcome projection.
- The approved design requires recoverable conflicts, bounded continuation, per-page confirmation and no exposed old controls. F1-F4 are implementation deviations, not reasons to change the design to fit the code.
- Migration prompt and actual script agree on stopped-writer requirement, raw backup, independent writable legacy root, new blank entry, explicit frozen baselines, retired setting cleanup and no grant of missing tools. Baselines are operator input; the script does not certify live flush itself, which correctly remains the deployment operator's responsibility. Native live mode switch and conversational import still need acceptance.

### Prototype / Reference Contract

| Contract (`design.md:230-232`) | Milestone | Evidence | Status |
|---|---|---|---|
| Only Dreaming control; no memory/creation switch or skill-creator selector | R5/W6 | Web/iOS filtering and config tests; caller observed legacy memory Tool Allowlist row | F4 warning; screenshots pending |
| Save versus applied/pending/failure, draft retained | R5/W6 | Existing config save architecture retained; affected frontend tests | Real1280/390 save/failure/effective comparison pending |
| Work shows range and partial outcomes | R4/W5 | Host partial summary projection test, restricted runtime receipt | Real authorized Work/reopen evidence pending |

## Issues

### CRITICAL

- **C1 — M1 exit criteria are not yet complete** (`design.md:274`). W1/W2/W4 need the specific missing deterministic boundary coverage above; W5/W6 and R1-R5 require caller-owned actual acceptance evidence. W7 still requires final CI/native iOS/format/docs outcomes. Attach versioned direct evidence and resolve real failures; do not treat this report as product acceptance or silently narrow the milestone.

### WARNING

- **F1** `dreaming.ts:133`: retire/rebase inapplicable partial plans while preserving actual saved receipts and third versions; demonstrate subsequent backlog progress and restart safety.
- **F2** `memory-sources.ts:136`: bounded page/continuation support for oversized units without prematurely advancing the unit cursor; demonstrate that a later item eventually becomes reachable under the same budget.
- **F3** `document-memory.ts:132`: scoped confirmation must reuse valid unchanged versions instead of requiring every unrelated page to be reread on each ordinary edit; demonstrate an edit in a library containing an unrelated unread page and maintain revocation safety.
- **F4** `apps/node/src/capabilities.ts:50`: remove the retired tool from document-mode visible settings/catalog/display while preserving stored choices and ordinary tool permissions; verify the actual settings page.

### SUGGESTION

None. Stop after the confirmed findings and required exit evidence are handled.

## Corrected Delta Reconciliation

| Delta item | Implementation / test evidence | Outcome |
|---|---|---|
| gateway/agent-capabilities: document memory, immediate edits, scoped consumer refresh | same-generation unchanged hashes reused; native root capture with unread unrelated verified page; same-child three-request capture (`671954c74`) | aligned; actual model judgment belongs to acceptance |
| gateway/agent-capabilities: persistent bounded Dreaming, conflict/restart/Git progress | inapplicable plan retirement; persisted page offsets/last-page cursor; actual file/entry interruption recovery (`01c5088b7`) | aligned |
| gateway/agent-capabilities: fixed skill-creator, paused Skill automation, modes/defaults/migration | prior native/config/migration evidence retained; migration script/test AST unchanged in fix delta | aligned; actual creation/mode journeys belong to acceptance |
| gateway/personal-agent: current source eligibility and derived knowledge invalidation | prior serialized sync and generation protection; actual child pending/revoked-generation requests; native PA Dreaming refresh before freeze/apply | aligned; completed semantic cleanup belongs to S20 acceptance |
| im/agents-nodes: only Dreaming UI, no retired control, file-only mode | mode/Skill filtering plus old memory catalog/display filtering in Node/Web/iOS; existing selection preserved | aligned |
| im/agent-work: separate native maintenance, host partial results, quiet success, reopen | prior trajectory/host projection; summary distinguishes processed pages from final logical cursor | aligned; real Work journey belongs to acceptance |
| gateway/agent-capabilities: historical automatic Skill discovery/cache-prefix preservation | existing session-level knowledge fact reconciliation and native Skill snapshot behavior retained; auto Skill subscription disabled in both modes | aligned; wording now explicitly limits the automatic-success premise to historical results |
| gateway/agent-capabilities: real consumers protected during capability updates | legacy Memory cancellation-protection test, capability reservation and Dreaming configurationChanging/stopAgent | aligned; wording separates legacy Memory/Heartbeat/business dependencies from cancellable automatic Dreaming |
| gateway/agent-capabilities: model child catalog versus maintenance history | original legacy fork tests plus independent Dreaming assembly/trajectory registration | aligned; inheritance is limited to legacy/historical forks and Dreaming is explicitly an empty-context restricted execution |
| gateway/agent-capabilities: incomplete input and normal model stop are not completion | `dreaming-incomplete-runtime.test.ts` four real native failure modes; actual before/after status stream comparison and unchanged bytes | aligned; optional expert source snapshot is absent rather than an undefined JSON field |
| gateway/agent-capabilities: actual backlog and complete bounded input | read-only certified next-batch preview with explicit unavailable/blocked semantics; native PA/expert long-source tail and exact string reconstruction | aligned; status queries leave progress unchanged and long input is readable through ordinary native tools |

### Uncovered Observable Behavior

No additional deliberate external behavior change was identified outside the four delta files. The four prior deviations were corrected in implementation without changing the contract. The new pagination metadata and page-completion summary implement the existing bounded-input/partial-result requirements.

Outcome: **aligned** at the reviewed implementation and deterministic evidence layer. This does not turn pending product scenarios into passed journeys.

1 critical issue (incomplete exit evidence), 4 warnings. Fix and finish the listed evidence before PR approval.

## Round 2 — targeted closure and evidence reconciliation

- `verification_mode`: targeted-closure, including the corrected-delta reconciliation above.
- `validated_at`: `c80a9337f3e1c6bd485723a093b6931bd0af0939`; `finding_origin_head`: `be1fec6c9075ffafe402c7387f3cde25546ae95d`; fix delta `7c1f71cd4..c80a9337f`.
- Additional test-only evidence at `671954c74` and `01c5088b7` was reviewed without expanding the frozen implementation range.
- `requires_full_verification`: false. All relevant Round 1 conclusions were retained and the actual shared-boundary fix effects were inspected.
- Code findings F1/F2/F3/F4: **closed**. Current implementation findings: **0 CRITICAL, 0 WARNING, 0 SUGGESTION**. Remaining C1 is an acceptance/complete-CI evidence hold, not a newly inferred implementation defect.

### Updated direct evidence

| Evidence | Result and what it proves |
|---|---|
| `/tmp/feat676-review-fixes.log` | 19/19 passed: stale-plan generation/file retirement, bounded source pages and scoped confirmation, Node hidden-tool selection preservation |
| `/tmp/feat676-ci-fixture-fixes.log` | 47/47 passed: affected control/config fixtures use the new default capability contract |
| `/tmp/feat676-provider-fix.log` | 3/3 passed: previously affected provider fixture |
| `/tmp/feat676-pa-dream-test2.log` | 2/2 passed: real native expert and PA Dreaming, PA authority refresh twice, staged writes, restricted actual request/tool set and host receipt; missing product bridge injection repaired |
| `/tmp/feat676-child-context3.log`, `671954c74` | 1/1 passed: one original native fork, three real requests, current bytes after manual correction, source pending notice, then generation-1 stale basis without current-entry injection |
| `/tmp/feat676-full-apply-recovery.log`, `01c5088b7` | 5/5 passed: original plan resumed from before-first-file, saved-body-before-run-receipt and saved-entry-before-checkpoint; no early cursor commit, same saved receipts/commits, no duplicate body or model rerun; no-increment follow-up does not call model |
| `/tmp/feat676-frontend-tests.log` | 1031/1031 passed; actual prototype screenshots and journeys remain product review evidence |
| `/tmp/feat676-ios-test.log`, `/tmp/feat676-ios-archive.log` | Native simulator test succeeded and Release archive succeeded; runtime TS compile is separately recorded |
| `/tmp/feat676-typecheck2.log` | Typecheck passed; caller reports c80 build passed. Precommit review-build installer SHA names its parent and is not substituted for the frozen implementation SHA |
| `/tmp/feat676-docs-check2.log` | Documentation integrity passed: 315 sources, 68 required routes |
| `/tmp/feat676-ruff2.log`, `/tmp/feat676-ruff-format2.log` | Ruff passed, all 95 checked Python files already formatted; independent AST comparison confirms both migration changes are formatting only |
| `/tmp/feat676-root-ci-final.log`, test-only descendant `b36053016` | Complete `pnpm exec vitest run --maxWorkers=2`: 158 files / 836 tests passed, 305.70 seconds; c80 product implementation unchanged |

The earlier root CI run included the unfinished child-test assertion reading nonexistent `request.system`; that assertion was corrected to actual request messages in `671954c74` and the narrow test passed. The subsequent complete root suite is green as recorded above; the earlier partial/failing run is not relabeled as a pass.

### Updated M1 coverage

- W1/F2: a large certified unit is exported in bounded pages, progress survives JSON serialization/restart state, complete-step cursor stays until the last page, exact joined source bytes match, and the later correction is reached. Existing live/cold/second-flush/pairing/revision/inherited-prefix evidence remains valid.
- W2/F1/F3: actual atomic library receipts are combined with reconstructed Dreaming/run/owner state at the three application boundaries. The completed-record replay protects cursor updates; the separate lost-atomic-receipt test still covers publication preceding receipt. Source invalidation remains conservative while ordinary edits reuse only same-generation unchanged versions. Actual original-child request delivery is now directly established.
- W3: targeted admission/cancellation evidence remains valid; no-increment provider/model non-call is now directly covered by the added recovery test. PA and expert native Dreaming both work after declaring product bridge injection. Other Skill/tool permissions remain unchanged.
- W4: actual root, original-child and maintenance requests are covered. These deterministic provider fixtures prove delivery and guards, not the model's understanding or every possible large-fragment extraction outcome. Product judgment remains with the independent product reviewer.
- W5: prior actual host receipt/native trajectory and PA Work projection evidence remains valid; no public-success notification is added by the fix delta. Real authorized Work/reopen validation remains a product journey.
- W6/F4: Node/UI retired-tool filtering is corrected, Web's full test gate and native iOS test/archive pass. Actual1280/390 prototype and pending/failure/effective comparison evidence is awaited from product review.
- W7: prior migration/dependency/Python evidence is unchanged, formatting/docs pass, and complete root CI is green. The final S01-S20 outcome matrix and any later test-only acceptance additions still control overall closure.

The final delta wording was also checked for the three current-spec contradictions identified during canonical preparation: historical Skill successes still retain reconciliation/cache-prefix semantics, in-flight protection no longer implies uncancellable Dreaming or active Skill maintenance, and inheritance no longer describes the new empty-context Dreaming execution. These are corrections to omitted same-scope contract text and match the existing design/implementation. Canonical incorporation is owned by the caller; the reviewer has not modified the delta or current specs.

### Current verdict

Targeted implementation verification: **pass**, all four focus findings closed and corrected delta **aligned**. Overall M1 verification remains **pending** solely for final independent product acceptance and its additional incomplete-input native evidence. Complete root CI is green. No spec/design edits were proposed or made to accommodate the implementation.

## Round 3 — S14 native evidence and optional status values

- `verification_mode`: delta; frozen head `b203c5823239e8c462ac1c88615e0f8ef9769450`; actual implementation delta from `b36053016` consists only of `MemoryDocuments.status` and `Dreaming.reviews` optional-field construction. Prior code and tests are not re-reviewed in full.
- Missing source state is now omitted from the status object rather than sent as an unsupported undefined value. This preserves the distinction between no authoritative snapshot and an authoritative empty allow set. Review metadata omits only absent fields; empty summary and timestamp 0 remain representable.
- `/tmp/feat676-incomplete-runtime2.log`: 2 files / 9 tests passed. The four native modes are `unread`, `partial-batch`, `failed-read`, and `normal-stop`. They reach the real normal-tool status renderer before and after maintenance, verify the exact persisted stream object does not advance, verify the original entry bytes remain unchanged and the run is failed with a complete-read/finish diagnostic. Incomplete-batch fixtures explicitly contain multiple input units.
- This closes the specific S14 deterministic delivery/guard evidence gap and checks the optional-result fix at the actual model-facing serializer. Existing root aggregate 158 files/836 tests at `b36053016` plus the affected 9/9 delta is reused; an additional full rerun is not required for the two object-construction changes.
- All three supplemental legacy contract changes in the same commit were checked against design/current implementation and remain **aligned**. They do not change runtime behavior.
- `issues`: []; `requires_full_verification`: false; corrected-delta outcome: **aligned**. Pending overall M1 evidence: final independent product acceptance and final-head build/typecheck result.
- Final-head build/typecheck were subsequently verified: `/tmp/feat676-build-status.log` completes with installer candidate SHA `b203c5823239e8c462ac1c88615e0f8ef9769450`; `/tmp/feat676-typecheck-status.log` completes all package/app checks. Both commands exited 0. Only independent product acceptance remains pending.
- Final `check:ios-runtime` passed (`/tmp/feat676-ios-runtime-final.log`) and documentation integrity passed (`/tmp/feat676-docs-prearchive.log`); these supplement the native iOS test/archive evidence rather than replace it.

## Round 4 — observed-backlog and native input readability closure

- `verification_mode`: delta; frozen head `5a123bae760d429c84bc2a3f72814009a69836f0`, actual delta from `b203c5823` limited to status preview/guidance and source-input serialization/guidance plus the corresponding existing native tests.
- S18's actual backlog is now available from a certified read-only source cut. `sourcesPending` remains eligibility only; `maintenance.backlog` separately identifies the next bounded batch and unknown/blocked ranges. There is no total-count promise and no cursor, dedup receipt or rotation commit from a query.
- S10's source JSON is no longer an unreadable long single line. Long strings are losslessly encoded as ordered short chunks and pretty-printed; the model receives explicit decoding/read-continuation rules. `ReviewFiles` continues to require complete actual read evidence, so the serializer change does not weaken finish or cursor gates.
- `/tmp/feat676-readable-tests.log`: 13/13 passed across native Dreaming, incomplete-input, recovery and scheduling suites. Both PA and expert source inputs exceed 6,000 characters; actual maintenance request messages retain the final source marker without line truncation and finish succeeds. Serialized input reconstructs the original string exactly. Failed/partial/no-finish modes retain pending backlog and identical before/after source streams.
- Prior full root 836/836, source, migration, UI and native iOS evidence remains applicable; new behavior is covered by this affected 13-test set rather than an unnecessary repeated full suite.
- `issues`: []; `requires_full_verification`: false; corrected-delta outcome: **aligned**. Current remaining overall evidence: final-head build/typecheck and independent product reacceptance.
- Final frozen-head `pnpm build` and `pnpm typecheck` subsequently passed (`/tmp/feat676-build-final-fixes.log`, `/tmp/feat676-typecheck-final-fixes.log`); the installer candidate names exact SHA `5a123bae760d429c84bc2a3f72814009a69836f0`. Only independent product reacceptance remains pending.
- Final complete root gate was subsequently rerun at the same 5a123 implementation: `/tmp/feat676-root-ci-5a123.log`, `pnpm exec vitest run --maxWorkers=2`, **159 files / 840 tests passed**, 292.03 seconds. Use this final aggregate instead of the earlier 836-plus-delta composition; the prior runs remain historical diagnostic evidence.

### Independent acceptance reconciliation

`acceptance.md` Round 2 provides the final actual-product reconciliation observed at this update. The verifier reviewed that evidence mapping without reenacting the journeys:

- S01-S09, S11, S13-S16 and S20 retain the independent reviewer's prior applicable pass evidence.
- S10/S12 now pass: the same persistent root spans actual windows; manual recovery `b9851fd9-d1dd-4260-81f6-ed666140f9da` completed 40/40 with source boundaries preserved, then a separate **automatic** run `fdc890cb-46e2-47b5-b0ab-9dd32821c3bc` began while the main work was still running and completed 10/10. The files and Work distinguish actual results, missing receipts and later facts. The manual run is not used as automatic admission evidence; earlier failure/cancellation history remains visible.
- S18 now passes: the real N3 answer names observed pending backlog, next-batch scope, exact source range and budget block; it does not conflate eligibility with backlog or historical receipts with new saves. Automatic completion produced Work history without an extra public reply.
- S19 now passes: the real expert consumed document-only, legacy-only and document-only markers in the respective file modes, preserving the expected stale-basis caveat for uncheckpointed manual text. Existing backup/import evidence remains valid.
- S17's feature/Skill/manual semantics pass, but the approved1280/390 reference contract also requires the real **saved but not yet effective** state. The reviewer captured Saving/disabled buttons, a409 retained draft, successful applied state and offline read-only state; neither attempted isolated pause proved an actual persisted pending operation. Thus S17 remains **inconclusive**, not an implementation failure or a passed must-match.

Current remaining issue: **C1 (narrowed to W6/R5 pending-state evidence)**, one unmet explicit exit criterion at `design.md:230-232,274`. Complete the real persisted-but-unconfirmed state observation and link its actual operation/state plus screenshot; filenames or Saving… alone do not prove it. All previously listed C1 mechanism/CI/model gaps have been closed by the evidence above.

Current verdict: targeted implementation **pass**; corrected-delta **aligned**; overall M1 **fail / awaiting one explicit UI exit-criterion evidence**. Current counts: 1 CRITICAL evidence hold, 0 WARNING implementation issues, 0 SUGGESTION. This does not assert a new product defect and does not authorize silently weakening the approved must-match.

## Final M1 closure

Independent acceptance `8b28b00dd` completes the final reference requirement without changing product code. The isolated transparent WebSocket proxy delayed only the original node configuration apply/status frames; it neither altered UI nor fabricated responses. Actual operation `d67ed387003b486ea12a54f4e739079f` remained pending while the390 page displayed Save awaiting confirmation, last confirmed state, Refreshing/Read-only and Confirming save/Draft retained. Releasing those frames produced the real v4/off applied state at03:17:24, with the waiting notice removed, editing restored and No changes. The verifier viewed `/tmp/nano-feat676-review/ui390-confirmation-pending.jpg` and `ui390-confirmation-applied.jpg`; these match the report. The earlier ineffective SIGSTOP attempt and Saving-only images are explicitly excluded as pending evidence.

**C1 is closed.** The independent product outcome is now S01-S20 **20/20 pass**, A1/A2 closed, no pending acceptance issue. No historical failed run is relabeled as successful, manual recovery is not substituted for automatic execution, and no source failure is interpreted as empty backlog.

| Final criterion | Disposition / retained evidence |
|---|---|
| W1 | pass: certified live/cold cuts, two flushes, own paired prefixes, fragments/revisions/dedup, persisted bounded continuation and later-source progress; actual same-root cross-window automatic journey |
| W2 | pass: native atomic third-version/Git/lost-receipt protection; reconstructed plan recovery before-first/after-body/after-entry; no early cursor, original-child current/pending/revoked request capture and actual correction/stop-use journeys |
| W3 | pass: injected scheduler, idle/no increment, pause/off/resource deferral and cancellation; document/legacy exclusivity; fixed creator selection and real foreground create/reload; paused automatic Skill maintenance |
| W4 | pass: actual root/child/PA+expert maintenance requests and tool results, long-source complete-read/finish and incomplete-input rejection; independent real model consumption and source-boundary behavior |
| W5 | pass: authorized native maintenance trajectory/host receipt projection; actual Work partial/success/reopen and quiet automatic completion |
| W6 | pass: reference comparisons at1280/390, creation/legacy/Skill controls,409 draft preservation, real pending→applied closure; shared config plus native iOS tests and Release archive |
| W7 | pass: synthetic migration bytes/hash/permissions and seven write interruption/reentry points, live mode/import journeys, final root159 files/840 tests, Web1031 tests, native iOS/runtime, Python124, exact-head build/typecheck, format and docs gates |
| R1-R5 | pass: independent `acceptance.md` final S01-S20 matrix and specific source/message/Work/UI locators; deterministic failure mechanisms remain separately identified |

Final `verification_mode`: targeted-closure/delta with retained full coverage; `verdict`: **pass**; `issues`: []; `validated_issues`: F1/F2/F3/F4/C1 closed; `requires_full_verification`: false; corrected-delta `outcome`: **aligned**. The validated/effective implementation range remains the fields at the top; subsequent report/canonical/archive-only changes are caller-owned retained documentation deltas.

All checks passed. Ready for PR.

## Delivery retention — caller closeout

Final fetch retains `origin/main=6b4213c205db04adcebc950fe539a5a759e57391`; no upstream delta invalidates the gates. The range `5a123bae760d429c84bc2a3f72814009a69836f0..1681feb40251451c4f8a276003d5fc78b94d3ad2` contains only the three independent reports. Subsequent delivery changes merge the reviewed four delta-specs into canonical requirements, update their indexes and move this complete unit to archive; product code and tests remain identical to the validated implementation. All three gate conclusions are retained for that documentation-only delivery suffix; the PR records its exact effective-through head.

The final implementation has a complete 159-file / 840-test TypeScript pass, 1031 Web tests, 124 Python tests, native iOS tests and Release archive, build/typecheck, packaged iOS runtime check and Ruff passes. Canonical and archive integrity are checked separately after the move. Local test processes, IM listener, gateway/runtime and temporary configuration-delay proxy have been stopped; ports 65225/62264 and the owned tmux session are released. Runtime data and evidence remain local for audit, and the development worktree is retained for the unmerged PR. No production deployment or merge was performed.

## Round 5 — PR #428 native trajectory identity delta

- `verification_mode`: delta / targeted closure of the observed Dreaming native-viewer failure.
- `executed_base`: `c1eea6beb6c2ec4e47cb4bb73b8c6d8b5778a689`; `validated_at`: `e207a51b6e8313083cff05ccebfcca7196b8653d`; main baseline `6b4213c205db04adcebc950fe539a5a759e57391`.
- `requires_full_verification`: false. The seven-file delta is confined to Dreaming identity setup/recovery, the dependency declaration, two existing test files and design/deployment clarification. No spec files changed: **no spec delta**. The existing canonical contracts already require native execution details, cold readability, read-only access and separation from the model's child-management directory.
- Prior W1-W4/W6-W7 and unrelated product evidence remain applicable. Prior W5/S18 claims based only on Work summaries and reopening are insufficient for the reported native-viewer path; their native-entry portion is superseded by this round and the independent product reacceptance. The earlier final M1 signoff must not be read as proof that the reported native entry worked.

### Completeness, correctness and coherence

| Dimension / contract | Implementation and direct evidence | Result |
|---|---|---|
| New maintenance identity; `docs/specs/im/agent-work.md:203-211`, design `:278-284` | `dreaming.ts:223-226,296` appends the public one-shot/native descriptor during setup; locked DSH durably stores setup events before `agents.create` resolves. Native expert and PA DTOs expose prompt, finish and host receipt, with identical warm/cold snapshots (`dreaming-runtime.test.ts:41-60`). | aligned |
| Recorded old runs retain their actual history; same cold-read contract and deployment supplement | `dreaming.ts:340-373` uses public persistence write ownership, validates exact ID/origin/parent/no inherited prefix, appends missing metadata only and flushes before the durable marker. Recovery assertions preserve every original event, next sequence, original failure/receipt state and repeat-run result; wrong parent rejects without writing (`dreaming-recovery.test.ts:95-121`). No model or memory-write path is called by identity repair. | aligned at implementation / deterministic recovery seam |
| Hidden maintenance remains outside managed children; `docs/specs/gateway/agent-capabilities.md:994-1008` | Descriptor events have no model surface operation. Actual captured native requests preserve the restricted prompt/input/tool set and omit the descriptor; both pre/post-restart descendant queries return `[]`. Catalog publication and normal model delegation code are unchanged. | aligned |
| Architecture and startup ownership; `SPEC.md:7,49-54` | Only integration imports declared public DSH exports. `KnowledgeRuntime` injects `sessionPersistence` (`runtime.ts:37`) and recovery precedes normal initialization (`index.ts:323-324`). No DSH patch, private runtime dependency or viewer bypass. | aligned |
| Design and test coverage | The appended design/deployment text describes the actual creation and one-time backfill strategy. Existing native-runtime and recovery files were extended at their respective observable seams; prior source, receipt, scheduling and incomplete-input protections remain. UI prototype/reference contracts are unchanged and outside this delta. | complete for this implementation delta |

The code review above includes Agent Context Implementation Review. This verifier reuses that check: the relevant delivered prompt/tools, model-hidden metadata and catalog boundary were inspected in combination. There is no implementation deviation from design and no newly identified design defect. Deterministic provider requests do not establish real-model understanding; no prompt or tool semantics changed that would require a new understanding experiment.

### Evidence reconciliation

- The original error is a real native-path regression: `/tmp/feat676-trajectory-red.log` records **2/2 failures**, both `subagent descriptor is corrupt`.
- Independent rerun at the fixed candidate: `pnpm exec vitest run packages/dsh-integration/tests/dreaming-runtime.test.ts packages/dsh-integration/tests/dreaming-recovery.test.ts --maxWorkers=2`, **2 files / 9 tests passed**, 8.64 seconds, `/tmp/feat676-trajectory-independent-review.log`. This covers both PA/expert warm and restarted DTOs plus all seven recovery tests.
- The older `/tmp/feat676-trajectory-green2.log` sequence assertion failure and `/tmp/feat676-trajectory-regression.log` header-fixture failures remain failed diagnostic runs. The corrected source now derives the sequence from the preserved prefix and creates a valid public Session header; `/tmp/feat676-trajectory-recovery3.log` and the independent 9/9 rerun confirm closure. The other four files in the regression log passed **16 tests** and remain applicable.
- Package typecheck is green in `/tmp/feat676-trajectory-typecheck.log`. Final caller-run logs were independently read: `pnpm exec vitest run --maxWorkers=2` passes **159 files / 842 tests**, 300.29 seconds (`/tmp/feat676-trajectory-full-ts.log`); dependency contracts pass **13/13** (`/tmp/feat676-trajectory-dependencies.log`); docs integrity passes **281 maintained sources / 68 required routes** (`/tmp/feat676-trajectory-docs.log`). The old 840-test aggregate remains historical evidence and is superseded for this candidate.

### Current verdict and limits

`verdict`: **pass** for the targeted implementation verification; `issues`: []; **0 CRITICAL, 0 WARNING, 0 SUGGESTION**; `outcome`: **aligned**; `requires_full_verification`: false. No additional observable behavior requiring a spec delta was found.

The remaining independent product task is actual S18/native-viewer reacceptance, including opening an existing pre-fix run through the authorized product UI, inspecting real prompt/tool/host details and reopening after restart. This report's controlled old-run recovery test is not substituted for that upgrade/UI journey. The product reviewer owns its outcome; the historical 20/20 matrix is not carried forward as unconditional post-fix native acceptance. No production service, configuration or implementation file was changed by this reviewer, and the test-created isolated homes/processes were cleaned by their fixtures.


## Round 6 — PR #428 guidance cleanup delta

- `verification_mode`: delta; `executed_base`: `8fef02de95451334567c5d7c1f4c2edb7ed8fa8f`; `validated_at`: `d572ad78bc216fd9347bf6922e5c42171c22afba`. The candidate was frozen and HEAD matched at verification start.
- Scope: four files / six replaced lines of model-facing guidance. User intent is removing redundant permission reminders, old background-Skill explanation, Codex migration commentary and the memory/scheduler aside. This review does not reopen the complete unit or mutate source/spec/design/tests.
- `requires_full_verification`: false. **No spec delta**: current operation, scope, receipts, source/identity boundaries and Task/Dreaming lifecycle remain unchanged. Canonical requirements do not require these removed sentences to be repeated in model instructions.

### Completeness, correctness and coherence

| Contract / requested outcome | Implementation and evidence | Result |
|---|---|---|
| Remove the specified surplus guidance while retaining usable memory consumption; `agent-capabilities.md:1022-1031`, design's short-system-guide / detailed-Skill split | `document-memory.ts:44` now gives the direct file-tool and `nano-memory` entry. Adjacent fixed owner/role, current-page/version/checkpoint and missing-tool instructions remain. `nano-memory/SKILL.md:9-47` still supplies the complete relevant read/edit/entry/exclusion workflow. | aligned |
| Foreground Skill creation remains discoverable and operational; `agent-capabilities.md:885-895,1063-1075` | `skill-creation.ts:9` retains discovery, evidence, constraints and writable scope. `skill-creator/SKILL.md:124-173` retains actual Nano tool names/arguments, unavailable-tool response and actual write/partial-result receipts. Deletions remove explanations rather than a required operation or resource. | aligned |
| Task/authorization and Dreaming boundaries remain distinct; current document-memory and Dreaming requirements `agent-capabilities.md:1022-1047` | The short guide still says memory is not authorization, Task state or live permissions. Detailed memory boundaries retain source/disclosure constraints and the staging/private-finish/no-Skill rule. No scheduler, permission check, tool restriction or lifecycle code changed. | aligned |
| Relevant Context is actually delivered and coherent after both Skills load; M1 W4 | Reused this reviewer's Round 6 Mode B inspection in `code-review.md`: three real native pre-adapter requests contain new short guidance; the next requests contain actual `skill` results for both current bodies, with useful missing-tool/receipt instructions. Every removed sentence/fragment is absent in all three records. | complete at controlled native-delivery seam |
| Architecture, native trajectory/recovery and existing UI/reference contracts | Four-file diff contains wording only; no dependencies, schema, visibility, lineage, viewer or UI implementation changes. Prior 842-test runtime aggregate and separate actual native UI/cold-read acceptance remain applicable within their original scope. | unchanged / retained |

### Evidence and limitations

- Direct evidence: `/tmp/feat676-prompt-cleanup/probe.mjs`, `/tmp/feat676-prompt-cleanup/result.json`, `/tmp/feat676-prompt-cleanup/runtime/requests.jsonl` records 1–3. Exact message/field locators and configuration are in the Round 6 code review. The probe uses the real native runtime and real `skill` execution with deterministic `llm/stream` responses; it proves assembled delivery **before provider adaptation**, not wire delivery, autonomous choice, real-model interpretation or successful memory/Skill writes.
- Caller-provided candidate validation, not independently rerun: `pnpm --filter @nano/dsh-integration build`; `pnpm exec vitest run packages/dsh-integration/tests/cron.test.ts packages/dsh-integration/tests/capabilities.test.ts packages/dsh-integration/tests/dreaming-runtime.test.ts`; exit 0, **3 files / 9 tests**, 10.98 seconds, 2026-10-29 10:45:21 Beijing start. Stdout was not saved to a log. Caller also reports docs integrity **281 maintained sources / 68 routes**, archive check and diff check passing.
- Per `testing.md`'s stable observable-seam rule, ordinary wording is not promoted into a permanent string-match test. Existing native capture and affected regression evidence suffice for this delta; no service or full-suite rerun was performed by this reviewer.
- No implementation departure from design, newly identified design defect or omitted behavior requiring a spec delta was found. Real-model understanding of this wording was **not newly tested** and is not inferred from controlled calls. This narrow cleanup does not invalidate the prior model/product evidence for unchanged mechanisms.
- Historical evidence is preserved: `acceptance.md` Round 3 at the base records actual old/new native trajectories, authorized restart/cold reads and the non-blocking T1 prompt observation. It supplies the previously separate S18 reacceptance; this verifier inspected that report, did not reenact its journey and does not turn T1 into a cleanup finding.

Round 6 `verdict`: **pass**; `issues`: []; **0 CRITICAL / 0 WARNING / 0 SUGGESTION**; `outcome`: **aligned**; `requires_full_verification`: false. Prior unit evidence remains scoped as recorded. Only these two reports were edited; no product code, service or configuration was changed by this reviewer.


## Round 7 — R8 full verification (2026-10-29)

- `unit_id`: feat-676; milestone: M1-role-memory-dreaming.
- `verification_mode`: full; `review_round`: 7.
- `validated_at`: `6205cc5794ad6efab00cd144b61e3b2f9eefa09d`.
- `executed_base` / `effective_base`: `80db8b9a6`; `effective_through`: `6205cc5794ad6efab00cd144b61e3b2f9eefa09d`.
- Design authority: approved R8 at `452e26373`, with the candidate's native-identity supplement and historical capability delta reconciled below.
- `requires_full_verification`: false (this round already covers the full R8 implementation; fix closure must cover its actual shared-source/recovery impacts).
- `verdict`: **not ready / implementation-mismatch**. Current counts: **1 CRITICAL evidence/exit-criterion gap, 2 WARNING confirmed implementation defects, 1 SUGGESTION documentation defect**. CRITICAL below records missing current acceptance, not a proven model/product failure. Prior passes are historical; they are not the current result.

### Completeness and correct scope

The implementation increment has the intended single writer, two source paths, frozen continuous batches, per-task extraction/replacement cache, bounded business-history/IM recovery, fixed shared package and offline protocol conversion. No additional runtime, DSH private import, PA/IM DSH dependency or parallel knowledge writer was found. The reviewer changed only the two assigned reports and did not start production or alter implementation/tests/configuration/design.

M1's implementation mechanisms are substantially present, but M1 cannot exit yet: the confirmed findings below affect W2 and W4/W8/W10/W12, and the revised independent product/real-model criteria have not been supplied as current passes to this verifier. The full CI was explicitly left to the caller. Old acceptance stays valid only where its exact unchanged condition still applies; it cannot certify the redesigned behavior by inheritance.

### Correctness — requirements and scenarios

| Requirement / scenarios | Implementation and direct evidence | Current disposition |
| --- | --- | --- |
| Role/audience and complete document consumption, S01-S04/S08-S09 | document-memory.ts role/context/version handling, memory-documents.ts basis/receipts; role layout and final consolidation prompt; unchanged original tests in the expanded run | Mechanisms retained; changed source provenance has F-R8-2 below; no new autonomous audience/semantic pass claimed |
| Sole Dreaming writer/current correction, S05-S07 | document-memory.ts execution rejection and read-only injection; memory_maintenance routes manual/import through Dreaming; independent native requests 1/2/5 show current guidance | Aligned structurally; affected real root/child correction and later consumption remain product-review work |
| Continuous qualified history, S10-S14/S21 | memory-sources.ts freezeTarget/freeze/commitSourceRange; dreaming.ts continuous loop and fresh retry target; memory-sources and cycle runtime evidence | Aligned batching/cut/continuation mechanisms; source-envelope projection loses required metadata (F-R8-2) |
| Partial/restart/Git, S15-S16 | dreaming.ts prepare/finish/application receipts, memory-documents.ts apply; recovery native tests | Version compensation fails after retention expiration (F-R8-1) |
| Auto/manual/lifecycle/quiet Work, S17-S18 | tick/start/stop/configurationChanging and maintenance trajectory registration/publication; scheduler/runtime/PA/IM expanded regressions | No new static mismatch; R8 Work/native reacceptance is distinct from old S18 history |
| Old-data migration, S19 | migrate_dreaming_protocol.py retains initial activation, successful cursors, source qualification/receipts; retires old JSON plans/offsets; protocol-2 guard, separate legacy migration | 14 migration tests reused; no migration or production run performed by verifier |
| Source withdrawal, S20/S26 | generation/status/exclusions, request assembly + tools + apply checks; invalid summary sourceVersion/generation forces re-extraction | Mechanism present; current model recovery/stop-use behavior still requires revised product evidence |
| Task summaries, S22-S25/S30 | memory-sources.ts children own baseline/inherited-source matching/budget; dreaming.ts extraction cache, replacement/no_signal and integrated version tracking | Native controlled journey supports extraction→failed consolidation→reuse→continuation replacement→no_signal; does not prove autonomous understanding |
| Business history/own recovery, S27-S28 | dreaming-history.ts directory, lineage, qualification/cut before createHistoryView, scoped cursor; dreaming-agent.ts restricted setup; shared rc.6 | Independent 14-test narrow run plus native delivery; real-model omission→query→correct conclusion and own-window recovery not yet accepted here |
| Read-only IM supplement, S29 | dreaming-history.ts original parent actor, directory + activation/cutoff; global-agent.ts dedicated product route; work.ts version-qualified read/search without source-read side effects | Static and supplied unit/integration evidence aligned; actual IM read/search/Inbox unchanged-state product evidence remains separate |

### Coherence — W1-W13 and evidence depth

| Exit criterion | Implementation / evidence reviewed | Status and limit |
| --- | --- | --- |
| W1 certified native source cuts | memory-sources.ts live first flush → immutable observation → second flush; cold revision, pairing, baseline/identity; source tests in 307 run and independent narrow rerun | Mechanism covered; original-source rendering problem separately F-R8-2 |
| W2 single writer, atomic apply and crash/Git recovery | document-memory.ts; memory-documents.ts apply/checkpoint; dreaming.ts staged plan and recover | **WARNING F-R8-1**: cleanup destroys a still-recoverable completed run's staging |
| W3 scheduling/configuration/Skill pause | tick/start/stop and unchanged feature/capability/Skill selection paths; expanded scheduler, knowledge and PA suites; old fixed-creator UI evidence only for unchanged controls | No additional static mismatch; does not re-certify all current true-model Skill behavior |
| W4 actual Context and behavior | independent root/consolidator native request capture in code-review Round 7; supplied native task-extraction fixture; tool schemas/restricted assembly | Assembled pre-adapter delivery checked; **WARNING F-R8-2** information loss; revised provider-wire/real-model behavior pending |
| W5 Work/auth/receipts/quietness | reviews/publish/maintenance trajectory, PA Work and IM tests in expanded run | Static/native mechanisms covered; current product Work results not inferred from test counts |
| W6 UI/reference/iOS | R8 code increment has no Web/iOS source change; the two UI controls and save/apply structure retain prior evidence; current delta changes the meaning of turning off Dreaming to read-only/current response/manual Dreaming | No new UI mechanism defect; no new screenshots or iOS compile claimed; final inherited-evidence accounting remains caller-owned |
| W7 migrations/builds/contracts/docs | implementation-r8.md paths; 14 migrations and 27 migration+architecture tests; whole build/typecheck supplied; own .venv docs-check passes 327 sources/68 routes | Available local checks pass; current full CI and final S01-S30 matrix not yet supplied to this verifier |
| W8 continuous batches/long human text | freeze pagination at Unicode characters and original message hash/ID; successful range commit/fresh target after failure; source/cycle fixtures | Mechanism covered; **F-R8-2** continuation omits original envelope metadata |
| W9 inherited background/child replacement | children authenticates actual parent copied records, baseline/time/cut and source identity; cache version includes own/inherited/generation; deeper children only bounded recovery | Deterministic and native controlled support; autonomous inherited-condition handling pending |
| W10 two-stage failure/partial input | summary cache only valid matching version/generation; extraction success distinct from integration; pending summaries omitted for capacity remain unintegrated; input prepared/hash checked | Two-stage mechanism covered; **F-R8-2** affects actual Inbox provenance; changed real-model cases pending |
| W11 protocol conversion | explicit offline script + stopped-writers flag/backup/planned replacements; old plans retired; existing protocol-2 progress not reset on completed rerun | 14 migration checks reused, including unreported child activation boundary; no runtime migration compatibility branch introduced |
| W12 original prompts/content dimensions | fixed Codex originals and prompt-adaptation.diff compared with final dreaming-prompts.ts; provenance/LICENSE/NOTICE packaged; Muse dimensions land in current role layout | Source fidelity/adaptation reviewed; **F-R8-2** removes needed input conditions; autonomous long-term understanding/feedback/preferences pending |
| W13 shared history + bounded IM | public rc.6 root export createHistoryView, fixed release URL and lock integrity; source_history directory/query/identity/cursor; own history stays archived-current-session; PA/IM bounded product route | Narrow 14 tests and native delivery support structure; shared release not misrepresented as GitHub immutable; actual real-model query/restore + IM no-side-effect journey pending |

Supplied local results were checked at their locators: `/tmp/feat676-expanded-tests.log` **68 files / 307 tests passed**; `/tmp/feat676-migration2.log` **14 passed**; `/tmp/feat676-python-pre-review.log` **27 passed**; `/tmp/feat676-native-no-signal.log`, `/tmp/feat676-cycle.log`, `/tmp/feat676-history3.log`, `/tmp/feat676-full-build.log`, `/tmp/feat676-typecheck-pre-review.log`. They are implementation-owner evidence, not independently rerun full CI. Independently executed: `/tmp/feat676-static-r8-narrow.log` **2 files / 14 tests passed**; `.venv` docs-check `/tmp/feat676-static-r8-docs.log` **passed**; both actual lower-seam reproductions `/tmp/feat676-static-r8-repro.json`.

### Prototype / Reference and delta reconciliation

The reference contract in design requires no Memory/creator toggles, document Dreaming only, save-vs-applied state and real Work partial-result semantics. R8 retains UI implementation and changes backend behavior; code inspection does not invalidate the unchanged reference screenshots, but no fresh visual or true-product pass is asserted by this static verifier.

The four active delta files agree with the intended R8 single writer, current-conversation correction plus later durable persistence, source withdrawal, continuous sources/task replacement and business-vs-own history distinction. The candidate's additional historical-Skill-cache, capability-protection and maintenance-directory clauses preserve existing contracts; they do not restore automatic Skill forks. The native-identity design supplement matches the public descriptor append/repair implementation and introduces no second business source.

Current canonical specs in this unmerged unit branch still contain the earlier implementation's foreground-write wording (for example agent-capabilities.md's immediate body/entry correction). The active delta correctly supersedes it for the target. That is a required final canonical reconciliation after gates, not justification to change implementation to the obsolete writer model or silently proclaim the unit complete. No additional uncovered observable behavior was found beyond the reported implementation mismatches. Current reconciliation outcome: **implementation-mismatch**.

### Issues

#### CRITICAL — current milestone evidence / exit criteria

- **V-R8-1, current R8 acceptance remains open (CONFIRMED evidence gap, not a confirmed model failure).** design.md:393 and the S21-S30/affected S05-S20 contracts require actual requests, independent product behavior and final scenario accounting. The supplied implementation report labels its single synthetic model journey a self-check and explicitly says independent acceptance/wire capture remain pending. Old passes at other snapshots cannot satisfy the revised requirements. Action: caller completes the bounded independent product/real-model and full-CI work already assigned, attaches exact candidate/session/request/response and actual resulting state locators, and reconciles retained old evidence only for unchanged conditions. No extra production exercise is requested.

#### WARNING — confirmed implementation mismatches

- **F-R8-1 / code-review Round 7 finding 1 (CONFIRMED).** dreaming.ts:351-352 cleans completed runs even when saved/versionRecorded=false still requires their staging at line 297. Real recovery reproduction deletes the file and produces ENOENT for the next application. Violates design section 6's retention of pending-recovery materials and S15/S16/W2. Preserve outstanding compensation material and verify expiration→compensation→new-work behavior at the existing recovery seam.
- **F-R8-2 / code-review Round 7 finding 2 (CONFIRMED Context interface defect).** memory-sources.ts:63 and 77-80 discard the Inbox outer target/delivery/name/type/channel envelope in rendered and continued material. This contradicts design section 4.4's historical chat and participant/observer provenance, and W4/W8/W10/W12. Preserve the envelope through the actual readable projection; verify the rendered native input, not only the intermediate JSON. Failure mechanism, expected/observed Context, impact, evidence and limitations are in the corresponding code-review finding.

#### SUGGESTION

- **D-R8-1 (CONFIRMED).** spec.md:156-157 uses archive-depth ../../../../packages links from the active unit; three cited files resolve outside the repository and are absent. Restore ../../../packages for this active path. The independent docs-check passes its own maintained-source scope and does not refute this direct path check.

### Context evidence and final disposition

Reuse code-review Round 7's Mode B review: fixed-source provenance, final prompt/Schema assembly, generation invalidation, original history/IM identity/cut, cached summary replacement and staging application were traced together. `/tmp/feat676-static-r8-context/requests.jsonl` records 1/2/5 show root guidance; 3/4 show consolidator input/directory/tools and finish result in the following request. This is actual native assembled delivery with controlled llm/stream, not provider-wire or autonomous model consumption. The preliminary real-model self-check remains labeled as such and has not been relabeled as independent acceptance.

Two WARNING defects require implementation fixes; one CRITICAL acceptance gap requires the caller's remaining evidence. The documentation suggestion is low priority. No new review loop is warranted without an actual fix/evidence delta. The report's fixed validated/effective scope is unchanged by this report commit or concurrent caller documentation edits.


## Round 8 — R8 targeted closure at eff2d4684 (2026-10-29)

- `unit_id`: feat-676; `verification_mode`: targeted-closure/delta; `review_round`: 8.
- `validated_at`: `eff2d4684cc396824ae65943f485a9ba66175111`; `executed_base`: `b8069b23892d035e67aa0695ae150a9a864e4265`; findings originated at `6205cc5794ad6efab00cd144b61e3b2f9eefa09d`.
- Effective full-plus-closure implementation range: `80db8b9a6..eff2d4684cc396824ae65943f485a9ba66175111`.
- `requires_full_verification`: false. Round 7's unaffected implementation/design mappings remain effective; this round checks only the actual fixes and accompanying strings/documentation.
- **Targeted implementation outcome: aligned. Named findings F-R8-1/F-R8-2/D-R8-1 are closed. Overall milestone verdict: still not ready pending current independent product acceptance.** Counts: **1 CRITICAL evidence/exit-criterion gap retained, 0 WARNING, 0 SUGGESTION**. The retained gap is not a confirmed model failure.

### Closure mapping

| Focus / affected criteria | Candidate implementation | Evidence and result |
| --- | --- | --- |
| F-R8-1; S15/S16/W2 | recover retains completed-run staging while any saved receipt awaits version recording; normal cleanup resumes after compensation | Existing recovery test uses a real Git index.lock and actual files, succeeds through expired recover/start compensation, then cleans after success; independently passed at Node 24.22.1. **closed** |
| F-R8-2; source-provenance portions of W4/W8/W10/W12 | Normal rendered message bodies retain non-messages envelope; Unicode continuation segments each retain the same envelope while message fields stay separate; Global and child share the rendering path | Direct-render test and the existing original-message Unicode traversal assert target/name/observer/type/channel in actual text. Independent built-candidate rendering also preserves all five tested identity fields. **closed at deterministic Context interface seam**; autonomous model consumption remains separately pending |
| D-R8-1 | Three active-unit implementation links use ../../../packages | Direct path resolution confirms all exist. **closed** |
| UI prototype R6 explanation delta | Web English/Chinese and native iOS accurately describe reading existing memory and explicit manual organization with automatic Dreaming off | Literal-only diff matches design's sole writer and switch semantics; owner UI **28 passed**, Web build passed. No new control or save/apply change. True-page R6 closure remains owned by the in-flight product reviewer |
| Fixed-upstream evidence supplement | implementation-r8.md records phase1/phase2/storage/workspace/locking source reading and Nano differences; source README replaces stage_one.rs with phase1_output.rs | Reviewer verified the corrected files at the fixed source commit; the source-reading account is owner evidence, not a claim this verifier repeated the upstream investigation. No prompt/runtime delta or new spec change |

Independent command/result: source+recovery narrow tests **20/20 passed**, `/tmp/feat676-static-closure-eff2d.log`. Reused owner red/green/build evidence: `/tmp/feat676-review-red.log`, `/tmp/feat676-review-node24.log` (**26/26**), `/tmp/feat676-review-build-node24.log`; UI results `/tmp/feat676-review-ui.log` and `/tmp/feat676-review-ui-build.log`. These provide appropriate targeted regression coverage for the two fixes. The delta does not require a new full review or new spec language to justify the implementation.

### Remaining current gate

**V-R8-1 remains open.** The product reviewer is in flight. This snapshot has no final independent S01-S30/retained-scenario matrix and accompanying current real-provider/model behavior conclusion supplied to this verifier. Earlier source/Wire/true-behavior limitations are not closed by the deterministic regression, the source-inspection narrative, or the UI unit test. The caller has additionally recorded local full-suite/build/typecheck/iOS-runtime/Python results for the original 6205cc579 candidate; those improve available local validation evidence but do not constitute a remote CI pass or replace the revised independent product gate. Reconcile the final bounded evidence when it arrives; do not rerun unaffected mechanisms merely to fill a checklist.

Current corrected-delta reconciliation: **aligned for the reviewed fixes**, with no newly uncovered observable delta; overall M1 still **incomplete solely on its outstanding evidence/acceptance criterion**. The two CONFIRMED implementation WARNINGs from Round 7 are closed. Code-review Round 8 contains the corresponding Mode B Context repair evidence and scope limits. Only the assigned two reports were appended; implementation, tests, design and production were not modified by this verifier.


## Round 9 — final R8 acceptance/evidence closure (2026-10-29)

- `unit_id`: feat-676; `verification_mode`: targeted-closure/delta; `review_round`: 9.
- `validated_at`: `5432c125ad33ec163515dc25acd663da972b3796`; `executed_base`: `5ef3bbf960c053629a51830cfc03aa19389a5530`.
- `effective_base`: `80db8b9a6`; `effective_through`: `5432c125ad33ec163515dc25acd663da972b3796`. These fields describe the R8 full-plus-closure scope; prior unchanged implementation coverage stays in the earlier scoped records. Product implementation remains eff2d4684; approved design authority remains R8@452e26373.
- `requires_full_verification`: false; `verdict`: **pass**; corrected-delta `outcome`: **aligned**.
- Current verifier issues: **0 CRITICAL / 0 WARNING / 0 SUGGESTION**. F-R8-1/F-R8-2/D-R8-1 remain closed; **V-R8-1 is closed** by current independent acceptance and the bounded evidence below. Product acceptance separately remains pass-with-issues because historical T1 is an explicitly retained, non-blocking side finding (not reproduced/fixed in R8).

### V-R8-1 evidence reconciliation

| Previously open requirement | Current evidence reviewed | Disposition / exact strength |
| --- | --- | --- |
| Revised independent scenario accounting and actual product behavior | acceptance.md Round 4, commit 5432c125a: all **30 unique S01-S30 rows** map to real-model, controlled-mechanism or explicitly unchanged retained evidence; actual PA correction/child follow-up, expert audience/negative outcome, source exclusion then Dreaming cleanup and live Work/UI results | **closed**. Revised foreground-only-read behavior is not passed via obsolete writer acceptance. Product reviewer reports 0 blocking/major and no new minor; T1 remains separate |
| W4/W12/W13 source missing-condition delivery and model action | S27 initial partial input has no K-47/K-74; actual adapter request contains autonomous source_history search/read, same original root/window/item and appendix result; saved project/entry and actual host 2/2 saved+versioned inspected | **closed at representative real-model consumer depth**. It proves this real missing-condition recovery, not all future model behavior or downstream shared-proxy conversion |
| W8 continuous source completion and truthful partial state | runs-snapshot.json: same cycle 93043ffd-1a4d-4365-9a27-0b26df788021, four completed batches 3cfbfeba/7b7bebfd/d9fd3d7b/fd6b391a, actual 0/0 → 2/2 → 0/0 → 2/2, final range reaches frozen through=69 without pending-source text | **closed**. The earlier 2/2 host receipt still correctly reports a remaining source; it is not misrepresented as whole-cycle completion |
| W13/S29 real IM product entrance and read-only effects | New test 86886b9c6 uses actual IM process, device binding/authenticated relay, real GlobalAgent and stores; pagination/read/info, original IDs and before/after database/Inbox/journal equality; withdrawal rejects old cursor | **closed at actual cross-process product mechanism**. Owner and independent product reviewer each ran 1/1 pass. Caller is controlled; no autonomous model IM choice claimed |
| S28 context-window recovery/task lifecycle | Round 4 accurately retains native request-controlled notes/new_context/own-history/source_history and task extraction-reuse/replacement/no_signal evidence | **closed at design's deterministic boundary depth**. It is not called autonomous model choice to change context |
| S01/role memory consumption | PA nonempty Global cross-chat actual response preserves current corrections, original-link provenance, audience restriction and unknowns; expert actual document read plus subsequent correct condition judgement is a separate observation | **closed without stronger recall claim**. PA result is not an empty-context memory-only recall test |
| W6 current explanatory UI/native compilation | Current 390 Web explanation and Work evidence in independent acceptance; iOS Simulator `/tmp/feat676-ios-r8-build.log` ends BUILD SUCCEEDED; previous targeted 28 Web tests/build retained | **closed for explicit contract**. No new iOS visual acceptance claimed |

The verifier inspected the actual S27 proof/request/result/memory/host/run locators rather than only its summary: `/tmp/feat676-r8-product/s27-source-history-proof.json`, `/tmp/feat676-live-evidence/68981408217c48c39483d4b8bdd5ecd4-request.json`, `s27-saved-memory.json`, `s27-native-receipt.txt` and `runs-snapshot.json`. S29 actual process assertions and helpers were inspected; `/tmp/feat676-r8-product/s29-process.log`, `s29-mechanism.log` and `/tmp/feat676-im-process.log` support the claimed passed runs. No duplicate full or cross-process run was added after valid independent evidence.

### Effective implementation, canonical readiness and retained limits

Direct `eff2d4684..5432c125a` comparison shows no changes to runtime/product/UI/iOS implementation. c08c3a653 merges only main@082e72ec4's bugfix-678 design/incident documents. Later commits add evidence and the single S29 test; the test's identity, real transport, state assertions and cleanup are appropriate and introduce no product-code change. This preserves prior full review plus Round 8 confirmed-fix closure.

All four active delta texts are unchanged from eff2d4684; target canonical files and MODIFIED requirement identities exist. SHA-256 fingerprints for the exact approved merge input:

| Delta | SHA-256 |
| --- | --- |
| gateway/agent-capabilities.md | b9e7fd37582f7826c8d47b86d654a33b6880224c61a2ecddff77fc7cd44cce66 |
| gateway/personal-agent.md | cb9d8294e3eb35d3062e9578fd9764e69423ac72aa9b55ccb42b40909506e1c6 |
| im/agent-work.md | 753306934bd4bd4642234f274b19d3f74374b84815d37d315fa944100e2a28a3 |
| im/agents-nodes.md | a6d01c288818ec2310db5835568337e1244aebee293e1fd381ca8da58c88baa6 |

Canonical reconciliation/archive may proceed as a pure documentation suffix: replace by requirement identity (some canonical headings already contain the earlier feat-676 wording), apply the removed requirements, preserve unrelated current contracts and update routes/links. Do not duplicate ADDED headings or preserve old foreground immediate-write wording alongside the new sole writer. The caller owns that exact future suffix and retention record; these reports do not pretend it has already been made.

All R8 M1 W1-W13 implementation/evidence concerns are now resolved at the stated depth using Round 7's full matrix plus Rounds 8-9 closures. This concludes verification; no requested implementation change remains. Retained limitations are explicit: T1 is non-blocking and unfixed; PA cross-chat is nonempty Global context, S29 caller is controlled, S28 window/failure injection is controlled, wire capture ends at the local adapter/proxy boundary, and native iOS compilation is not visual QA. None is silently recast as stronger evidence. Remote CI, merge, production deployment/migration and cleanup are caller-owned delivery states and are not asserted by this pass.

## Round 10 — direct-input/native-completion delta verification (2026-10-29)

- `unit_id`: feat-676; `verification_mode`: **delta + corrected-delta**; independent reviewer `/root/dreaming_two_fixes_review`.
- Fixed `executed_base`: `871e48c0478175802c9ce99ecd5b3198f203a5bb`; `validated_at`: `75ed0d4b7904ae5084aaca2de82c6c732a36194d`; commits `091d0d7c5`, `75ed0d4b7`.
- Scope: the two user-approved post-PR fixes and their affected current/delta/design, prompts, Skill, host completion/application and recovery links. Previous full-unit conclusions are not reissued for the new head; unrelated evaluation findings are excluded.
- `verdict`: **pass for this delta**; corrected-delta `outcome`: **aligned**; `requires_full_verification`: **false**.
- Issues: **0 CRITICAL / 0 WARNING / 1 SUGGESTION**. This is a mechanism/code/spec verification, not a fresh autonomous-model or full-product acceptance pass.

### Completeness, Correctness and Coherence

| Dimension | Result |
| --- | --- |
| Completeness | **2/2 requested fixes implemented**; all changed runtime consumers/callers and the changed canonical/archived delta scenario checked. No new user interface or prototype requirement. |
| Correctness | Normal completion is distinguished from execution failure/cancellation before result acceptance; JSON validation and post-completion staging validation gate persistence; source/file/summary versions and receipts still gate progress. |
| Coherence | Public DSH root exports only; no provider-native JSON Schema mode is falsely claimed, no substitute completion tool, new recovery system or runtime loop added. Latest explicit design decision and current/delta agree with implementation. Old design shorthand remains a documentation suggestion below. |

### Corrected Delta Reconciliation

| Delta item / affected contract | Implementation evidence | Test/evidence | Outcome |
| --- | --- | --- | --- |
| design.md:293,302 direct initial-message delivery; existing own-history recovery | dreaming.ts:204-207,227-228,242-265,283-287; dreaming-agent.ts:51-59,93 | Direct-input 4 files/14 pass; runtime request asserts full long input/no file; task request asserts original inherited/own material, no input file, actual rollover/notes/source recovery | **aligned** |
| current agent-capabilities.md:1094-1097 and archived specs/gateway/agent-capabilities.md:170-173, “两阶段正常完成后由宿主保存”; design.md:293,303-308 | dreaming-agent.ts:38-49,94-104: no finish, native completed status, strict final JSON + paired empty/safe slug. Prompts:52,80-82 and shipped Skill:48-52 agree | Runtime 2 + task 5 pass; actual assembled requests have no finish, successful extraction uses one request; invalid JSON/field/empty/slug fail | **aligned** |
| Normal consolidation, no-change, failure/cancelled staging; W2/W10 affected seam | dreaming-agent.ts:97-123 validates after normal completion; dreaming.ts:289-307 saves/checkpoints before commitProgress | Incomplete runtime 6 pass: normal stop/no-change succeeds; denied invalid writes leave valid unchanged memory; missing entry, model error and cancellation reject publication/progress | **aligned** |
| Formal-file versions, source generation, summary reuse/replacement/no_signal; W2/W9/W10 | dreaming.ts:167-177,226-239,250-260,289-313; unchanged operation/receipt recovery:140-150,345-359 | Task valid case passes reuse after failed consolidation, continuation replacement, no_signal retirement and recovery; recovery 8 pass covers generation/third-version/interruption/version-recording | **aligned** |
| Continuous batches and original progress ownership; W8 | dreaming.ts:157-210,309-313 retains frozen target and only successfully integrated versions | Cycle runtime 1 pass: successful prefix commits; failed later batch remains uncommitted; retry freezes fresh target | **aligned** |

The canonical scenario and its archived delta contain the same five added lines. Direct input transport is an internal simplification: the selected material, source meaning and access scope do not change, so no additional externally observable behavior requiring a new canonical scenario was identified. No uncovered observable delta was found in the assigned 15-file range.

### Issues

- **SUGGESTION D-POSTPR-1 — stale design completion terminology.** design.md:194 still says the two fields return through a “受限完成接口”; design.md:279 still says maintenance has a “私有完成接口”, while :293 explicitly removes private finish and :303 describes final JSON/native completion. Align those two old phrases with the final response/host-validation wording when maintaining the design. The latest decision and executable prompt/Schema/Skill are unambiguous, so this is a non-blocking historical-document inconsistency, not an implementation-mismatch or model-visible conflict. The related source comment at document-memory.ts:86 also retains old “own finish tool” wording; it has no runtime effect. No code finding is emitted for these comments.

### Evidence accounting and limits

Reused owner logs were inspected at the specified locators. Final effective regression is **5 files / 22 tests passed**, reconciled from `/tmp/feat676-no-finish-green.log` (18 pass, four extraction-receipt wording assertion failures) and `/tmp/feat676-no-finish-task-green.log` (all task 5 pass after assertion repair). Direct-input red/green is **3 fail → 14 pass**; normal-save red is **2 fail**. Build `/tmp/feat676-no-finish-build.log` and docs `/tmp/feat676-no-finish-docs.log` pass. See code-review Round 11 for the reproducible Node 24 command and precise coverage; already-valid checks were not duplicated.

Code-review Round 11 supplies the reused Mode B Context inspection: initial material plus maintenance prompt, actual request tool lists, shipped layout Skill, history/notes recovery, source status and authoritative host receipt were considered together. These fixtures run real isolated DSH and capture assembled `llm/stream` input with controlled output. They do not establish final provider-wire serialization, autonomous JSON adherence, choice to recover original input after rollover, consolidation quality or cost reduction. No new paid-model evaluation was performed, as directed; existing earlier acceptance cannot be relabelled as a fresh behavior pass for this changed completion protocol. The user's planned evaluations remain separate.

No shared architectural boundary change requiring full verification was found. Remote CI, PR merge, deployment/migration and production acceptance are outside this report. No new services or worktree were started; only the two assigned reports were edited, without a commit.

### Caller closure of D-POSTPR-1

After the independent fixed-head review, the owner aligned the two design phrases and the document-memory.ts comment with final JSON/native completion and host validation. This is wording-only; no executable code, prompt, tool schema or test changed. The suggestion is addressed; the independent reviewed runtime remains `75ed0d4b7904ae5084aaca2de82c6c732a36194d`.
