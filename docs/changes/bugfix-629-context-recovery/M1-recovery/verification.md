# Verification Report: bugfix-629-context-recovery

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

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `agent-capabilities.md:7-11` same work across windows | Exact `turn_id` filter and persisted checkpoint references | Plugin history/safety, including two windows and replay | aligned at implementation seam; product outcome pending |
| `agent-capabilities.md:13-17` consumed new task with stale Notes | Current open-turn metadata, recovery instruction, source-preserving archived read | Default-budget pressure and overflow regressions | aligned at implementation seam; real continuation/delivery pending |
| `agent-capabilities.md:19-22` original detail and honest gap | Existing bounded `read` and pagination paths retained, not_found/not_archived preserved | Existing complete arguments/result, Unicode tail and missing reference tests | aligned |
| `agent-capabilities.md:24-28` approved Skill restoration and stable ordinary progress | Scoped callable check; name/path navigation or restricted full-body branch | Four native permission/engine combinations and fixed request comparison | aligned at implementation seam; real re-read/large-Skill matrix pending |

### Uncovered Observable Behavior

No additional product-facing behavior in the complete implementation diffs requires a separate delta requirement. The new History `turn_id` parameter/item metadata, reference-on-demand guidance, and restricted full-body restoration are the approved design mechanisms for the stated behavior. Existing fallback and authorization requirements remain current; the diff does not change those contracts.

Outcome: **aligned** for the inspected delta and implementation. This is not an overall verification pass while V1/V2 remain open. `requires_full_verification: false` for continuing closure on the same implementation; a substantive implementation/design change must be scoped again by the caller.

Report ownership: caller will commit this report in the shared unit branch. No review service/process was started; nothing requires cleanup. Await supplementary evidence through the caller; do not poll product execution.
