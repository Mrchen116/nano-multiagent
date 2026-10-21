# Verification Report: bugfix-629-context-recovery

> Latest conclusion: **Round 4 below reviews the native-pruner delta**. R3 original-incident acceptance is FAIL and remains recorded; R4 product acceptance is pending. Earlier static passes do not establish product success. No Ready-for-PR, canonical merge or completed-unit conclusion is issued.

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

Current reconciliation: approved R4 design/delta at Nano `06c7aec52d759c45dd9db82bfef0a2a052b47b6e`, plugin `ce7d551ef90811191fb190a99f04ba74e961e14c`. Recheck scope is the R3 → R4 native-pruning delta; other valid evidence is retained.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `agent-capabilities.md:7-11` same work across windows | Original Notes and window/item History retained, no extra current-turn protocol | Native multi-window/session replay coverage retained; R3 original-incident product report shows actual task loss | Mechanism unchanged; R3 hard-reset recovery FAIL is not closed by R4 pruning |
| `agent-capabilities.md:13-18` consumed task plus batch tool-result pressure | Plugin `src/index.ts:139-151,225-231,279,346-348`: public pruner before pressure decision, same budget remeasurement, existing overflow reset afterward | R4 published-pruner integration: batch avoids reset and retains task; unprunable content still resets; public pressure/overflow/explicit behavior covered | aligned at native request seam; same-25-volume real delivery pending |
| `agent-capabilities.md:20-23` original detail and honest gap | Existing History reads originals removed from active surface by native prune; native replacements preserve source links and visible prune marker | Prior complete arguments/result/Unicode pagination tests retained; R4 original results retained and replayed | aligned; correct interpretation of truncated preview remains product validation |
| `agent-capabilities.md:25-31` native Skill catalog, no old body/index, restricted History, old-mode behavior | R3 Nano hook and native catalog/source paths unchanged | Retain R3 installed 5-test matrix, real seven-Skill catalog/no-growth/one-Skill re-read, workflow-only real History/source recovery from `regression.md:80-91` | aligned for retained coverage; unexecuted real Node restart/off-on not upgraded to pass |

### Uncovered Observable Behavior

No uncovered new observable behavior found in the R4 delta. Pruning-at-W, remeasurement before H, original record retention, no unnecessary reset when pressure is removed, existing reset when still above H, and absence of new task hints are explicit in the corrected batch-pressure scenario and design decision 6. Public pressure and overflow wiring are included in the same approved mechanism; explicit reset and no-service behavior are intentionally retained. R3 Skill and protocol-removal behavior is unchanged.

Outcome: **aligned** for the inspected R4 delta/implementation. R4 overall verification is pending on its product exit criterion. R3 V1 is actual FAIL, not pending or passed; R4 preventing one avoidable reset will not prove recovery after every unprunable hard reset. `requires_full_verification: false`: targeted delta review suffices; unchanged valid evidence is retained.

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
