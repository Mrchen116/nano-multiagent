# Verification Report: bugfix-629-context-recovery

> Final conclusion: **PASS for the user-approved delivery scope**, with final reconciliation below. Three validated scenarios are merged into current spec. R3/R5 forced-reset old-Notes task-selection failures remain actual FAIL and are explicitly deferred to [#377](https://github.com/Mrchen116/nano-multiagent/issues/377); they are not restated as fixed. Earlier no-delivery/pending conclusions are historical and superseded only for this approved scope, not for that unresolved behavior. This report does not assert that merge or deployment has occurred.

> Interim validation snapshot: Nano `164352839cd8717748d4621a5d731780beb44b7e → 2ee87df7becb22f5d2576c192dbbee3018a3a07f`; plugin `621278d → 51eb236`.
> Scope: `full` implementation/spec/design review plus `corrected-delta`. Review round: 1. Product evidence and final immutable package handoff remain pending.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Implementation and available automated evidence reviewed; M1 reviewer exit criteria and final distribution evidence remain open |
| Correctness | No confirmed implementation defect in either complete diff; product recovery behavior is not yet accepted |
| Coherence | Follows the six approved design decisions and public DSH boundary |
| Code review | `[]` (full diff, including the task's temporary package/lock changes) |
| Verdict | Pending; not ready to claim M1 complete or full verification pass |

The Nano checkout was on `codex/bugfix-629-context-recovery`, with only the caller-declared package.json/pnpm-lock.yaml candidate dependency modifications before this report. The plugin checkout was on its bugfix branch at `51eb236`. The two dependency modifications point to a temporary `file:/tmp/bugfix629-e2e/dsh-agent-context-0.3.0-rc.2.tgz` candidate; this is accepted as a test fixture, not assessed as the final delivery contract. No source, test, configuration, or design was changed by this review.

## Completeness

- All implementation files in both supplied complete diff ranges were reviewed, including plugin README, package version, guidance and goldens, and Nano regression changes.
- Incident requirements and all delta scenarios have implementation paths and automated evidence, as mapped below.
- The sole milestone at `design.md:91` additionally requires the real product matrix at `design.md:80-85`, complete CI, and a fixed distributable dependency. Those evidence items are still being prepared by the caller and must not be replaced by scripted adapter completion.
- Frontend prototype/reference: N/A; this unit changes no client surface.

## Correctness

Plugin locations below are relative to the separate plugin checkout `/Users/czj/Repos/opensource-hub/dsh-context-rollover/.worktrees/bugfix-629`.

| Requirement / Scenario | Implementation evidence | Regression / observed evidence | Status |
|---|---|---|---|
| Unchanged Skill/Memory text does not grow with ordinary progress | Plugin `src/index.ts:100-121` contributes window identity only and removes per-assembly Notes hints; Nano `packages/dsh-integration/src/knowledge/runtime.ts:63-76` restores navigation when scoped `skill` is visible | Plugin `tests/engine.spec.ts` stable-context test; native request comparison below | Covered at request seam; seven-Skill real model scenario pending |
| Stale completed Notes plus newly consumed Inbox work, pressure or overflow | Plugin `src/history.ts:309-339`, `src/rollover.ts:264-269`, `src/checkpoint.ts:28-32`: body-free open-turn navigation precedes Notes hint and explicitly requires recovering input/delivery state | Plugin `tests/safety.spec.ts` parameterized default-budget pressure/overflow tests: C=258400, output cap=32768, default B/R; input 223853 in pressure case; actual archived Inbox payload remains recoverable | Mechanics covered; model recovery and delivery pending |
| Direct input and repeated reset in the same work | `normalizedItems` uses native `turn/start.seq`, cleared by `turn/end`; `searchHistory` applies exact turn filter after archived-only selection | Plugin `tests/history.spec.ts` two content windows, exact opaque turn ID, forward pagination, old turn separation, missing turn empty, active body exclusion; `tests/safety.spec.ts` native paired pressure windows | Covered at native/session seam; direct-input real model matrix pending |
| Restart preserves recoverable records | Native compaction checkpoint is a durable `user/message` paired with compaction events; History reconstructs window/turn IDs from snapshot events | History replay tests; Nano `model-policy.test.ts` restarts the native subprocess in all four permission/engine combinations | Session replay and Skill restoration covered; normal product Node restart evidence pending |
| Skill permissions, including explicit invocation with no callable Skill tool | Nano `runtime.ts:70-75`: public scoped `tools.get('skill', agent)` selects navigation versus full-body restoration; both paths still use scoped `skills.get` | Nano `model-policy.test.ts`: `['workflow'] + /skill:retained` and `['workflow','skill'] + /skill:retained`, crossed with plugin enabled/disabled; restored body versus name/path/no-body checked after compaction and restart | Four combinations covered; real Skill re-read and six-step restricted-branch stability evidence pending |
| Provenance, pairing, session isolation and fallback remain intact | History normalization/read paths preserve original source/role and reject active or foreign-window reads; selection/transaction pairing code unchanged; ownership checks unchanged | Plugin history, rollover, tools, preset and safety tests; existing Nano default context, knowledge-policy, capabilities and tool-presentation coverage in the 484-test run | Existing automated coverage passes; product off/on evidence pending |

### Evidence reviewed

| Evidence | Command / method | Result and limits |
|---|---|---|
| `/tmp/bugfix629-plugin-red.log` | Caller ran changed regression cases against pre-fix implementation | Stable-context failed with copies `[2,3,4,5,6,7]` versus fixed `[2,2,2,2,2,2]`; default pressure/overflow cases lacked interrupted-turn recovery. Three effective failures |
| `/tmp/bugfix629-plugin-all.log` | Plugin `vitest run` | 9 files / 26 tests passed; supplied typecheck/build success also reported by caller. Scripted adapters prove request mechanics, not product task completion |
| `/tmp/bugfix629-nano-red.log` | Caller ran four permission/engine combinations plus preset against pre-fix Nano | The two callable-Skill combinations failed; the restricted existing configurations and preset case passed |
| `/tmp/bugfix629-nano-green.log` | Nano targeted model-policy Vitest run | 1 file / 5 tests passed |
| `/tmp/bugfix629-nano-full-tests.log` | Nano `vitest run` | 107 files / 484 tests passed; no duplicate full run by reviewer |
| `/tmp/bugfix629-nano-typecheck.log` | Nano recursive typecheck | All listed packages completed; no errors in supplied log |
| `/tmp/bugfix629-build.log` | Nano build | Build completed; installer metadata identifies base SHA `1643528`, so this log alone is not treated as final pinned-release or CI evidence |
| `/tmp/bugfix629-docs-check.log` | Documentation integrity | Passed, 253 maintained Markdown sources / 67 required routes before this report |
| Reviewer-run architecture gate | `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_runtime_dependency_contract.py -q` in the supplied Nano checkout | 13 passed in 0.12s |
| Native request comparison | Read actual `messages[].content[]` text in the request logs under the `home` fields of `/tmp/bugfix629-baseline-counts.json` and `/tmp/bugfix629-fixed-counts.json` | Post-reset requests 3-8: baseline Skill sentinel copies `[1,2,3,4,5,6]`, runtime snapshot markers `[2,3,4,5,6,7]`; fixed copies `[0,0,0,0,0,0]`, snapshots `[2,2,2,2,2,2]` |

The comparison intentionally excludes `source.sections`, which duplicates context text in serialized runtime metadata. It establishes that ordinary tools/Notes no longer append unchanged text to the provider-facing message body. The native probe used one synthetic Skill and scripted adapter responses; it does not satisfy the seven-Skill and real task-recovery acceptance by itself. The two fixed runtime snapshots are bounded reset reconstruction cost allowed by design decision 6, not stepwise growth.

## Coherence

| Approved design decision | Followed? | Evidence |
|---|---|---|
| 1. Remove high-frequency references and Notes directory from context contribution | Yes | Plugin `src/index.ts:100-121`; `get_context_remaining` and exhausted-window fallback still return references; guidance and goldens describe on-demand use |
| 2. Respect both Skill selection and callable-tool permission | Yes | Nano `runtime.ts:66-76`; inspected locked DSH public `Tools.get` implementation, which resolves `view(scope).visible`; no allowlist widening |
| 3. Exact native turn boundary across archived windows | Yes | Plugin `src/history.ts:83-89,132,181-194`; opaque event seq, no global turn-number matching; active-only items excluded before filtering |
| 4. Body-free interrupted-turn metadata on reset | Yes | Plugin `src/history.ts:309-339`; at most first plus four latest item refs, bounded JSON metadata; no content preview/body; `src/rollover.ts:264-269` computes metadata synchronously before replacement |
| 5. No semantic completion classifier or second task database | Yes | Guidance asks the model to recover actual input and deliveries; no new persistence owner, task inference, or send hook introduced |
| 6. Preserve public native compaction transaction and bounded environment reconstruction | Yes | Existing selection, locks, shrink guard, source coverage, paired summary/replace/end and flush preserved; no DSH private import/patch or runtime fork |

The locked native AgentLoop opens `turn/start` before claiming its first input, so admitted direct input is assigned to the correct turn; pending not-yet-persisted claims remain on the existing pre-step path. `interruptedTurn` emits no recovery block for an idle manual reset or when the current turn has no item in the selected span. Filtering by session-local turn ID does not broaden which session History can read.

## Issues / open evidence

### CRITICAL

- **V1 — M1 product exit criteria remain unverified.** Contract: `design.md:78-85,91` and delta `specs/gateway/agent-capabilities.md:13-28`. Supply the independent product reviewer report and raw request/native/delivery locators for (a) stale completed Notes + already-read latest Inbox input + default-budget forced reset followed by History recovery and exactly one correct delivery; (b) real-model direct input across at least two content windows; (c) seven Skills totaling at least 52400 characters, six ordinary/Notes steps, and genuine Skill tool re-read; (d) normal Node restart plus off/on. Include the restricted `['workflow'] + /skill:name` branch without temporarily permitting `skill/read`. No confirmed source defect is implied by this pending gate.

### WARNING

- **V2 — Final package/CI handoff remains pending.** Contract: `design.md:58,91`; current candidates: `packages/dsh-integration/package.json:74`, `pnpm-lock.yaml:268`. Replace the caller-declared temporary test dependency with the immutable release URL/integrity after release, identify the exact plugin commit/tarball hash and final Nano commit, then provide applicable final CI/install/build evidence. Review the resulting dependency-only delta before closure. The temporary path is not reported as a final-contract code-review finding.

### SUGGESTION

None. No speculative edge-case or style changes requested.

## Corrected Delta Reconciliation

Final reconciliation: user-approved scope split `34e0ab6d924821d0ded6a8ce8088cba9b456c718`, independent product final disposition `5fa5db7b9ed5e58afaba36dc50bc36517fc49270`. Executable source remains frozen Nano `839880856ca9b8d9717fe0045bbc34a7b479de5c` and plugin `823a2029d216cc5e128a76976abc7b0c84df4690` / rc.5. Only the three final delta scenarios are delivered; prior forced-reset selection failures are deferred to #377 by explicit user decision.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Final delta: 新任务已读后大批工具结果造成上下文压力 | Plugin public native-pruner-before-H path, same-request budget remeasurement; archived originals/source links retained, residual pressure still uses original reset | R4 real Web IM same-25-volume original Inbox task retained, 32 native prunes, one correct todo delivery; native automated boundary coverage | aligned; exact full scenario text is present in current `docs/specs/gateway/agent-capabilities.md` |
| Final delta: 长任务按需恢复 Skill | Nano new mode omits entire used-Skill body/index contribution; native catalog and selected/current-session History retained; old summary mode retains prior body behavior | R3/R4 seven-Skill/no-growth/real reload, workflow-only original-source History, actual normal restart and off/on; native integration retained | aligned; exact full scenario text is present in current spec; does not guarantee model chooses the right note |
| Final delta: Explicit Skill gestures survive later tool-history pruning | Nano `capabilities.ts:85-121` extracts id/name from complete live final result and injects through current selection/pre-step/durable invocation ID | R6 pruner off/on regression, actual native prune, three completed turns, human once, Agent/partial excluded, no restart replay; final 485 tests | aligned; exact full scenario text is present in current spec |

### Uncovered Observable Behavior

No uncovered delivered behavior found. Notes hint rendering is a separately verified format correction to existing bounded navigation, not a new task-recovery mechanism. The final delta intentionally removes two unchanged canonical scenarios (multi-window continuation and original-detail recovery) from its modification list; current spec retains their pre-existing text unchanged. Their omission from this unit's delta is not deletion of the canonical requirements or proof that all related failures have disappeared. Explicit forced-reset old-Notes selection remains known failed behavior tracked in #377.

Outcome: **aligned; final scoped verification PASS**, 0 CRITICAL / 0 WARNING / 0 SUGGESTION in the user-approved delivery scope. Independent product disposition also passes that scope. R3/R5 failures remain FAIL and are deferred rather than fixed. `requires_full_verification: false`; frozen implementation/test evidence is retained and no source/dependency delta invalidates it.

Report ownership: caller will commit this report in the shared unit branch. No review service/process was started; nothing requires cleanup. Await supplementary evidence through the caller; do not poll product execution.

## Round 3 — user-directed lifecycle revision

> Final product supplement: `regression.md:55-105` now records **FAIL** for the original incident, with actual default-budget pressure, stale completed Notes, zero History calls and no todo delivery. The following pending statements record the earlier static handoff state only. R3 V1 is now failed; independent Skill lifecycle/source observations that passed remain valid as identified in Round 4.

### Metadata and scope

- `verification_mode`: full affected-contract review plus corrected-delta reconciliation above.
- `review_mode`: full final diff against the original implementation bases, plus explicit rc.2 → R3 removal diff.
- Nano executed base: `164352839cd8717748d4621a5d731780beb44b7e`; validated HEAD `35fccff2fdea096aad481c02e683c4176b7319b2`; source change `c2a7d2a6c3445c165899caffd15c21c8fdf01990`; approved design `242d80010`.
- Plugin executed base: `621278d`; prior reviewed head `51eb236`; validated HEAD `2c29b0b59581ff622923e3b92a0a4b6c68de1e9f`.
- Nano checkout initially had only caller-owned pending additions to `M1-recovery/implementation.md`; plugin working tree was clean. Only this verification report was edited by the reviewer.
- Gate 2 R3 is Approved, 0 CRITICAL / 0 WARNING. This review applies its changed target; it does not preserve candidate rc.2 task-navigation or restricted automatic-body requirements.

### Verdict

**Code review: Nano `[]`; plugin `[]`. R3 implementation/delta alignment: aligned. Final R3 product verification: FAIL, 1 blocking original-incident failure / 0 additional implementation WARNING / 0 SUGGESTION.**

R3 originally awaited M1 product verification; the final independent report now confirms that the original task was lost after pressure reset. Static alignment with R3 design remains valid, but it cannot close this product failure. Earlier V2 immutable packaging/install handoff is closed for R3 by the release pin, matching artifact bytes, frozen install, final build and installed native integration evidence below. No PR/merge/deployment or remote CI result is claimed.

### Completeness and correctness

| R3 decision / contract | Actual implementation and test evidence | Conclusion |
|---|---|---|
| Stable plugin environment contribution (`design.md:25`) | Final `src/index.ts:100-121` contributes only window identity, without per-step references or Notes hint. Original budget/fallback reference lookup is retained. Existing stable-context test remains in final plugin run | Followed; ordinary changes no longer force a full runtime snapshot |
| Remove the whole extra Skill restoration (`design.md:27`) | Nano `packages/dsh-integration/src/knowledge/runtime.ts:68` returns before `files(...).references`, the loop and contribution push when the actual preset compaction owner exists. No used-Skill navigation/body branch remains in new mode | Followed; neither index nor fallback body is contributed |
| Preserve native catalog and original explicit input (`design.md:29`) | No catalog/explicit invocation source code was modified. Locked DSH `tool-skill` checks visible scoped skill tool, effective skill set and active-surface catalog digest. Nano explicit `/skill:name` still persists `skill-invocation`. Native model-policy covers initial explicit input, post-reset absence and subprocess restart in both tool configurations | Followed; catalog content contains names/descriptions rather than old Skill instructions |
| Keep old summary full-body behavior (`design.md:29`) | Without a preset owner, Nano retains original scoped `skills.get` and `renderSkillContent` loop. Both summary-mode permission configurations assert body restoration | Followed; R2 callable-tool index path removed from old mode too |
| Remove candidate task recovery protocol (`design.md:31`) | Final plugin `src/history.ts`, `src/checkpoint.ts`, `src/rollover.ts` and `src/tools.ts` equal original base for those files. No `turn_id`, `interruptedTurn` or `<interrupted_turn>` exists in shipped JS. Old dedicated turn-filter test removed; default pressure/overflow tests now assert original History retrievability without replay | Followed; native pairing, source retention and archived-only session boundary unchanged |
| Judge original incident with real Notes/History (R3 design decision 5/runbook/M1) | Final `regression.md:60-78`: actual pressure reset after consumed new Inbox, stale Notes read, no History, completed without todo delivery | FAIL; static History availability did not translate into task recovery |

The owner query is the same public `agentPresets.serviceFor(agent, 'compaction')` already used by `NanoCompaction`. It resolves the retained Agent preset's service; no heuristic based on old logs, tool names or new persistent mode state was introduced. The current approved topology uses this owner for the no-summary workspace engine and leaves disabled mode to the host summary engine. No speculative third-party owner classification is added to this review.

Existing source/approval logic is untouched. Under the restricted new-mode `['workflow']` configuration, History remains an internal enabled context tool and original `skill-invocation` content is not excluded by History normalization. Thus the implementation provides the approved existing recovery path without granting `skill/read`; whether the model actually uses it is still part of product acceptance.

### Evidence reviewed, with exact limits

| Evidence | Result | What it establishes |
|---|---|---|
| `/tmp/bugfix629-r3-nano-red.log` | 3 intended failures, 2 passed | Old new-mode restricted/callable contributions violate the no-index/body target; old summary callable branch violates restored full-body target |
| `/tmp/bugfix629-r3-plugin-red.log` | 2 intended failures, 3 passed | Candidate pressure and overflow requests still contained forbidden interrupted_turn |
| `/tmp/bugfix629-r3-nano-tests.log` | 1 file / 5 passed | Revised four native engine/tool configurations plus preset-owner case |
| `/tmp/bugfix629-r3-plugin-tests.log` | 9 files / 25 passed | Final plugin suite, retaining pairing/history/pagination/preset/notes/budget protections while removing candidate turn protocol; supplied plugin typecheck/build also passed |
| `/tmp/bugfix629-r3-full-tests.log` | 107 files / 484 passed | New Nano source with old rc.2 plugin; broad Nano regression evidence only, not a final-rc.3 full-suite claim |
| `/tmp/bugfix629-r3-installed-tests.log` | 1 file / 5 passed | Final installed rc.3 native model-policy integration; the non-existent `agent-context.test.ts` argument matched no additional test and is not counted |
| `/tmp/bugfix629-r3-install.log` | Frozen lockfile accepted; one package downloaded/replaced | Immutable rc.3 dependency resolves with final lock |
| `/tmp/bugfix629-r3-final-build.log` | Build complete; source metadata `c2a7d2a6c3445c165899caffd15c21c8fdf01990` | Final source and rc.3 package build; not an installed production release |
| Reviewer artifact inspection | Pack and downloaded copies both SHA256 `58aee15f347f2a2a26e02bb9bd0c8766e3a54e06ae294695d3aed1583c9c8f99`; SHA512 matches lock; all 27 installed lib files match release bytes; both manifests rc.3; no candidate protocol symbols in shipped JS | `/tmp/bugfix629-e2e/dsh-agent-context-0.3.0-rc.3.tgz` equals `/tmp/bugfix629-release-verify-rc3/dsh-agent-context-0.3.0-rc.3.tgz`; installed integration dependency manifest is also rc.3 |
| Final code/lock inspection | Exact GitHub `v0.3.0-rc.3` URL plus SHA512 integrity in package/lock; no temporary file dependency | Final distribution pointer replaces prior candidate dependency |
| `git diff --check` in both checkouts | Passed | No diff whitespace errors; no source changes made by reviewer |

No unchanged full suite was rerun, and no R3 product instance was operated by this reviewer. The prior architecture gate remains applicable: the changed owner call consumes an already-declared public service, no dependency/import or boundary changed. Prior rc.2 request-count or product outcomes may explain the baseline but cannot pass R3. In particular, rc.2's restricted-body sequence `[1,1,1,1,1,1]` is obsolete; R3 requires absence of the extra body/index in new mode.

### Open issues and closure instructions

- **R3 V1 — FAIL (CRITICAL: original incident reproduced).** Independent `regression.md:60-78` confirms consumed new Inbox/default pressure before new Notes, stale completed Notes read, no History recovery and no final todo delivery. Separately, seven-Skill/no-growth/re-read and restricted original Skill History/source observations passed; actual product Node restart/off-on remained unexecuted. Preserve both successes and uncovered scope without calling R3 accepted. R4 has a separately scoped prune-first target.
- **R3 V2 — closed.** Final URL/hash/lock/install/build and final installed native tests reviewed. This closure does not assert PR CI, deployment or production health.
- **Old turn-navigation and restricted automatic-body conclusions — superseded.** They belonged to rc.2 and are intentionally removed by the user's R3 decision. Their removed tests are not missing regression protection for the new scope.

`requires_full_verification: false` for evidence closure on these frozen heads. A changed implementation, new recovery hint or changed budget/policy must be resubmitted with its concrete delta. Product reviewer owns `/tmp/bugfix629-r3-runtime`; this review neither started nor stopped it. Caller owns report commit and remaining evidence handoff.

## Round 4 — native pressure pruning delta

### Metadata, scope and verdict

- `verification_mode`: delta plus corrected-delta reconciliation above; `review_mode`: patch.
- Nano range `35fccff2fdea096aad481c02e683c4176b7319b2 → 06c7aec52d759c45dd9db82bfef0a2a052b47b6e`: product source unchanged, exact rc.4 dependency and lock plus scoped design/evidence changes.
- Plugin range `2c29b0b59581ff622923e3b92a0a4b6c68de1e9f → ce7d551ef90811191fb190a99f04ba74e961e14c`: `src/index.ts`, native-pruner integration in existing safety tests, declared optional peer/dev dependency and lock, README/version.
- R4 Gate 2 Approved, 0 CRITICAL / 0 WARNING; checked against current `design.md:39,53-61,73` and corrected delta.
- Reviewer owns only this report. Frozen code, tests, design, product runtime and existing evidence were not modified; no full-suite duplicate, service control or new product experiment performed.

**Code review findings: Nano `[]`; plugin `[]`. Implementation/delta alignment: pass for the scoped native-pruning change. Overall M1 product verdict: pending R4 evidence. R3 product verdict: FAIL remains.**

### Implementation and correctness

| Contract / path | Evidence | Result |
|---|---|---|
| Prune at work line W, remeasure before hard line H | Plugin `src/index.ts:139-151` closes over the same `decision.messages`, `assembly`, resolved header and rendered system message for both `budget()` calls; `prunePressure` at `225-231` calls the public synchronous service only when T >= W | aligned; no stale pre-prune reading drives reminder/fallback/reset |
| Current task remains when tool-result pressure is removed | Real published pruner test loads 25 results below the existing per-result spill cap, observes 25 native prune events, no reset, current input in next request, 25 prune markers, bounded request body | covered at native request seam; this scripted response is not task delivery |
| Still above H after pruning | Existing safety owner test adds unprunable text to the 25-result batch; observes 25 native prune events and one reset | covered; prior hard-reset behavior preserved |
| Public `compactIfNeeded(pressure)` | `src/index.ts:341-348` invokes the same `prunePressure` before H; test starts at W <= T < H and ends below W with one prune and no rollover | covered; fixes public entry as well as pre-step hook |
| Provider overflow | `perform` at `src/index.ts:278-286` prunes before surface selection and its native measurement; existing request-error retry/generation path unchanged | Native test proves below-W continuation initially has full result, then overflow causes prune before compaction/start and existing single reset/retry |
| Explicit/manual and no-service behavior | `reason` branch bypasses `prunePressure`; overflow is the only added operation in `perform`; missing optional service returns original reading | Explicit batch test has no prune and one reset; existing no-service pressure/overflow/manual tests remain in final suite |
| Native source, durability and replay | Public `ToolResultPruner.pruneSession` retains original event data and message/source/call, changes only content, writes `compaction/prune` before replacement with original `sourceEventSeqs`; plugin does not reproduce these mechanics | Original 25 full result events remain durable, Session replay matches; existing History archived-only normalization can read original nodes once replaced |
| Public package boundary | Type-only root import `@deepseek-ai/dsh-compaction-tool-result-pruner`, exact published peer version and optional metadata; get service through existing Cordis public API | No DSH fork/patch/private import, alternate truncation algorithm, manual token subtraction or new budget state |
| No new task/Skill hints | R4 leaves history/checkpoint/tools/guidance and Nano knowledge source unchanged | No withdrawn turn protocol or extra used-Skill contribution reintroduced |

Read the locked public pruner type and implementation directly: `pruneSession` is synchronous, scans current-surface tool/results, prices shadowed content through the native token meter and preserves complete originals. Locked BasicCompactionEngine likewise prunes/re-measures before pressure decisions and prunes before overflow selection. R4 uses that same service rather than copying its algorithm. The existing plugin budget function still includes pending inputs, tools/system changes and its request reserve; those cannot disappear between pre/post prune accounting.

### Evidence reviewed

| Locator | Result and limit |
|---|---|
| `/tmp/bugfix629-r4-plugin-red.log` | 4 effective failures against the old implementation: batch prune paths (including still-over-H), public pressure entry, overflow prune. Explicit unchanged reset case passed; do not call all new tests red |
| `/tmp/bugfix629-r4-plugin-tests.log` | 9 files / 30 tests passed, including 10 safety tests. New same-batch cases use default C258400/O32768 and real installed pruner; no model task-completion claim |
| `/tmp/bugfix629-r4-plugin-typecheck.log` | Published dependency resolution and typecheck passed |
| `/tmp/bugfix629-r4-plugin-build.log` | Build passed |
| `/tmp/bugfix629-r4-install.log` | Nano frozen lock accepted; rc.4 package resolved and installed |
| `/tmp/bugfix629-r4-nano-build.log` | Full build completed, installer candidate identifies Nano `06c7aec52d759c45dd9db82bfef0a2a052b47b6e`; not production deployment |
| Reviewer artifact inspection | Pack/download copies at `/tmp/bugfix629-e2e/dsh-agent-context-0.3.0-rc.4.tgz` and `/tmp/bugfix629-release-verify-rc4/dsh-agent-context-0.3.0-rc.4.tgz` both SHA256 `6649b0da07c886a886a7a0e2a594df8d476951d6aca80a8bdc27b6a0b4cababa`; SHA512 equals Nano lock; installed rc.4 manifest and all 27 lib files equal release bytes; shipped JS has no withdrawn turn protocol symbols |
| Both checkout `git diff --check` | Passed |

R3 installed model-policy/context/workspace tests, static source and architecture conclusions remain valid for unchanged Nano Skill restoration, catalog/source/permission paths. They are not represented as a new final-rc.4 484-test run. The new path is covered by final plugin tests and build, while real final host wiring/25-volume delivery is awaiting the product reviewer.

### R3 failure and retained evidence

R3 original incident is **FAIL**, per independent `regression.md:60-78`: session `534620fd-450e-4756-9b6d-04ba99d3276f` read new Inbox at seq83, received 25 Skill results seq93-141, pressure-compacted at seq143-146 before new Notes, read stale completed preparation at seq151/152, did not invoke History or deliver the requested AMBER todos and ended completed at seq168. This is an observed failure, not merely missing evidence. Current R4 implementation cannot retroactively change it.

Retain the independent R3 successes at `regression.md:80-91`: native Skill catalog reconstruction with zero old body/index; six ordinary/Notes steps without new runtime snapshot or old Skill body growth; genuine one-Skill reload; workflow-only explicit Skill body restored from History with source `skill-invocation` and correct result. Those paths are unchanged by R4. Normal product Node restart and real off/on were not completed in R3 and remain unproven beyond native scripted integration tests.

### Issues and handoff

- **R4 V1 — pending (CRITICAL: product exit criterion not complete).** At `design.md:53,57,73`, provide independent final-rc.4 evidence using the unchanged 25 original volumes/default budget/spill/policy: original batch pressure, native prune before new Notes, next provider request retaining current Inbox task without avoidable rollover, correct original-source todo facts and exactly one persisted delivery. Check that pruned middle previews are not mistaken for full documents. No scripted completion or offline token reduction closes this item.
- **R3 V1 — FAIL, retained residual boundary.** Native-pruning avoidance of an unnecessary reset is the R4 target. Even a future R4 pass must not become a claim that all unprunable hard-reset task recovery now succeeds; this remains an explicitly documented limitation under the user-selected Notes/History design.
- **V2 immutable package/install/build — closed for rc.4** by the inspected final pin/artifact/installation/build evidence. No PR CI, production deployment or production-health claim.
- No confirmed code-review defect or additional implementation warning in the scoped delta. No speculative work requested.

`requires_full_verification: false`; the declared delta and all its affected admission/overflow/package seams were reviewed. Caller will commit this report after the independent product handoff. No canonical spec merge or completion archive is authorized by this interim report.

## Delivery disposition after independent R4 product report

Product report commit `3cddf7e18` closes R4 V1 as **PASS for native pruning of the unchanged 25-document batch**. Normal restart, source-preserving History recovery, old-summary fallback, and re-enabled Skill lifecycle mechanisms also passed. Source/dependency tree remains Nano `06c7aec52` and plugin `ce7d551`; subsequent commits only record evidence, so static findings and corrected-delta alignment are retained.

The separate on-after-off task **FAILS** after explicit new_context: it writes a new on-checkpoint, then reads an older checkpoint and delivers the old task status. See regression.md R4-1. This is not evidence of a native-pruning regression, but it blocks declaring the original broad current-task recovery requirement fixed. No additional recovery protocol is introduced without a newly agreed design.

Accordingly the full unit remains active: no canonical-spec merge, archive, Ready PR, merge or production deployment. The scoped code and passing pressure result are preserved for review, and the residual failure is reported to the user. This disposition supersedes any earlier pending-product status; it does not alter the independent code-review verdict.

## Round 5 — Notes hint format and bounded adaptation check

> Final product supplement: independent `regression.md:166-201` records **FAIL (R4-1 not closed)**. The new Notes header/order/metadata appeared correctly in the actual first post-reset request, with `on-checkpoint` first, but the model still read old `checkpoint` and delivered the wrong prior status. The pending statements below preserve the earlier static handoff; this is now a confirmed failure, not missing evidence.

### Metadata and verdict

- `review_mode`: patch, plugin `ce7d551ef90811191fb190a99f04ba74e961e14c → 823a2029d216cc5e128a76976abc7b0c84df4690`; local `src/notes.ts`, existing Notes test, package version only. Nano `0d0d78d97ced7e18976c1964c05aa0a5f8b4fe1e → 418dd4bfb36cf6ecd81e25dc6f3ba225d2f4729e`, rc.5 exact dependency/lock and format explanation; product source unchanged.
- `verification_mode`: targeted delta; format correction described in `design.md` R5 Changelog, retaining R4 Gate 2 architecture.
- Reference: local Codex clean HEAD `464add49587a7cb6032d5ab04faa8a1585947853`, specifically `codex-rs/ext/history-notes/tests/history_notes_extension.rs:48` and `src/extension.rs:115-170`.
- Reviewer changed this verification report only. No source/design/test edit, runtime control, new product input or repeated full suite.

**R5 code-review findings: plugin `[]`; Nano dependency delta `[]` (product source unchanged). Format implementation: aligned. New adaptation omissions confirmed by the bounded check: none. R4-1 product result remains FAIL until the independent new run proves otherwise.**

### Format correctness and evidence

| Requirement | Actual evidence | Result |
|---|---|---|
| Fixed Codex sample header and metadata layout | `notes.ts:232,236`: `Recent notes (up to 5, most-recent first):` and `- <path> (<lines> lines, <bytes> UTF-8 bytes)`; exact fixed Codex `THREAD_HINT` sample has the same header/entry metadata | aligned in presentation; session-relative paths intentionally retained |
| Correct local counts and order | `listings()` still sorts mtime descending, path as stable tie-break. `hint()` reads text for its local newline-split line count and uses actual stat UTF-8 byte size. Test uses two distinct mtimes and Unicode `新状态\ncontinue` = 2 lines / 18 UTF-8 bytes | covered; no guessed backend line-count algorithm claimed |
| Existing scope and bounded body-free navigation | Still takes first five current-session entries, tests candidate total with `Buffer.byteLength` <=4000, returns empty for no notes, emits no file body. Existing write/read isolation and limit code unchanged | aligned; no automatic file selection/current-task pointer or new recovery instruction |
| Hint timing and provenance | `perform` still obtains hint at window construction; checkpoint text includes it with existing runtime/window guidance; ordinary assembly does not call hint | unchanged; no per-step dynamic-context regression or role/source rewrite |

- `/tmp/bugfix629-r5-notes-red.log`: one exact-format assertion failed effectively against `<recent_notes>` path-only output; four existing Notes tests passed.
- `/tmp/bugfix629-r5-notes-green.log`: all 5 Notes tests passed after the format correction.
- `/tmp/bugfix629-r5-plugin-tests.log`: 9 files / 31 tests passed; `/tmp/bugfix629-r5-plugin-typecheck.log` and `...-build.log` passed. Existing warning about the parent tsconfig path did not prevent those successful gates.
- Final rc.5 `/tmp/bugfix629-r5-installed-tests.log`: 2 files / 10 tests passed (`agent-context-default` and `model-policy`), exit 0 confirmed by caller. No duplicated 484-test run; unchanged R4 broad evidence retained.
- Final dependency artifact: release `/tmp/bugfix629-release-verify-rc5/dsh-agent-context-0.3.0-rc.5.tgz` SHA256 independently verified as `25ddf026b251bcebefdfba294607ce518a47ca155de769bdd413b2ee739b8ea7`; computed SHA512 equals final lock, installed manifest is rc.5, all 27 installed lib files equal release bytes and `lib/notes.js` contains the new header. Caller separately compared published download with the pack byte-for-byte.
- `/tmp/bugfix629-r5-install.log` frozen install passed; `/tmp/bugfix629-r5-nano-build.log` full build passed. Build metadata records pre-pin `0d0d78d97`; the final `418dd4bfb` difference only pins the already-built package/lock and format record, with no Nano source delta. Do not represent that metadata as an installed production release.
- Full-suite evidence is reused without rerun. It verifies local rendering and existing native mechanics, not selection of the correct note after a real reset.

Codex's fixture is a supplied `thread_hint` backend response, not the implementation of the backend's selection/counting algorithm. Its extension checks response text and the 4000-byte cap and emits a tool-attributed context fragment. R5 matches the visible sample shape only. It does not establish 100% server behavior equivalence, created-vs-updated backend selection semantics, or special trailing-newline/empty-file counting rules unknown from that reference.

### Separately listed new findings from the bounded recovery-chain check

**Confirmed new findings: `[]`.** Checked adjacent Notes/History guidance, current tool schemas and execution dispatch, hint order/bound, reference guidance and checkpoint/source plumbing. No additional patch is requested on the available direct evidence.

| Inspected area | Assessment |
|---|---|
| Tool names/parameters in guidance | Guidance names merged `notes`/`history`, action `list_items`/`search`/`read`, `new_context`, `get_context_remaining`; these resolve to actual current dispatch. Returned History window/item IDs and pagination cursors feed the declared corresponding fields. `offset_chars`/`limit_chars`, Notes `start_line`/`end_line` and Unicode continuation fields map to their actual implementations. No stale upstream names were found in current guidance |
| Notes and History ordering | Hint/list use local modified-time descending; History uses session seq in requested direction with exact directional cursor. This matches current local semantics. Upstream customizable file ordering and absolute Agent path navigation are not promised by this plugin |
| Isolation and merged tools | Session-relative note paths, current-session archived-only History, immediate local consistency, combined action tools and bounded parameter ranges are explicit DSH adaptations. They differ from Codex's separate backend tools/cross-Agent paths and eventual consistency deliberately; absence of those upstream capabilities is not a newly found omission |
| References | Guidance explicitly requests current references via `get_context_remaining` and uses attached fallback references. It no longer promises that a new runtime snapshot supplies references every step. This is the retained fix for DSH cumulative environment snapshots |
| Source and role | Codex tool-attributed context-hint fragment versus DSH user-role compact-checkpoint is a known structural runtime adaptation. Current DSH checkpoint remains native `compact-checkpoint`, while recovered History retains original source/role. No basis to reclassify it as human authorization, introduce developer messages, or manufacture a tool result |
| Unknown backend details | No backend implementation for hint selection/counting is available in the reference. A difference not established by source or current local contract is not reported as a defect |

### Remaining handoff

- R4 native-pruning and its accepted same-25-document result remain valid, as do independent restart/original History/source, old summary and Skill lifecycle mechanism observations.
- R3 broad forced-reset task loss and R4-1 wrong-note task completion remain actual failures. The new format has no new task hint, task state or selection policy, so a static pass cannot close them. R4-1 recheck on rc.5 must be recorded by the independent product reviewer; no outcome is predicted here.
- Final rc.5 immutable package/lock/install/build and installed 10-test handoff is closed on Nano `418dd4bfb` and plugin `823a202`; no PR CI or production claim.
- `requires_full_verification: false` for this format-only revision. No canonical merge, archive, Ready PR, merge or production change follows from this report.

## Round 6 — complete live Inbox result before native pruning

### Metadata and verdict

- `review_mode`: patch; source/test delta through frozen Nano `839880856ca9b8d9717fe0045bbc34a7b479de5c`, product source change confined to `packages/dsh-integration/src/capabilities.ts`; existing `knowledge.test.ts` owner test extended. Approved R6 design/delta reviewed; no plugin change from rc.5.
- `verification_mode`: targeted delta plus reconciliation above. Retain R4 native-pruner and R5 hint-format evidence; do not rerun unaffected full gates.
- Checkout initially had caller-owned pending implementation evidence only. Reviewer changed this report only, not source/design/tests/config or runtime.

**Code-review findings: Nano `[]`; plugin N/A (unchanged). R6 implementation/delta: aligned; scoped verification PASS, 0 CRITICAL / 0 WARNING / 0 SUGGESTION. Targeted deterministic native regression and final full build/485-test/typecheck gates passed. General task recovery remains failed as recorded separately; this scoped pass does not complete the full unit.**

### Lifecycle, provenance and correctness

| Contract / seam | Direct evidence | Assessment |
|---|---|---|
| Observe complete successful host-live Inbox result | `capabilities.ts:97-104` checks exact inbox name, Agent, `!result.isError`, current process `isLiveInbox(agent.id, callId)`; reads final `result.value.body.messages` rather than mutable rendered message text | aligned; check/read history/failed/foreign results cannot become pending merely through matching content |
| Exact producer shape and ordering | Existing `global-mode.ts:43-62` retains raw product result as `body`, completes attachment admission and `inbox.prepare`, records live call, returns `{body,content}`. Read final locked DSH tools implementation: final value is retained losslessly alongside content, `tools/result` callback is invoked synchronously and cannot alter the committed result | Complete body available at the chosen public seam; queue observer performs no async lookup/tool dispatch |
| Human, complete messages only | `capabilities.ts:103` filters `sender.type === 'user' && !partial` before parser. Existing prefix syntax is unchanged and direct `nano-human` input uses the same extracted parser | No new automatic invoking source/grammar or authorization rule |
| No second body channel | Agent-keyed WeakMap at line95 contains only generated invocation ID and Skill name; observation at line104 queues those pairs. No message/Skill body cache, file/database write, new RPC, schema/source change | aligned with user scope; transient adapter handoff, not another persisted Inbox or recovery protocol |
| Accepted pre-step, current selection and consumption | `capabilities.ts:109` returns on rejected decision before consuming. Lines115-117 use scoped current `skills.get`, session cwd/signal and `isUserInvocable`; line120 clears pending after processing | Selection checked at consumption, not frozen as a body during observation; errors during lookup leave the queue for existing failure handling rather than silently discarding |
| Once-only behavior | Native snapshot invocation IDs are collected at line110, include off-surface history; local invoked set is updated before adding each message. IDs retain `nano-skill:<messageId>:<name>`; same-step duplicate pairs and repeated live-read IDs cannot produce another persisted invocation once admitted | Existing persistent dedup mechanism retained, no new processed-message store |
| Source, restart and pruning | Existing injected source remains `skill-invocation`; restored sessions do not dispatch fresh final tool results or reconstruct live call provenance; queue is Agent-local/in-memory. Native pruner still operates normally on rendered text | No source upgrade or full-body re-injection; no historical JSON parser remains in the Skill consumer |

The old source loop parsed every still-live historical Inbox tool result before checking invocation IDs; native pruning could therefore break JSON even after the original gesture had already been processed. R6 removes that loop entirely rather than catching and discarding parse errors or exempting Inbox from pruning. This directly addresses the observed repeat-step crash while preserving normal pruning and current Skill permission checks.

### Test validity and evidence

| Evidence | Observed result / meaning |
|---|---|
| `/tmp/bugfix629-r6-red.log` | Existing unpruned variant passed; pruned variant failed with three turn endings `error,error,error` instead of `completed,completed,completed`. One effective failure, one pass, three unrelated tests skipped; this is not a five-test red run |
| `/tmp/bugfix629-r6-green.log` | Two variants passed, three unrelated tests skipped. Both execute the real RuntimeClient/native Global Inbox path; pruned case uses the installed native pruner and explicitly requires a persisted `compaction/prune` event |
| `knowledge.test.ts:146-175` | 12000-character long result remains below the existing single-result spill limit but above native character prune threshold; fixture's pre-step invokes actual native service to exercise consumer ordering deterministically without a model pressure trigger. It checks three completed turns, exactly `nano-skill:human-message:selected`, excludes Agent/partial-human cases, shuts down/restarts, observes invocation count still one |
| `/tmp/bugfix629-r6-build.log` | Narrow source compilation passed |
| `/tmp/bugfix629-r6-full-tests.log` | Final frozen R6 source: 107 files / 485 tests passed; caller confirmed exit 0. Reviewer read completed log, did not rerun |
| `/tmp/bugfix629-r6-typecheck.log` | Final recursive typecheck passed; completed log inspected |
| `/tmp/bugfix629-r6-nano-build.log` | Final full build passed; installer candidate metadata identifies exactly `839880856ca9b8d9717fe0045bbc34a7b479de5c`, not a deployed release |
| Documentation integrity | Caller confirmed final docs check passed; no additional doc gate rerun by reviewer |
| Reviewer `git diff --check` | Passed |

The test's deterministic pre-step pruning is appropriate for this consumer bug: it exercises actual source registration, final result value, pruning, repeated native turns and durable invocation IDs. R4's already accepted pressure-at-W wiring remains its own evidence. The new case does not claim another true pressure-triggered product journey or a real-model task-recovery success. Failed/non-live/system exclusions are directly established by the guard/producer lifecycle; the newly parameterized fixture explicitly covers human, Agent, partial and restart cases and is not overstated as an exhaustive source matrix.

### Retained conclusions and handoff

- R4 same-25-volume prune-first request preservation and single correct delivery remain PASS.
- R5 Notes format, bounded metadata and actual first post-reset ordering are PASS as mechanisms; the same independent run still chose old Notes and delivered the wrong status, therefore **R5/R4-1 remains actual FAIL**. R3 hard-reset task-loss evidence also remains FAIL.
- R6 has no task/Skill hint, file selection rule or extra recovery protocol and cannot close those model behavior failures. The unit remains active, with no canonical merge/archive/Ready PR or production claim.
- Final Nano 485-test/typecheck/full-build evidence is complete and inspected; no duplicate full run by reviewer. Plugin rc.5 artifact conclusions remain valid because the plugin dependency/bytes did not change.
- `requires_full_verification: false` for closure of the declared deterministic consumer delta on the frozen source. Only this verification report was edited; caller owns commit and runtime/evidence handoff.

## Final scope and current-spec reconciliation

### Validated snapshot and verdict

- Requested scope commit: `34e0ab6d924821d0ded6a8ce8088cba9b456c718`. Actual checkout on entry: `5fa5db7b9ed5e58afaba36dc50bc36517fc49270`; its only additional change from the requested commit is the independent final product disposition appended to `regression.md`.
- Effective executable source remains Nano `839880856ca9b8d9717fe0045bbc34a7b479de5c`, plugin `823a2029d216cc5e128a76976abc7b0c84df4690`, immutable rc.5 with previously verified artifact/lock/install. Confirmed no subsequent delta in integration source/tests, package manifest or lock.
- `verification_mode`: corrected-delta/final scope reconciliation. Prior code-review findings `[]` retained; no new code review or full test run required for documentation-only scope closure.

**Final scoped gate: PASS — completeness satisfied, implementation/current-spec delta aligned, architecture coherent; 0 CRITICAL / 0 WARNING / 0 SUGGESTION within this delivery.** The explicit user scope decision allows the already-validated repair to proceed to merge/deployment while the known forced-reset Notes-selection failure remains tracked as [#377](https://github.com/Mrchen116/nano-multiagent/issues/377). It does not convert that failure into success.

### Scope and current contract checks

| Check | Evidence | Conclusion |
|---|---|---|
| User-authorized delivered scope | `incident.md` opening delivery section lists stable context contribution, no extra used-Skill replay, native pressure pruning, Notes hint format and once-only complete live-Inbox Skill extraction. `design.md` Final delivery scope mirrors that split and links #377 | consistent with implemented and validated final behavior |
| Three delta scenarios merged | Compared complete scenario blocks programmatically: batch pressure/native pruning; long-task Skill lifecycle; live-Inbox explicit Skill gestures. Exactly 3 delta blocks, all exact full-text matches in current `docs/specs/gateway/agent-capabilities.md` | aligned; no missing condition, widened source or changed guarantee introduced in the merge |
| Old current scenarios retained | Diff of current spec only adds those 21 lines; existing multi-window and original-detail scenarios are untouched. Final delta removes their previously repeated unchanged text | no accidental canonical deletion or invented acceptance of the known failing boundary |
| Known failure preserved and separately owned | `incident.md` marks forced-reset recovery deferred to #377; `design.md` final scope and `regression.md` final disposition preserve R3/R4-1/R5 FAIL and identify out-of-unit #377 | failed evidence stays failed; no additional recovery hints/protocol or widened implementation |
| Independent product acceptance | `regression.md` final scope section at commit `5fa5db7b9` gives PASS for the user-confirmed delivery, based on same-25-volume Web IM/prune/current-task preservation/one correct delivery, Skill/source/restart/old-mode evidence | current scoped product exit criteria complete; no unresolved in-scope product blocker |
| Original production request replay | Read `production-replay.md`: fixed source/rc.5, exact completed-turn prefix and scheduled/Inbox ordering, actual journal reads, 10 real requests with 5 constant snapshots, one substantive todo answer captured by isolated sink, 0 resets/errors | useful supplementary causal evidence, not a new independent Web IM/Feishu/production receipt or proof of unavoidable-reset recovery |

### Evidence retained and delivery boundary

Reuse final installed Nano 107 files / **485 tests**, typecheck/full build, plugin 9 files / **31 tests** plus typecheck/build, meaningful red/green evidence and independent code review from the already-frozen source. No new implementation, dependency, fixture or runtime change calls those checks into question. Reviewer re-ran only text comparison and `git diff --check`; no service was controlled or product message sent.

Earlier statements that the full unit could not proceed without solving old-Notes selection described the prior broader scope. They are superseded for delivery disposition by this explicit user decision and the final product report; the underlying FAIL records and known limitation remain. New canonical scenarios cover the verified pressure and Skill behaviors, not a claim that forced-reset task selection is generally solved. Any implementation intended to close #377 requires its own agreed scope and evidence.

This final verifier gate is complete and ready for the caller's authorized delivery steps. It does not itself merge, archive, deploy, restart production or claim version/connection/user-visible acceptance after deployment. Only this report was modified and committed by this reviewer.
