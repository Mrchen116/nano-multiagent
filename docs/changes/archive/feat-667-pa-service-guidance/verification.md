# Verification Report: feat-667-pa-service-guidance

> Validation snapshot: `c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5` → `7ddaceb942423436bc656fba6707b04f131c9cb1`

Latest status: **Round 5 passes final bounded reconciliation**: V1 completion evidence is closed, V2 remains closed, and all three final gateway deltas are aligned. Earlier pending verdicts remain historical snapshots. Canonical merge/archive and this unit's PR/CI/deployment are subsequent delivery actions, not claimed completed by this report.

## Round 1

- Reviewer: independent `/root/pa667_static_review`.
- verification_mode: `full`; review_round: `1`.
- Scope: all M1 exit criteria, all unit Requirements/Scenarios, design decisions, gateway delta-specs, and currently available implementation/test evidence. Reuses the full Context Implementation Review in `M1/code-review.md`.
- verdict: **pending evidence / not pass**. One CRITICAL completion-evidence issue, zero WARNING, zero SUGGESTION. No confirmed implementation defect or implementation/design mismatch was found.
- requires_full_verification: `false`; remaining work is bounded completion-evidence reconciliation for the existing M1 criteria, not another full code review.

## Summary

| Dimension | Result |
|---|---|
| Completeness | All 10 unit scenarios have implementation mapping; M1's required real-model/product evidence was not yet supplied at this snapshot. M1 remains incomplete. |
| Correctness | Available native runtime/schema/enforcement/depth tests support the engineering claims; real model behavior remains unverified. |
| Coherence | Implementation follows the A+B design and repository boundaries. No current-spec merge is performed in the active unit. |

## Completeness

- Tasks: single M1; implementation exists, but its combined worker/reviewer exit criteria are not all closed. No tasks/progress artifact is required for this simplified workflow.
- Spec: all declared scenarios map to the three service texts and existing runtime/product mechanisms; the additional delegation layer and root-only product chat boundary are implemented.
- Prototype / Reference: N/A; no frontend prototype or client change.
- Current specs reviewed: `gateway/personal-agent.md` (identity, observation, source permissions, disclosure, configurable guidance); `gateway/global-agent.md` (root coordination, explicit public delivery and lifecycle); relevant `gateway/agent-capabilities.md` and `gateway/task-graphs.md` contracts. The active deltas intentionally extend behavior; they do not overwrite current specs before completion.

## Correctness

| Requirement / Scenario | Implementation location | Available evidence | Status |
|---|---|---|---|
| 小事直接完成 | `apps/im-server/src/personal-agent-defaults.ts:2,10` | Default text and existing first-create configuration seam | Implemented; real result pending |
| 长事项持续交付并说明能力边界 | default instructions; `nano-ongoing-work/SKILL.md:9-21,52-59` | Actual executor ID/record/delivery instructions; native continuation tests | Implemented; real long-task result pending |
| 更正与短问题 | `nano-ongoing-work/SKILL.md:25-28` | Native same-child continuation available; no supplied two-work real-model correction/short-answer trace | Implemented; real scenario pending |
| 单项停止 | `nano-ongoing-work/SKILL.md:30-34` | Existing cancellation semantics retained; explicit user scope and no late-result restart guidance | Implemented; actual A-only stop/B delivery pending |
| 承诺后的实际准备 | `nano-proactive-care/SKILL.md:8-21` | Source verification/private preparation/delivery limits in text; source and disclosure mechanisms retained | Implemented; real private draft and absence of public send pending |
| 已处理、无新价值和覆盖不足 | `nano-proactive-care/SKILL.md:12-14,23-27` | Instructions preserve uncertainty and stop stale/redundant preparation | Implemented; real processed/quiet/incomplete-source cases pending |
| 自定义、清空和禁用保持 | unchanged PA creation/config paths; `agent-config.ts:133-134,155-176`; `capabilities.ts` Skill filtering | Existing personal-agent, personal-security and capability coverage; no backfill logic added | Engineering protection available; product choice checks pending |
| 任务执行者可再委派一层 | `client.ts:26`; unchanged native subagent mechanism | `/tmp/pa667-child-green6.log` 2 passes, `/tmp/pa667-depth-green2.log` 3 passes; reviewer explicit-override probe | Default depth engineering verified; #361 two-level Ready PR/CI and progressive delivery pending |
| 子 Agent 只进行内部通信 | `agent-config.ts:105-139`; `global-mode.ts:79-86`; `global-agent.ts:411-415`; role-sensitive Task/UI/security | Ordinary Global/PA actual runtime schema + spawn/fork/cold resume and internal tool results; direct product-send rejection; reviewer deferred-feedback capture | Engineering verified; real parent source request/read/final public delivery pending |
| 主人要求接续已停止事项 | `nano-ongoing-work/SKILL.md:32-34` | Native same-ID cold continuation available; no automatic restart promise added | Implemented; explicit owner resume of stopped original worker pending |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| A limited to editable initial Persona plus two packaged Skills | Yes | Exactly the declared service-text locations; no new ledger/scheduler or #414 memory structure |
| Native default maxDepth 1→2; caller override preserved | Yes | Default preceding caller patches in `client.ts:26`; native depth tests and reviewer explicit maxDepth=1 execution probe |
| Product chat tools only on Global roots, native internal messaging retained | Yes | Root-local registration, actual child send schema, product session guard and cold-resume evidence |
| Root handles Task responsibility and executor coordination without new hard binding | Yes | Skill/Task guidance; no Task-child field, executor manager or Task protocol migration |
| Child current guidance consistent with available tools | Yes for covered engineering seams | Static Task/UI/security branches plus actual runtime child prompts, schemas and deferred feedback; real model consumption still pending |
| Existing user choices and source/disclosure boundaries retained | Yes in implementation | No default backfill or replacement configuration path; inherited source/approval checks remain; existing user-choice testing retained |
| No independent observer, runtime fork/private import, client rebuild or production migration | Yes | Full diff inspected; no such additions |

### Prototype / Reference Contract

N/A.

## Evidence ledger and limitations

- `/tmp/pa667-child-green6.log`: `global-child-tools.test.ts`, 2/2 passed. Ordinary Global and PA, real locked native runtime, model-stream fixture; root/first/second child schemas, fork, internal messaging and cold continuation. It does not prove real-model task selection.
- `/tmp/pa667-depth-green2.log`: `trajectory-runs.test.ts`, 3/3 passed. Default depth-2 execution, rejected depth-3 ordinary creation, causal run records and cold reads.
- `/tmp/pa667-affected.log`: 82 passed / 1 failed, where the failed personal-child-delivery expectation still required the now-forbidden child public send. This is a historical run, not an all-green result. The committed test now expects refusal; its corrected case passed in `/tmp/pa667-depth-green.log`. That later log's trajectory failure was an incorrect result-field locator, subsequently corrected and passed in green2. Do not count either historical failure as an unresolved product failure or as a fully green combined gate.
- `/tmp/pa667-build.log`: workspace build passed. The generated installer footer names the pre-commit base; the caller supplied it as the build of this implementation before commit, so it is used as caller-attributed build evidence rather than independent commit-stamped provenance.
- `/tmp/pa667-static-probe.log`: independently executed during this review on confirmed HEAD, Node 24.22.1, locked runtime. A later explicit maxDepth=1 overrides the new default and rejects second-level creation. A Global child Task.apply produces actual next-request feedback routed to parent via agent_id/message, preserving fixed conversation and not repeating the root public-send demand. Controlled model responses; no real-model behavior claim. Isolated runtime shutdown and home cleanup completed.
- No final real-model/product acceptance artifact or main/candidate finite comparison was available to this reviewer. No production data, service or #414 old workspace was used.

## Issues

### CRITICAL

- **V1 — M1 completion evidence is still outstanding (CONFIRMED evidence gap, not a confirmed product defect).** Contract: `design.md:101-107,113`. Current runtime fixtures cannot satisfy the mandated real-model/product results: finite baseline/candidate comparisons; actual Skill discovery/loading; user-requested #361 two-level implementation with independent Ready PR/CI and root delivery; two simultaneous works with correction/short question/A-only stop/B result and explicit original-worker resume; private useful preparation followed by handled/no-value quietness and incomplete-source uncertainty; user-choice product checks; child request → root source read → root public delivery. These activities were explicitly reported as in progress, and none is presumed failed or complete. **Action:** retain incomplete/Draft status, supply version/model/config/input/tool-result/output locators from the independent acceptance work, then reconcile only these criteria and any actual discovered fix delta. Do not amend spec to erase them or re-run an unrelated complete suite.

### WARNING

None.

### SUGGESTION

None.

## Delta reconciliation

The three active gateway delta-specs match the intended implemented changes: PA service guidance/private preparation, Global root-only product tools and lifecycle consistency, and default two-layer delegation with native refusal at the third layer. No additional externally observable behavior in the unit diff was found missing from those deltas. Task data and IM protocols remain unchanged. This is implementation alignment, not confirmation of the pending model behavior outcomes.

Outcome: implementation aligned; final M1 verdict awaits V1 evidence closure.

## Round 2 — bounded completion-evidence reconciliation

- verification_mode: `targeted-closure`; review_round: `2`; focus: V1 and the single test-timeout patch.
- Prior implementation snapshot: `7ddaceb942423436bc656fba6707b04f131c9cb1`; current validated head: `32e2fd74c0262e286ab8807dcb259c5572446a87`. Product source has not changed between these heads, so the independent product report's runtime snapshot and Round 1 implementation mapping remain valid.
- verdict: **pending / not pass**. CRITICAL: 1 narrowed completion-evidence gap; WARNING: 0; SUGGESTION: 0. No confirmed implementation defect.
- requires_full_verification: `false`. Do not repeat the completed scenarios or full source review; the next review is limited to new #361 completion evidence and any actual fix delta.

### Newly verified engineering evidence

| Evidence | Reviewed result and applicability |
|---|---|
| `/tmp/pa667-alltests-serialbudget.log` | 143 backend files / 768 tests pass in 294.09s. `M1/implementation.md` records `--maxWorkers=2` and prior default-poll/resource-contention timeouts, so the final pass is not represented as an unconditional timing guarantee. |
| `/tmp/pa667-frontend2.log` | 108 frontend files / 1,031 tests pass. |
| Durable `checks/pa667-pytest.log` | 70 pass, 32 deselected. |
| Durable `checks/pa667-typecheck.log`, `pa667-build.log` | Typecheck and workspace build pass; original build footer provenance limitation from Round 1 remains. |
| Durable `checks/pa667-docscheck.log`, `pa667-ruff.log`, `pa667-ruff-format.log`, `pa667-iosruntime.log` | Docs integrity, Ruff check/format and native interactive generated-asset/typecheck gates pass. |
| `knowledge-review.test.ts:207` patch | Only explicit poll deadline added; expected error/completion, facts, stored content, retry and interval assertions unchanged. Adjacent completion poll already uses 8 seconds. No product implementation or 20-second outer deadline change. Code review Round 2 returns `[]`. |

Durable evidence root: `/Users/czj/.codex/reports/feat-667-pa-service-guidance-20261027/`. Its README maps the original temporary locators to preserved files and identifies runtime `7ddaceb`; no incomplete #361 implementation was inspected. Both completed ordinary acceptance stacks were reported stopped; this reviewer started no service or replacement experiment.

### V1 reconciliation against independent product evidence

Reviewed independent `acceptance.md` committed at `f37ce20c0`, including model/configuration, ordinary user inputs, actual tool receipts, user-visible messages, explicit limitations, and the retained provider/source evidence. The candidate uses `codexOAuth:gpt-6-astra` / medium; the same-runtime main-text comparison uses the same model, tools and fresh isolated workspace. The finite comparison supports only the three observed cases and does not establish an improvement percentage or lower latency.

| Criterion / scenario | New evidence and result | Closure |
|---|---|---|
| 小事直接完成 | Actual useful recipe `61605d…`; direct answer without requiring Task/team management. | Closed / pass |
| 长事项持续交付并说明能力边界 | A's full 45-minute training draft `11996cc…` and B's full 102-yuan dinner/purchase result `7cdc157…` delivered. User-designated #361 complete development remains outstanding. | Ordinary work supported; #361-dependent row remains inconclusive |
| 更正与短问题 | A/B have distinct continuable IDs; correction reaches original A and short question receives actual reply `230e176…`. | Closed / pass |
| 单项停止 | Actual interrupt of original A and inactive observation, while B continues and delivers after fresh-message revalidation. | Closed / pass |
| 承诺后的实际准备 | Independent observed book-exchange commitment, original-message/source checks, loaded proactive-care, useful private draft `581ec5…`, observed-group audit with no PA public send. | Closed / pass |
| 已处理、无新价值和覆盖不足 | Handled update and unchanged recheck are quiet; unavailable-source reply `68bf7…` preserves unknown coverage. | Closed / pass |
| 自定义、清空和禁用保持 | Same binding on retry; custom/empty configuration and actual provider requests show chosen Persona and Skill discoverability. New PA default captured separately. | Closed / pass |
| 任务执行者可再委派一层 | Engineering depth-2/depth-3 boundary already verified; required #361 independent Ready PR/CI and completed progressive delivery not yet supplied. | Still open / inconclusive |
| 子 Agent 只进行内部通信 | Actual candidate first-level and original-A resumed provider schemas lack root product tools/public send parameters. Only the #361 second-level real task and progressive result path remain for this acceptance row. | First-level/resume supported; #361-dependent row remains inconclusive |
| 主人要求接续已停止事项 | Explicit owner resume → same original A → verified full final draft sent; B not duplicated. | Closed / pass |
| Actual Skill consumption and three finite comparisons | Original ledgers record ongoing-work and proactive-care calls. Main/candidate short tasks both complete; both correct original long workers; private-preparation difference is limited to this single observed case. | Closed within stated finite scope |

Bounded spot checks of preserved raw artifacts support reuse of the independent report: `tool-ledger.json` contains the exact original A correction, interrupt and explicit resume IDs and the two Skill loads; `schema-ledger.json` records root product and internal-only rows; baseline provider inputs `1793091409207171000.json` and `1793091430140627000.json` contain, respectively, the chosen custom Persona and no custom/main/candidate default Persona. This verification does not redo product acceptance or generalize from one trace.

### Remaining issue and next action

**V1 remains open only for the user-required #361 independent Ready PR/CI plus completed two-level execution and progressive root delivery** (`design.md:103,107,113`; acceptance A1). This affects three dependent acceptance rows: the complete long-work requirement, executor re-delegation and the second-level internal-result/delivery path. The independent report has not observed failure; it correctly leaves them inconclusive. Existing native depth/schema/internal communication tests and execution IDs cannot replace that completed development outcome.

Action: keep M1 incomplete and do not declare acceptance pass/Ready. Once the ongoing original #361 chain supplies its final independent PR, CI and versioned root → first-level → second-level → parent/root result/delivery evidence, reconcile only those items and any actual code fix. All seven ordinary scenario results, choice checks, Skill-consumption evidence, finite comparison and successful engineering gates remain retained. No new full review or ordinary scenario rerun is required solely because #361 is still running.

## Round 3 — corrected coordination delta

- Reviewer: independent `/root/pa_authorization_review`; review date: 2026-10-27.
- verification_mode: `corrected-delta`; scope: only the coordination correction in `87bcbe387..003c09589b540d012f1a284623b2886be9f7b0f7`, plus document-only closure `fdcd95ab5f246bccd2c6fd0e615096ac97718da8`, including the corrected Global delta, design addition and three affected product-guidance locations. Reuses code/Context review Round 4; unaffected prior conclusions are retained.
- Outcome: **aligned / pass for this corrected delta**. CRITICAL 0, WARNING 0, SUGGESTION 0. No implementation mismatch or architecture violation found. `requires_full_verification: false`.
- The whole-unit verdict is still pending: prior #361 PR/CI and final root-delivery evidence is outside this patch reconciliation and is not closed by a next-step probe.

### Corrected Delta Reconciliation

| Delta item | Implementation evidence | Validation evidence | Outcome |
| --- | --- | --- | --- |
| `specs/gateway/global-agent.md:32-36`, internal progress without parent intervention | `global-mode.ts:19,85`; ongoing-work lines 13-20,26,31-32: no receipt/continue loop or automatic progress forwarding/note rewrite; routine work continues; meaningful final result retained | Exact final root/child native context captures; two quiet root probes; final recovered-child probe chooses a next check. Replay tools are not executed. | aligned |
| `specs/gateway/global-agent.md:38-41`, necessary communication and final delivery | Same root/child guidance; ongoing-work lines 33,38-48,62-73; `task-graphs.ts:21` and unchanged deferred-feedback path retain actual waiting/results and fixed conversation | Real-blocker decision probe and synthetic status-question probe; reused native internal communication/Task/child delivery checks; no full final-delivery product rerun | aligned within the stated probe/engineering scope |
| Complete replacement of current Requirement `全局 Agent 在任务执行期间主动沟通` | `global-mode.ts:19` still requires initial acknowledgment before deep work, respects no-reply, and distinguishes acknowledgment/private prose from actual final delivery | Current `docs/specs/gateway/global-agent.md:266-276`; corrected delta lines 20-41 at `fdcd95ab5`; complete initial and long-task scenarios retained in accordance with `docs/specs/CONTRIBUTING.md:134,143,154` | aligned; V2 closed |

### Coherence and validation limits

The implementation follows `design.md:39`'s coordination decision and repository boundaries: the changes are guidance only, with no new message filter, scheduler, Task protocol, persistence mechanism, permission bypass or runtime fork. Continuable/fork return modes agree with the locked runtime, and root-only public delivery/source checks remain. No frontend reference applies.

Evidence is reused from `M1/coordination-fix.md` and `/Users/czj/.codex/reports/feat-667-pa-service-guidance-20261027/coordination-fix/`, independently inspected in code review Round 4. Native snapshots prove the exact final guidance reaches ordinary Global/PA roots, children and the existing cold-resume fixture. Astra medium replay results prove bounded next-step choices with retained tools/history and disclosed loaded-Skill substitutions. The earlier child counterexample, mislabeled extra baseline, retained explicit milestone-report case, synthetic status input and first-candidate root-probe scope remain limitations rather than hidden successes. Relevant build and ten distinct existing checks are reused; no full regression or new long task was run by this reviewer.

### Issues and closure

None remain in the assigned corrected delta. **V2 closed:** `fdcd95ab5` changes only the delta document and restores the complete `接到真人任务` scenario plus the long-task scenario's no-reply and delivery distinctions, replacing only the update-cadence clause. Direct comparison confirms early acknowledgment to the original conversation and the distinction between acknowledgments/private drafts and real result delivery are preserved. No product change or full-suite rerun was required for this document closure.

### Uncovered Observable Behavior

None found within the assigned patch after V2 closure. Final whole-unit acceptance and #361 PR/CI/root delivery remain independently outstanding; this report does not infer their completion from the caller's progress update. The caller's planned service restart and real tryout after the #361 PR are subsequent product evidence, not prerequisites invented by this bounded document reconciliation.

## Round 4 — corrected simple-request acknowledgment delta

- Reviewer: independent `/root/pa_authorization_review`; review date: 2026-10-28.
- verification_mode: `corrected-delta`; scope: only `d76a7c6cd..985bc6f07883a55f70e293b65b3737370f08eab7`, reusing code/Context review Round 5.
- Outcome: **aligned / pass for this corrected delta**. CRITICAL 0, WARNING 0, SUGGESTION 0; `requires_full_verification: false`. This is implementation/contract alignment, not a new whole-unit product-acceptance verdict.

### Corrected Delta Reconciliation

| Delta item | Implementation and evidence | Outcome |
| --- | --- | --- |
| Global delta lines 22-24, simple requests directly deliver the result | `global-mode.ts:19` now limits mandatory preliminary acknowledgment to long-running tasks; ongoing-work line 73 uses the same qualifier. Existing requested-answer delivery guidance remains. Exact frozen root text appears in ordinary Global/PA native captures; pre-fix two-send behavior is recorded in `simple-request-before.json`. No post-fix real-model choice is claimed. | aligned at implementation/assembly level; behavior unverified |
| Global delta lines 26-34, long-task acknowledgment and updates | Long-task acknowledgment still precedes deep work in the original conversation, unless no reply is requested; update cadence, status responses, concise updates and acknowledgment-versus-delivery distinctions are retained. Exact source comparison confirms only the qualifier and corresponding Skill clause changed. | aligned |
| Design coordination decision and complete modified requirement | `design.md:39` limits the retained acknowledgment to long tasks; the complete Global modified requirement preserves internal coordination, necessary communication, stop/correction, real receipts and final delivery. No new runtime, permission, UI or scheduling behavior was added. | aligned |

Evidence reused: `coordination-fix/pa667-simple-ack-build.log` (related build pass), `pa667-simple-ack-tests-final.log` (one-off existing native fixture 2/2), and `pa667-simple-ack-context-{false,true}.json` (exact final Global/PA system inputs), under `/Users/czj/.codex/reports/feat-667-pa-service-guidance-20261027/`. The model-input fixture demonstrates delivery of the changed guidance and retained native boundaries; it is not a real-model behavior test or a replay of the user's simple request. The existing Skill's unchanged discovery/installation mechanism is reused; this inspection does not establish an update to already loaded Skill text in the running PA.

### Issues and Uncovered Observable Behavior

None found within this small corrected delta. The user-requested implementation remains two qualifiers, without a simple-request checklist or expanded instructions. Post-fix simple-request behavior is explicitly unverified, and the running #420 executor was not restarted or interrupted for this review. Prior long-task, PR/CI and whole-unit acceptance evidence are not reopened or reconciled by this patch review.

## Round 5 — final bounded completion and corrected-delta closure

- Reviewer: independent `/root/pa_authorization_review`; review date: 2026-10-28.
- verification_mode: `targeted-closure` for V1 plus `corrected-delta` for the three final gateway deltas. Reuses the existing full engineering, code/Context and independent product reviews; does not repeat them.
- Effective base: `39ce046cc2f228fc2be41f1418452b512df4ff75`; product source effective through `727be381aa0d4c6213f191a3da3c2a9a6b49f722`; independent final acceptance record: `5a1e0afa6a9fcc819dd289c9475529ed018b81e6`. These are integration/review bounds, not the execution versions of every historical journey.
- Verdict: **PASS** for final unit verification, with the evidence boundaries below. CRITICAL 0, WARNING 0, SUGGESTION 0. V1 closed; V2 closed. `requires_full_verification: false`; corrected-delta outcome: **aligned**.

### V1 actual completion evidence

Independent `acceptance.md` Round 3 at `5a1e0afa6` closes the three #361-dependent rows with actual completed development, internal returns and public delivery. Bounded spot checks in `/tmp/pa667-361-final-review/` and the original `/tmp/pa667-issue361-runtime/provider-requests/` support reuse:

| Prior gap | Verified closure evidence | Result |
| --- | --- | --- |
| Complete long-work outcome | [Ready PR #419](https://github.com/Mrchen116/nano-multiagent/pull/419), head `77468b4717b6e63ea4fec9fba9da9996f6cc92ed`, CI `40529144631` completed/success, independently checked by the product reviewer; retained `ci-watch.log` ends with backend/frontend success and iOS detection success, with native iOS correctly skipped. | closed |
| Actual second-level execution and return | Root `5524e22e…` → continuable `54612f0b…` → real implementer `fecdbd2e…`; call `47fbcdc8…` starts the implementer, and `239a7eff…` sends commit `dfee3df4…`, tests and limits back to the actual parent with a delivered receipt. Independent design/product/static roles and final archived task reports are recorded, rather than substituting maintenance sessions or a depth-only probe. | closed |
| Complete internal-result / root-public-delivery path | Call `044de914…` returns same-head green CI from first-level to root with an internal delivered receipt. Call `50805cec…` sends final PR/head/CI/result/limitations to the original owner conversation with `status=sent`, message `a9c9b221560b436a8936e0aaecb196cc`. Independently checked original WS events 131/132 confirm created/completed for that same message. | closed |
| Actual child versus root schemas | Spot-checked requests `1793095399827258000.json` and `1793114555726795000.json`: child send has only `agent_id/message`, without inbox/conversations/representation. Root final request `1793114589133299000.json` retains product tools and `target/text`. | closed within observed real chain |

The original seven ordinary scenario results and finite comparisons remain valid at their original versions. Acceptance Round 2's corrected natural trial supplies the independently verified two-input continuation, successful distinct IM/Vite Sol replies, honest retention of the earlier DeepSeek 402 failure, Luna reviewer configuration, original-worker continuation and actual owner delivery. The later natural-trial PR #416 / CI `40514929820` evidence explicitly includes the two further human PR-status/creation messages; it is not one-input autonomous PR completion. Product reviewer Round 3 retains these results and declares PASS without inventing another journey. The user's separate personal acceptance is recorded as human feedback, not a substitute for these technical records.

### All final corrected deltas and canonical mapping

Reviewed the final active deltas and `/tmp/pa667-canonical-merge-preview.patch`; the preview has not been applied by this reviewer. Complete `MODIFIED` entries replace their same-named current requirements while retaining unchanged obligations; `ADDED` entries introduce only the reviewed behavior.

| Final delta | Implementation / retained validation | Outcome |
| --- | --- | --- |
| `specs/gateway/agent-capabilities.md` | `client.ts` default native depth 2 with explicit override preserved; actual native depth/schema/fork/cold-resume evidence from earlier review. `policy/sources.ts` and `codex-context.ts` preserve original human scope, parent limits and pinned risk-policy exceptions; fixed Luna before/after/control evidence retains its narrow limits. Workflow wording now names only Workflow children, matching `engine.ts` filtering without expanding ordinary child capability. Preview adds depth requirement and updates the full Codex source/outcome requirement only. | aligned |
| `specs/gateway/global-agent.md` | Root-only product tools and product guard; internal-only child schema with working native messaging; role-sensitive Task/UI/security guidance. Complete communication requirement includes simple direct delivery, long-task acknowledgment/no-reply, useful update cadence, actionable internal messages, necessary stop/correction/status/final delivery and original receipt semantics. Earlier real journeys plus bounded coordination probes/native captures and V1 final return chain cover their stated scopes. Preview retains the complete corrected requirement; V2 does not recur. | aligned |
| `specs/gateway/personal-agent.md` | Creation-only editable Persona, discoverable packaged ongoing-work/proactive-care, existing custom/empty/disabled choice preservation; useful private preparation and quietness without disclosure authorization; bounded permission-blocker coordination and original-executor continuation. Existing product evidence and source/approval regression evidence are retained. Preview preserves the full existing configurable-guidance requirement and adds only the reviewed observation/blocker scenarios. | aligned |

No additional externally observable unit behavior was found missing from these deltas. No frontend prototype/reference contract applies. No new Task binding, ledger service, scheduler, provider/runtime fork, permission bypass or client migration was introduced.

### Final-main compatibility and engineering gates

`8d428779..b45b529b1` (PR #417) changes tests/fixtures, E2E/archive scripts and documentation, with no production runtime source. The merge at `8294c698c` retains prior product/Context evidence; `checks/pa667-final-*` records 14 backend/native, 75 frontend and 84 non-E2E Python checks, Ruff, workspace build/typecheck and packaged iOS-runtime check passing. The build footer names that merge head.

`b45b529b1..39ce046cc` (PR #421), integrated at `727be381a`, adds optional `RuntimeEvent.surfaceOp` typing and excludes model-context replace events from new Work/SingleThread tool-completion cards. Bounded code review checked the actual callers and unchanged durable model events; the change does not touch delegated tools, model input, Skill, policy or source authorization. `checks/pa667-main421-*` records 22 store checks, affected-package build and full typecheck passing. Prior raw evidence retains its provenance; historic display-duration anomalies are not recertified as exact timing. These main increments do not require repeating the existing full suite or real task matrix.

### Preserved limits and release readiness

- #361 was explicitly instructed to delegate and later received external diagnosis, bounded data/API authorization clarification, f0 runtime replacement with same-worker continuation, and caller help with a target-repository Git authentication mismatch. It establishes completed instructed execution, not a fully unassisted autonomous run. Natural PA organization is supported separately, with the stated additional human inputs and model-route limits.
- The unresolved ancillary notice-availability observation is retained and not declared fixed or proven preexisting. The independent product review explains that redesigning that propagation is outside the #361 retry acceptance scope; no surviving unit invariant violation was established by it.
- The long-task acknowledgment qualifier `985bc6f07` and Workflow-child qualifier `384ab2710` were not reloaded into the personal-trial runtime or tested in another complete real-model journey. Their limited code/assembly evidence is recorded in code-review Rounds 5/6. User acceptance of the prior real trial does not erase that limitation.
- Sol normal-chat success does not repair the default DeepSeek quota route. Synthetic fixtures/native assembly are not model-choice or end-to-end performance evidence; no delivery-speed improvement percentage is claimed.

The required bounded verification is complete. **Canonical merge and unit archive may proceed**, followed by this unit's own PR/CI, authorized merge and deployment. This report does not assert those later actions or a package release have occurred. No product code, services or runtime data were changed by this verifier; only review reports were edited.
