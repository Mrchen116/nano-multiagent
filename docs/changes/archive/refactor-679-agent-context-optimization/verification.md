# Verification Report — refactor-679 final frozen full review

> Mode: **full + corrected-delta reconciliation**. Executed base `4b27d962c1cc09a27a567619bd5cabc3db2ee934` → full-reviewed source `b610b02b56bb3760448208dfd567f1fba8034e51`; targeted repair validation extends to `6881952b96ea3a1575f5fbad44d6a717d8fb48c9`. Branch `codex/refactor-679-on-memory`; target `unit/feat-676`. Independent verifier also performed the distinct full [code review and Context Implementation Review](code-review.md). Only the two authorized review reports were edited.

## Final evidence closure and retained scope

**Final verdict: PASS** at `6881952b96ea3a1575f5fbad44d6a717d8fb48c9`; 0 CRITICAL / 0 WARNING / 0 SUGGESTION. Code-review JSON remains `[]`; corrected-delta outcome remains **aligned**. Target Memory baseline `unit/feat-676` / `c2a7fe3c3727db2c557a28915fda6ccee5e4298e` is unchanged. The separate independent product reviewer has accepted all R1–R6 and 15 motivation scenarios, with five historical findings closed. This closes the previously pending evidence gate without rerunning the full review or any model.

Evidence boundaries remain explicit: real model/browser journeys establish the representative product behavior; native/service regression establishes deterministic lifecycle, authority and failure-state mechanisms; preserved HTTP captures establish actual adapter serialization/window/summary under controlled model responses. They do not establish every live upstream-model payload or every autonomous model/condition combination. The copied `output/refactor-679/provider-wire-{DOCUMENT,LEGACY}.json` artifacts have identical SHA-256 values to the already-inspected temporary captures and remain local ignored evidence.

**Retained through documentation-only finalization:** exact blockwise merge of the three already-audited active deltas into canonical specs, whole-unit archive and resulting relative-link migration preserve this PASS and the code-review result. Record those operations and rerun docs-check; they do not require another full implementation/Context/product review. A new semantic/code change would require only its relevant delta check. Canonical merge/archive, PR, CI, merge into Memory and cleanup are caller delivery steps; this verdict does not claim they are already done. No production deployment is included.

## Final-round summary

| Dimension | Result |
|---|---|
| Completeness | 20/20 active delta scenarios aligned; 1/1 M1 complete with R1–R6 product PASS and W1–W5 evidence accepted |
| Correctness | No surviving implementation mismatch found; prior C1/C2/C3 and scoped repair residuals are closed in the frozen source |
| Coherence | Approved architecture and design decisions followed in inspected source and applicable native/provider fixtures |
| Full verifier verdict | **PASS — V-FINAL-1 closed; ready for canonical delta merge, archive and PR to unit/feat-676** |
| Issues | 0 CRITICAL; 0 WARNING; 0 SUGGESTION; all five product findings and V-FINAL-1 closed |
| Corrected delta outcome | **aligned** for all three active deltas; final implementation, regression and required representative product evidence accepted |
| requires_full_verification | false — retained full review plus two targeted repair reviews; final evidence closure did not reopen whole-unit review |

## Completeness and evidence

The sole milestone is [M1-context-flow](design.md#milestones), including reviewer R1–R6 and worker W1–W5. The active delta has 6 IM, 10 Gateway Task and 4 Gateway capability scenarios. There is no frontend prototype/reference must-match contract (N/A). Current architecture, Gateway Task/capability/PA/Global and IM Task contracts, the testing and Context engineering guidance, approved design and active deltas were read; the historical pre-fix verdict was not reused as final PASS.

Evidence reused without repeating the parent's whole suite:

| Evidence | Scope and actual result | Limit |
|---|---|---|
| `output/refactor-679/typecheck.log` | `pnpm -r --if-present typecheck`; all workspace checks passed at frozen source | Type safety, not behavior |
| `output/refactor-679/python-tests.log` | Parent's non-e2e Python regression: 127 passed, 28 deselected, including architecture contract | Does not cover real-model/user journeys |
| `output/refactor-679/recovery-focused.log` | Passed native Task sync, child context and Schedule deletion fixtures | Mixed log: earlier Memory/provider failures are not PASS |
| `output/refactor-679/recovery-fix.log` | Memory document and owner-workspace fixtures: 8 tests passed | Mixed log: then-failing HTTP revalidation cells superseded only by recovery-wire |
| `output/refactor-679/recovery-wire.log` | Actual native/HTTP document+window and explicit legacy+summary revalidation: 2/2 passed | Controlled Anthropic SSE, not autonomous model behavior |
| [Historical scoped witnesses](review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate) | Relevant unchanged code paths: independent-input outage/recovery, hard Task-tool gate, public unread cursor, notice semantics | Narrow counterexamples only; final full review independently checked remaining source |
| Unchanged Memory/PA-source baseline fixtures | `memory-runtime.test.ts`, `memory-child-runtime.test.ts` and PA `personal-attention.test.ts` inspected: current entry refresh, same native child source invalidation/read-only, stop-use/original-child guidance | Covered by the runtime suite and final-fix-focused native empty-unread source-sync witness |
| Final runtime / docs / product evidence | `final-runtime-tests.log`: 949 passed plus one development red case subsequently closed by 53 passed; `docs-check-before-close.log`: 294 sources/68 routes passed; independent acceptance final-4 PASS at 6881952b9 | Preserve nonzero broad-run history and controlled-vs-real evidence distinction |

## Correctness — all active scenarios

The table records implementation/test alignment; the final independent product report now closes the associated R1–R6 exit conditions. Test filenames below are in the indicated owning package/app `tests/` directory. Native/HTTP rows are actual request/consumption seams; pure service rows prove only their own deterministic contract.

| Requirement / Scenario | Implementation | Regression / evidence | Alignment |
|---|---|---|---|
| IM: 改派双方获知 | [original formatter](../../../../apps/im-server/src/task-notifications.ts), assignment old/new labels and valid mentions | IM `task-notifications.test.ts`, `task-context-live.test.ts` | aligned |
| IM: 要求或关系更新 | Same formatter: requirements require latest detail read; parent/derived/alternative and directed dependency endpoints plus refs | IM `task-notifications.test.ts`, existing task tests | aligned |
| IM: 暂缓／关闭逐层传达 | Formatter selects only immediate Agent children without mutating their state | IM `task-execution.test.ts`, formatter tests | aligned |
| IM: 结果向上反馈 | Current assignee, creator and direct parent mentions; public delivery remains execution guidance | IM Task tests; integration `task-feedback.test.ts` | aligned; actual delivery in R5 |
| IM: 成员失去任务处理资格 | [authority transaction](../../../../apps/im-server/src/task-context-access.ts), persistent terminal revoke, claimed-batch filter and current unread cursor | IM `task-context-revocations.test.ts`, `task-context-live.test.ts`; integration `task-context-originals.test.ts`; scoped public-cursor witness | aligned |
| IM: 无业务变化与通知后的行动 | Semantic comparisons; one transactional original/relay/index; passive intake | IM migration/live tests; PA `task-context.test.ts`; native Task sync | aligned |
| Gateway: 停止通知延迟消费 | Authenticated original /stop, durable timestamps/fences, passive original injection, no fence-release wake | Integration `task-context-sync.test.ts` stop/cold restore/UI-resume cases and `task-execution.test.ts` | aligned |
| Gateway: 外部变更与离线恢复 | [fixed-cut sync](../../../../packages/personal-assistant/src/task-context.ts), persist-before-cursor, all pending revalidation, original ID evidence, unavailable independent-input separation | PA `task-context.test.ts` (>32); IM revocations/migration; native sync/originals and scoped outage witness | aligned |
| Gateway: 内部对象重建而事实未变 | No shown-delta private message; consumed original evidence reconciles lost ACK; native environment update owners unchanged | Integration `task-context-originals.test.ts`, `context-order-provider.test.ts`, Task execution | aligned |
| Gateway: 首次等待及校验失败 | Existing atomic waiting validation plus native owner/session/active/future proof | IM/PA Task execution tests; integration schedule inspection and execution tests | aligned |
| Gateway: 安静等待与安排失效 | Full current responsibilities, distinct repairs/limitations, unchanged-fingerprint limited suppression | Integration `task-execution-limits.test.ts`, `task-reminder-batch.test.ts`, Task execution | aligned |
| Gateway: 关联 Schedule 被删除 | [durable deletion owner](../../../../packages/personal-assistant/src/schedule-deletions.ts), Node UI and native tool converge; current Task reread and independent repair | PA `schedule-deletions.test.ts`; integration `schedule-deletion-native.test.ts` incl cold continuable and unsupported one-shot pending | aligned; real user/tool behavior in R4 |
| Gateway: 提前答复与定时复查 | Native Schedule evidence checks and current state; due occurrence avoids duplicate invalid-schedule wake | Integration `task-execution.test.ts`, `task-reminder-batch.test.ts` | aligned |
| Gateway: 一轮结束仍有可执行责任 | [current Task driver](../../../../packages/dsh-integration/src/task-execution.ts), D4 only genuine continuation, all own doing/waiting, held actions | Integration Task execution/limits, HTTP context revalidation, child context | aligned |
| Gateway: 保存等待说明或提交结果 | [D8 feedback](../../../../packages/dsh-integration/src/features/task-graphs.ts), selected Task data and fixed conversation, root/child branch | Integration `task-feedback.test.ts`, child context; existing Global send recovery | aligned; actual fixed-chat delivery in R5 |
| Gateway: 续期、回执重放与发送未确认 | Confirmed response feedback projection and send-state guidance; real waiting state retained | Integration feedback; PA `global-agent.test.ts` | aligned; model/no-duplicate outcome in R5 |
| Capabilities: 首次处理请求与能力更新 | [source-only current-step ordering](../../../../packages/dsh-integration/src/context-order.ts), real assembly/tool filtering | Integration `context-order-provider.test.ts`, `agent-context-default.test.ts`, `context-revalidation-provider.test.ts` | aligned |
| Capabilities: 去重与按需读取 | Frozen English prompt mapping, P2/P2R separate, existing custom prompt retained, child root-private surface omission | Integration context defaults/child HTTP; IM PA default tests; affected document/legacy HTTP | aligned; immediate PA invalidation combination passed in final-fix-focused |
| Capabilities: 用户删除独立或 Task 关联的 Schedule | Separate schedule-change and task-wait-repair facts with original owner/session | PA deletion tests; native deletion fixture | aligned; R4 product PASS |
| Capabilities: 重试、恢复和停止边界 | Durable intent before delete; confirmed result only; two receipts, stable native evidence, stop/disable passive boundary | PA deletion crash/restart/unavailable tests; native deletion and stop/sync tests | aligned |

## Coherence

| Approved decision | Final implementation evidence | Result |
|---|---|---|
| DSH only through integration public exports; Node uses client/stdin-stdout; no second loop | Native OwnedSessions/SessionController public APIs; integration dependency contract in Python run | followed |
| Reorder only current native environment/catalog; no history/role/ID rewrite | ContextOrder returns stable buckets after native next(); HTTP order/restart/config-change fixture | followed |
| One business original and independent actual consumption, no private responsibility delta | IM transaction/index, TaskContext persisted mapping, native event evidence, Inbox direct read/cursor cleanup | followed |
| Revocation terminal before source cleanup; consumed history retained | Authority transaction captures losses, terminal product mapping, queued/claimed filtering; native history and public cursor regression | followed |
| Independent authorization survives unrelated source outage while stale Tasks remain pending | Explicit unavailable result, native candidate filtering and D9, executable Task-tool gate, no Task-only loop | followed |
| Only genuine root continuation includes full current Task package; child keeps canonical evidence | Task pre-step assembly; replayable inherited-surface replacements; native fork/cold-resume HTTP fixture | followed |
| Native Schedule remains truth; two deletion facts and restartable receipts | ScheduleDeletions, current Task reread, native owned child resolution, independent notification receipts | followed |
| Preserve Memory owner/source lifecycle, sole Dreaming writer, document/legacy exclusivity and fixed creator | PA prepare invokes complete source refresh; dynamic memory owner unchanged; writePolicy selects owner workspace without changing backend mode; HTTP document/legacy/creator cells | followed; affected PA empty-unread native invalidation fixture passed |
| Prompt body and four independent-review consumers follow frozen design | English P/D bodies inspected; classifier/Codex/PA input/action use P2R and retain original strict output/tool contracts | followed; no autonomous security reliability claim |

### Prototype / Reference Contract

N/A. This unit does not modify client rendering or introduce a must-match visual reference.

## Issues

**Product repair disposition:** PA679-1 closed in real-model final-2; PA679-2/3 closed in independent real-stack final-3, including two concrete repairs consumed before replacement tools. Final-3 also verifies relation endpoints, minimal member withdrawal, PA source exclusion, /stop plus later information keeping Tasks paused, and fixed-chat result delivered once. PA679-4 (visible withdrawal omitted subject/Tasks) and PA679-5 (historical loss treated as permanent after restored access) now have targeted implementation repairs checked at 6881952b9; final independent real-stack rechecks are closed by acceptance final-4 at 6881952b9. Controlled provider HTTP window/summary captures have been independently parsed. No full product PASS is inferred from those mechanism captures.

### CRITICAL

None found in the frozen implementation.

### WARNING

None open. **V-FINAL-1 closed** on final independent evidence handoff at source `6881952b96ea3a1575f5fbad44d6a717d8fb48c9`. [Acceptance final-4](acceptance.md#最终结论2026-10-31round-final-4) supplies a self-contained R1–R6 and 15 motivation-scenario verdict, all five findings closed, exact runtime/model and product locators. The verifier independently checked the final engineering native events and Task document: seq114 contains the minimal revised withdrawal without latest task facts; seq127/128 queries current conversation permission; seq134/135 gets revision8 with 1024×576/竹叶63; seq139/140 sends the correct private answer with sent receipt; seq145 completes. Task revision8 still has n1/n2 todo, so current access verification did not start the work. The visible original is independently accepted as identifying E and both affected task links.

Final build/typecheck at 6dc940cf6 plus affected IM build/typecheck and PA build/typecheck at 6881952b9 passed; frontend 108 files/1,031 tests, shared iOS runtime, Python 127 non-e2e, ruff and docs-check 294 sources/68 routes passed. The broad runtime run remains honestly recorded as 949 passed plus one in-development red test, with that exact failure subsequently passing in the 53-test scoped run. No unresolved observed regression is retained.


### SUGGESTION

None. No speculative hardening or additional whole-Memory matrix is requested.

## Targeted repair verification — 6dc940cf6

- Mode: **delta**, retained full review at b610b02; fix delta `b610b02..6dc940cf6` only. `requires_full_verification: false`. No new architectural boundary or consumer owner was introduced; the earlier all-scenario mapping remains applicable with the repairs below.
- [Design Round 6](design-review.md#round-6) approved prepare-before-assembly. Implementation now obtains complete PA source state before native document/runtime snapshot rendering, caches only the current Agent step result, and still filters already-claimed revoked originals at pre-step. Preview lacks turn signal; child/Dreaming lack direct trusted root binding. The new empty-unread PA fixture confirms the immediately next native request uses current generation and invalidation, rather than the formerly one-step-late snapshot. This closes the previously identified affected-Memory evidence gap.
- The Channels transport fix restores the existing product synchronization request/result contract; its actual WebSocket correlation/rejection/FIFO regression protects the real integration failure missed by product-host stubs. PA679-1 has a separate successful real-model product recheck.
- Root/subtree deletion now calls the same original-message persistence within the mutation transaction before receipt/return. Two permanent cases protect original/index persistence and idempotent replay. Running Schedule repair injects at next step; idle followup and stopped passive admission remain. Held-tool native regression captures the concrete Task/D7 before another model/tool decision. PA679-2/3 were subsequently independently closed in acceptance final-3.

### Reused commands and results

All commands below use the configured Node v24.22.1 PATH. This reviewer read the actual source/test delta and logs and did not duplicate these runs.

```sh
pnpm exec vitest run apps/im-server/tests/task-execution.test.ts apps/im-server/tests/task-notifications.test.ts apps/node/tests/global-inbox-native.test.ts packages/dsh-integration/tests/task-context-originals.test.ts packages/dsh-integration/tests/task-context-sync.test.ts packages/dsh-integration/tests/context-order-provider.test.ts packages/dsh-integration/tests/context-revalidation-provider.test.ts packages/dsh-integration/tests/memory-child-runtime.test.ts --maxWorkers=1
# output/refactor-679/final-fix-focused.log: 8 files, 41 tests passed.
# Source matches 6dc940cf6 except later running-repair change, covered immediately below.
pnpm exec vitest run packages/dsh-integration/tests/task-reminder-batch.test.ts packages/dsh-integration/tests/global-child-tools.test.ts --maxWorkers=1
# output/refactor-679/repair-child-focus.log: 2 files, 4 tests passed at final repair source.
```

| Other final evidence | Observed result and limit |
|---|---|
| Channels WebSocket tests | Parent reports 16 tests passed for typed reply correlation; new Task sync parameterization inspected. Real product PA679-1 recovery independently recorded in acceptance. |
| `full-tests.log` | Original broad command: 175 files/938 tests passed, six failed on timeouts. This log itself remains a failed broad run. |
| `full-timeout-recheck.log` | Five affected files/12 tests passed; global-child had one undefined-events failure. A diagnostic-only assertion was added; both Global child variants then passed in repair-child-focus. No failing case is silently counted as passed by the original command. |
| `running-repair-red.log`, `running-repair-green.log` | First documents old next-turn timing; second retains one fixture failure caused by excluding required task_graph. Final corrected native regression passes in repair-child-focus; the intermediate 18 pass/1 fail run is not blanket PASS. |
| `docs-check-current.log` | Documentation integrity passed: 292 maintained Markdown sources, 68 required routes. Later report edits still require final docs-check. |
| `ruff-check.log`, `ruff-format.log` | Parent reports both passed; these do not prove product behavior. |
| Final build/typecheck/frontend/iOS runtime gates | Final build/typecheck, 108 frontend files/1,031 tests and shared iOS runtime passed; see the implementation evidence record and final closure. |

**Delta verifier result: aligned; 0 new implementation issues. At this delta snapshot the full verdict was pending; the final evidence closure above supersedes that status and closes V-FINAL-1.**

## Second targeted repair verification — 6881952b9

- Mode: **delta + corrected-delta repair check**, range `6dc940cf6..6881952b9`; retain prior full and scoped conclusions. `requires_full_verification: false`. **aligned; 0 new implementation issues.** No newly uncovered intended product behavior requires another active delta: IM qualification-change clarity was already required, and D3 now clarifies how historical facts coexist with current verified permissions under the existing authorization/paused-state contracts.
- PA679-4: current readers' original now identifies affected Agent name/ID and assigned Tasks with locatable links/refs in the same authority transaction. The removed Agent's same-ID relay and sync projection remain built from the separate minimal revocation record. New test exercises actual HTTP removal, publicized/persisted original, durable relay and sync output, and demonstrates old-text failure before repair. Current read ACL still gates publication; no new source or disclosure authority is introduced.
- PA679-5: actual Inbox D3 equals [approved Round 7](design-review.md#round-7). It dates the loss using the existing event_time field and allows only a later independently authorized request to use current tool-verified access; restored access does not resume paused Tasks or authorize denied actions. Native eligibility/ACL/state mechanisms are unchanged. The final actual model interpretation is independently closed in acceptance final-4 and cross-checked against native evidence in V-FINAL-1 closure above; source/service tests alone were not used to close it.

| Final evidence | Result / scope |
|---|---|
| `visible-revocation-green.log` | Node24, `pnpm exec vitest run` for IM task-context-revocations/live/migration, task-execution, identity and e2e/conversation-tasks with `--maxWorkers=1`: 6 files/53 tests passed. Covers current visible fact, same-ID minimal relay/sync and retained rollback/lifecycle/migration paths. |
| `eligibility-tests.log` | Inbox and PA TaskContext fixtures: 2 files/18 tests passed after revised D3. Does not assert autonomous E behavior. |
| `final-runtime-tests.log` | Final broad collection: 180 files/949 tests passed, one failed new visible-revocation red case collected during its development. The 53-test run above subsequently passes that exact case. This remains a nonzero broad-run log, with the sole observed failure separately closed. |
| Final build/typecheck | Full build/typecheck already passed at 6dc940cf6; parent reports 688 IM build/typecheck and PA build passed for affected source. Frontend 108 files/1,031 tests and shared iOS-runtime gate remain unchanged and passed. |
| Actual HTTP artifacts | `/tmp/nano-refactor679-daily/provider-wire-DOCUMENT.json` (3 requests, document-only entry, real manual window reset) and `provider-wire-LEGACY.json` (4 requests including native summarization, legacy-only entry, summary in next request) parsed independently. Both show fixed creator and current Task originals at `/v1/messages?beta=true`, root/session wire-session. SHA-256 respectively `021573e38a18afce5cfb111d934aad24b0504233153a86171a7a4c838cffd760`, `cd72a9951081dfd880d7ddbc8d851979460ceb717399da35821dc2407e714790`. Controlled fixture; no claim of live-model wire capture or revised-D3 behavior. |
| Product final-3 | Independently reported PA679-2/3 closed; multi-waiting concrete D7 consumed before replacement tools, relation changes, withdrawal deny, later /stop input staying paused and restored no-duplicate delivery covered. PA679-4/5 were subsequently independently closed in acceptance final-4. |

The existing 20-scenario alignment remains valid with the more explicit visible IM withdrawal and revised historical D3. All required implementation/assembly evidence gaps identified by this verifier are now addressed. **Final verifier PASS: V-FINAL-1 is closed by acceptance final-4, native evidence and final gate handoff.**

## Corrected Delta Reconciliation

All active deltas were checked against final source and meaningful regression seams; no design/spec/test was changed by the verifier.

| Delta item | Implementation / test evidence | Outcome |
|---|---|---|
| [IM Task delta](specs/im/task-graphs.md): all 6 scenarios | Original semantic notice and mentions; transactional access loss; durable replay/consumption/revocation; the six IM rows above | aligned |
| [Gateway Task delta](specs/gateway/task-graphs.md): all 10 scenarios | Current authority cut, stop/cold restore, genuine continuation, native waiting/deletion/repair and D8 fixed-chat feedback; the ten Gateway rows above | aligned |
| [Gateway capability delta](specs/gateway/agent-capabilities.md): all 4 scenarios | Actual native/HTTP environment/Skill ordering and window/summary; preserved configuration; two durable deletion facts; the four capability rows above | aligned |

### Uncovered Observable Behavior

None identified. Owner-workspace memory initialization/publication repairs the retained configured-workspace boundary; it does not add a new product behavior requiring a new delta. The dependency, capability selection, Dreaming sole-writer and existing consumed-history contracts remain authoritative. Historical implementation mismatches were repaired rather than normalized by weaker delta text.

**Outcome: aligned. Final verifier: PASS.** All three active delta specs match approved design and the final validated implementation; no further design/spec semantic change is required. V-FINAL-1 is closed with the required M1 evidence.

---

# Historical review records (superseded within this frozen full review's scope)

# Verification Report: refactor-679-agent-context-optimization

> Original validation snapshot: baseline HEAD `4b27d962c1cc09a27a567619bd5cabc3db2ee934` → **dirty pre-fix implementation**. Latest scoped repair recheck is recorded below; a final freeze was not assessed in this round. Destination branch is `unit/feat-676`, not main.

**Provisional independent verifier report, not final gate approval.** The latest scoped repair recheck below supersedes the original defects only for paths independently rerun. The retained historical body refers to witnessed pre-fix code; a separate final frozen review remains necessary. The reviewer did not modify implementation, tests, design or delta-specs.

Fresh independent context uses the approved current-model inheritance substitute because this SDK cannot select model/effort; **this is not a claim that `gpt-6.1-sol/high` was configured**. Responsibilities remain separate: this report checks implementation/spec/design consistency; it does not replace the parent’s real-product acceptance.

## Latest scoped repair recheck — not a final verdict

The parent explicitly limited this round to the two earlier CRITICAL counterexamples and one business-semantic WARNING. All rechecks used the approved inherited-model substitute and Node v24.22.1. Evidence and replayable actual-native setup are in [review-witnesses C/D](<review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate>); [code-review](<code-review.md#latest-scoped-repair-recheck--not-a-final-gate>) records the same bounded disposition.

| Scoped requirement | Independently rechecked result |
|---|---|
| Independent authorized input during authority outage | Ordinary human Feishu/web input reaches provider with current D9, even Task feature off; pending originals are excluded and remain prepared |
| Fail-closed automatic Task input and recovery | Task-only produces no provider and no extra prepare in the bounded idle observations; changed rechecks once; authority restoration consumes the stable original natively exactly once |
| Revocation/consumption in preexisting unread cursors | Actual public-source Global/Inbox old cursor returns no never-consumed revoked Task and no directly consumed duplicate; saved ordinary history is preserved |
| Native hard Task-tool gate | Actual feature-off allowlisted apply is denied before product offline; after authority catch-up in the same session, one new apply reaches product exactly once |
| Original notice semantics | Actual generator states explicit old/new assignee roles, directed old/new relation and dependency endpoints, references and directly affected owners |

The native hard-gate omission was caught during this recheck and repaired by the parent. A second real native counterexample then exposed a cached unavailable flag sticking after feature-off recovery; it was also independently reported, fixed with current per-tool snapshot revalidation, and the exact counterexample rerun succeeded. These intermediate defects and their evidence remain recorded, not erased.

**Scoped disposition: earlier three counterexamples and both repair-chain residuals are repaired in the paths rerun; 0 unresolved scoped findings.** Latest full scoped native job `bash-2f630a1037a04d46` exited 0 with relevant artifact hashes unchanged before/after. This does not independently close M1, the full 20-scenario execution matrix, true-model/product evidence, child cold isolation or any final frozen review. No final PASS or PR recommendation is authorized.

## Historical pre-fix summary

Everything from this historical summary through the original outcome below describes the first review snapshot. Its issue counts and marked deviations are superseded only where the scoped result above explicitly rechecked them; other entries were not reevaluated in this round. The final-gate evidence status must be established separately.


| 维度 | 结果 |
|---|---|
| Completeness | 20/20 active-delta scenarios mapped to production and inspected tests; 0/1 M1 independently signed off pending final freeze and exit evidence |
| Correctness | 3 confirmed pre-fix implementation defects; all other mappings are static evidence, not final execution PASS |
| Coherence | Main architecture followed; original-message business content, terminal revocation projections and independent-input degradation deviate |

**2 CRITICAL implementation issues, 1 WARNING implementation issue and 1 WARNING evidence/freeze gap. Fix/close before PR. No PR recommendation or final PASS.**

## Completeness

- Milestones: [M1-context-flow](<design.md#L770-L784>) is the sole milestone. Its implementation is present across IM, Node, PA and integration, but **0/1 independently signed off**; R1–R6/W1–W5 require final evidence handoff. This is an evidence status, not a claim that no work is implemented.
- Active deltas: [IM Task Graphs](<specs/im/task-graphs.md>) has 6 scenarios; [Gateway Task Graphs](<specs/gateway/task-graphs.md>) has 10; [Agent Capabilities](<specs/gateway/agent-capabilities.md>) has 4. All 20 are mapped below.
- Read the approved [design](<design.md>), [Gate 2 review](<design-review.md>), current [architecture](<../../../../SPEC.md>), current Gateway/IM task contracts, current PA/capabilities contracts, and actual dirty implementation plus untracked additions. No parent conclusion substitutes for this review.
- Prototype / Reference coverage: **N/A**. No frontend prototype/reference must-match contract is introduced; this unit changes backend/context behavior, not a new visual contract.
- Executed independently: only two explicitly authorized narrow witnesses, both exit 0: native ordinary external input with disabled Task feature and disconnected center; public-source partial-read cursor followed by terminal Task revocation. Details and built-input fingerprints are in [review-witnesses](<review-witnesses.md>). No full regression, extra HTTP stack, production access or unrelated model suite was duplicated.

## Correctness

“Inspected” below means the test source was reviewed, not that this reviewer ran it. “Pending final evidence” is not a code defect or an execution PASS.

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| IM: 改派双方获知 | [task-notifications](<../../../../apps/im-server/src/task-notifications.ts#L21-L52>) | [task-context-live](<../../../../apps/im-server/tests/task-context-live.test.ts>) inspected | **偏离**: unlabelled mentions do not state from whom to whom |
| IM: 要求或关系更新 | [task-notifications](<../../../../apps/im-server/src/task-notifications.ts#L23-L51>) | [task-context-live](<../../../../apps/im-server/tests/task-context-live.test.ts>) inspected | **偏离**: relation endpoints/business direction absent; requirement-update entry exists |
| IM: 暂缓／关闭逐层传达 | [task-notifications](<../../../../apps/im-server/src/task-notifications.ts#L25-L29>) | [task-context-live](<../../../../apps/im-server/tests/task-context-live.test.ts>) inspected | Static mapping present; final evidence pending |
| IM: 结果向上反馈 | [task-notifications](<../../../../apps/im-server/src/task-notifications.ts#L28>) and [delivery guidance](<../../../../packages/dsh-integration/src/task-execution.ts>) | [task-execution](<../../../../apps/im-server/tests/task-execution.test.ts>) and [task-feedback](<../../../../packages/dsh-integration/tests/task-feedback.test.ts>) inspected | Static mapping present; actual fixed-chat delivery evidence pending |
| IM: 成员失去任务处理资格 | [access authority](<../../../../apps/im-server/src/task-context-access.ts>), [sync](<../../../../packages/personal-assistant/src/task-context.ts>), [native removal](<../../../../packages/dsh-integration/src/task-context.ts>), [Inbox revoke](<../../../../packages/personal-assistant/src/inbox.ts#L233-L235>) | [IM revocations](<../../../../apps/im-server/tests/task-context-revocations.test.ts>), [native originals](<../../../../packages/dsh-integration/tests/task-context-originals.test.ts>), reviewer cursor witness | **偏离**: saved unread cursor can first expose revoked Task |
| IM: 无业务变化与通知后的行动 | [taskNotices](<../../../../apps/im-server/src/task-notifications.ts#L42>), [transactional relay/index](<../../../../apps/im-server/src/messaging.ts#L568-L618>) | [IM live](<../../../../apps/im-server/tests/task-context-live.test.ts>) and [migration](<../../../../apps/im-server/tests/task-context-migration.test.ts>) inspected | Static no-op/idempotent mapping present; final execution pending |
| Gateway: 停止通知延迟消费 | [execution fence](<../../../../packages/dsh-integration/src/task-execution.ts>), [Task stop authority](<../../../../apps/im-server/src/task-graphs.ts#L838>), [context driver](<../../../../packages/dsh-integration/src/task-context.ts>) | [native task-context sync](<../../../../packages/dsh-integration/tests/task-context-sync.test.ts>) inspected | Static passive-original/fence mapping present; final real behavior pending |
| Gateway: 外部变更与离线恢复 | [fixed-cut messaging](<../../../../apps/im-server/src/messaging.ts#L568-L618>), [durable PA sync](<../../../../packages/personal-assistant/src/task-context.ts>), [native pre-step](<../../../../packages/dsh-integration/src/task-context.ts>) | [PA >32 sync](<../../../../packages/personal-assistant/tests/task-context.test.ts>), [native sync](<../../../../packages/dsh-integration/tests/task-context-sync.test.ts>), reviewer no-Task/offline witness | Task fail-closed mapping exists; **independent-input availability regression confirmed** |
| Gateway: 内部对象重建而事实未变 | [Task state driver](<../../../../packages/dsh-integration/src/task-execution.ts>), [original-ID evidence](<../../../../packages/personal-assistant/src/task-context.ts>) | [native originals](<../../../../packages/dsh-integration/tests/task-context-originals.test.ts>) inspected | Static stable-ID/evidence mapping present; final execution pending |
| Gateway: 首次等待及校验失败 | [IM Task mutation](<../../../../apps/im-server/src/task-graphs.ts>) and [schedule evidence](<../../../../packages/dsh-integration/src/schedule-evidence.ts>) | [Task execution](<../../../../apps/im-server/tests/task-execution.test.ts>) inspected | Static owner/root/enabled/future validation mapping; final execution pending |
| Gateway: 安静等待与安排失效 | [Task execution driver](<../../../../packages/dsh-integration/src/task-execution.ts>) | [execution limits](<../../../../packages/dsh-integration/tests/task-execution-limits.test.ts>) and [reminder batch](<../../../../packages/dsh-integration/tests/task-reminder-batch.test.ts>) inspected | Static all-tasks/quiet-wait mapping; final execution pending |
| Gateway: 关联 Schedule 被删除 | [durable deletion service](<../../../../packages/personal-assistant/src/schedule-deletions.ts>), [Node UI/tool wiring](<../../../../apps/node/src/main.ts#L285-L293>) | [deletion service](<../../../../packages/personal-assistant/tests/schedule-deletions.test.ts>) and [native deletion](<../../../../packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Static independent repair mapping; parent native/restart evidence pending |
| Gateway: 提前答复与定时复查 | [schedule-source fold](<../../../../packages/dsh-integration/src/schedule-evidence.ts>), [Task driver](<../../../../packages/dsh-integration/src/task-execution.ts>) | [reminder batch](<../../../../packages/dsh-integration/tests/task-reminder-batch.test.ts>) and [native deletion](<../../../../packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Static stale-trigger and coalescing mapping; final execution pending |
| Gateway: 一轮结束仍有可执行责任 | [automatic continuation driver](<../../../../packages/dsh-integration/src/task-execution.ts>), [Task guidance](<../../../../packages/dsh-integration/src/features/task-graphs.ts>) | [task execution](<../../../../packages/dsh-integration/tests/task-execution.test.ts>) and [child context](<../../../../packages/dsh-integration/tests/task-child-context.test.ts>) inspected | Static all-owned doing/waiting, genuine-continuation-only mapping; final wire/behavior pending |
| Gateway: 保存等待说明或提交结果 | [effective result delivery hints](<../../../../packages/dsh-integration/src/task-execution.ts>) | [task feedback](<../../../../packages/dsh-integration/tests/task-feedback.test.ts>) and [child context](<../../../../packages/dsh-integration/tests/task-child-context.test.ts>) inspected | Fixed-chat/child-parent guidance exists; real delivery pending |
| Gateway: 续期、回执重放与发送未确认 | [Task delivery guidance](<../../../../packages/dsh-integration/src/task-execution.ts>), [Global durable publication](<../../../../packages/personal-assistant/src/global-agent.ts>) | [task feedback](<../../../../packages/dsh-integration/tests/task-feedback.test.ts>) and [Global recovery](<../../../../packages/personal-assistant/tests/global-agent.test.ts>) inspected | Static no-op/retry/unknown mapping; actual no-duplicate delivery pending |
| Capabilities: 首次处理请求与能力更新 | [current pre-step order](<../../../../packages/dsh-integration/src/context-order.ts>), [effective feature context](<../../../../packages/dsh-integration/src/agent-config.ts>) | [actual provider order](<../../../../packages/dsh-integration/tests/context-order-provider.test.ts>), [context defaults](<../../../../packages/dsh-integration/tests/agent-context-default.test.ts>) inspected | Native/HTTP capture fixture exists; actual window/summary and real-model evidence pending |
| Capabilities: 去重与按需读取 | [English policy sources](<../../../../packages/dsh-integration/src/policy/sources.ts>), [PA defaults](<../../../../apps/im-server/src/personal-agent-defaults.ts>), [root-only projection](<../../../../packages/dsh-integration/src/context-visibility.ts>) | [context defaults](<../../../../packages/dsh-integration/tests/agent-context-default.test.ts>) and [child context](<../../../../packages/dsh-integration/tests/task-child-context.test.ts>) inspected | Static source/policy preservation; Memory/Skill affected-matrix evidence pending |
| Capabilities: 用户删除独立或 Task 关联的 Schedule | [durable deletion](<../../../../packages/personal-assistant/src/schedule-deletions.ts>), [Node settings delete](<../../../../apps/node/src/main.ts#L285-L293>) | [deletion service](<../../../../packages/personal-assistant/tests/schedule-deletions.test.ts>) and [native deletion](<../../../../packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Separate schedule-change and Task-repair records exist; real-user/real-Agent scenarios pending |
| Capabilities: 重试、恢复和停止边界 | [deletion intents](<../../../../packages/personal-assistant/src/store.ts>), [recovery](<../../../../packages/personal-assistant/src/schedule-deletions.ts>), [passive Task execution sources](<../../../../packages/dsh-integration/src/task-execution.ts#L16>) | [deletion crash recovery](<../../../../packages/personal-assistant/tests/schedule-deletions.test.ts>) and [native deletion](<../../../../packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Durable phases separate missing/unavailable; final restart/stop execution pending |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| Runtime only via declared public integration exports; no second loop/private patch | Static inspection: yes; final dependency contract pending | [integration](<../../../../packages/dsh-integration/src/index.ts>), [Node](<../../../../apps/node/src/main.ts>), [owned sessions](<../../../../packages/dsh-integration/src/owned-sessions.ts>) |
| Reorder only current native runtime-context then skill-catalog; preserve source/history and independent memory | Static inspection: yes; final window/summary/memory matrix pending | [context order](<../../../../packages/dsh-integration/src/context-order.ts>), [provider fixture](<../../../../packages/dsh-integration/tests/context-order-provider.test.ts>) |
| One original transactional business notice, same original ID, no duplicate private snapshot/wake | Transport mapping yes; business facts incomplete | [task notices](<../../../../apps/im-server/src/task-notifications.ts>), [message index](<../../../../apps/im-server/src/messaging.ts#L568-L618>), [native Task input](<../../../../packages/dsh-integration/src/task-context.ts>) |
| Authoritative fixed cut, durable ingest before cursor, claimed-candidate revalidation; consumed history preserved | Mostly yes; alternate unread snapshot revocation incomplete | [PA Task context](<../../../../packages/personal-assistant/src/task-context.ts>), [native filter](<../../../../packages/dsh-integration/src/task-context.ts>), [Inbox cursor](<../../../../packages/personal-assistant/src/inbox.ts#L293-L317>) |
| Independent-input degradation allowed; unavailable Task originals/automatic steps remain pending without hot loop | No at witnessed pre-fix snapshot | [unconditional native prepare](<../../../../packages/dsh-integration/src/task-context.ts#L21-L25>), [witness A](<review-witnesses.md#L10>) |
| Full doing/waiting prompt only genuine auto-continuation; child hides inherited root-only guidance, canonical evidence remains | Static mapping present; child cold-resume final execution pending | [Task driver](<../../../../packages/dsh-integration/src/task-execution.ts>), [visibility](<../../../../packages/dsh-integration/src/context-visibility.ts>), [owned child rehydration](<../../../../packages/dsh-integration/src/owned-sessions.ts>) |
| Native future schedule evidence; separate durable user deletion and Task repair | Static mapping present; final native/product evidence pending | [schedule evidence](<../../../../packages/dsh-integration/src/schedule-evidence.ts>), [deletion service](<../../../../packages/personal-assistant/src/schedule-deletions.ts>) |
| English Nano-owned text; Task is not consent; worker P2 distinct from reviewer P2R | Static inspected policy mapping yes; real behavior pending | [policy sources](<../../../../packages/dsh-integration/src/policy/sources.ts>), [capability defaults](<../../../../packages/dsh-integration/src/agent-config.ts>) |

### Prototype / Reference Contract

N/A — no frontend prototype or reference contract. The explicit runtime/provider/product evidence contract remains mandatory and is not waived by this N/A.

## Historical pre-fix issues

### CRITICAL（提 PR 前必须修）

1. **Independent external conversation is blocked by unrelated IM Task synchronization.** [Native pre-step:21–25](<../../../../packages/dsh-integration/src/task-context.ts#L21-L25>) calls authoritative sync for every root. The actual native witness has `task_graph=false`, empty Task state and a normal Feishu question; it terminates with `CENTER_OFFLINE_NO_TASKS` before the provider. Preserve the [approved independent-input degradation](<design.md#L157-L191>) while keeping old Task originals/automatic steps pending and non-spinning. Add/review both the independent-input and stale-Task cases. Evidence: [witness A](<review-witnesses.md#L10>).
2. **Revoked unconsumed Task survives a frozen unread cursor.** [Inbox revocation:233–235](<../../../../packages/personal-assistant/src/inbox.ts#L233-L235>) does not terminalize snapshots; [cursor read:293–317](<../../../../packages/personal-assistant/src/inbox.ts#L293-L317>) first returns the Task after revocation despite `check.sources=[]`. Invalidate/filter affected unread fragments and saved-but-unconsumed read projections without rewriting consumed native history; cover public-source partial-read/revoke and direct-consume deduplication. Evidence: [witness B](<review-witnesses.md#L56>).

### WARNING（提 PR 前必须修）

1. **Business notices omit required relation endpoints/direction and reassignment roles.** [Notice generator:21–51](<../../../../apps/im-server/src/task-notifications.ts#L21-L51>) says generic updated/reassigned and stores only one task reference. Include both relevant task identities, old/new relationship business direction, and explicit from-old-to-new assignee wording. Preserve one original message, qualified mentions and old/new parent-owner attention. This is an implementation mismatch, not justification to weaken the [active IM delta](<specs/im/task-graphs.md#L11-L24>).
2. **Final source freeze and M1 execution evidence not handed over.** Before a final verifier decision, provide baseline→final source fingerprint including untracked files; narrow/final default regression and runtime dependency/docs-check results; child/deletion/restart fixtures; isolated real-stack R1–R6; true-model scenarios; first/running/offline/**actual window or summary** provider captures; and the affected Memory/Skill/PA-source matrix or valid baseline locators required by [design:778–783](<design.md#L778-L783>). This is missing verification evidence, not an invented production defect. Do not merge or claim PASS from static mapping or transport stubs alone.

### SUGGESTION（可以修）

None beyond required closure above. Avoid spec changes that merely normalize confirmed defects.

## Historical pre-fix delta reconciliation

Mode is full design/spec consistency plus active-delta correction assessment; no delta was edited by this reviewer.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| [IM: 改派双方获知 / 要求或关系更新](<specs/im/task-graphs.md#L18-L24>) | [notice generator](<../../../../apps/im-server/src/task-notifications.ts#L21-L51>) omits required business facts | [IM live fixtures](<../../../../apps/im-server/tests/task-context-live.test.ts>) inspected; repair/retest pending | **implementation-mismatch**; delta already states approved intent |
| [IM: 成员失去任务处理资格](<specs/im/task-graphs.md#L37-L41>) | [Inbox snapshots](<../../../../packages/personal-assistant/src/inbox.ts#L233-L317>) bypass terminal direct-context revocation | [exact public cursor witness](<review-witnesses.md#L56>) executed | **implementation-mismatch**; keep consumed-history distinction in delta |
| [Gateway: 外部变更与离线恢复](<specs/gateway/task-graphs.md#L13-L18>) + retained [local autonomy](<../../../../SPEC.md#L22>) | [unconditional sync](<../../../../packages/dsh-integration/src/task-context.ts#L21-L25>) overreaches Task fail-closed boundary | [native no-Task/offline witness](<review-witnesses.md#L10>) executed | **implementation-mismatch** against approved design/current invariant; no delta weakening needed |
| Other active Gateway Task/Capabilities and IM scenarios | Production/test mappings above | Test sources inspected; execution/product handoff pending | Statically mapped; final alignment **not yet verified** |

### Uncovered Observable Behavior

No intended new observable behavior requiring an additional active-delta requirement was identified. The unconditional offline-conversation block is an unintended regression of a retained invariant, not a new desired behavior to document. Child projection, ordering, default guidance, original Task context, Schedule deletion and fixed-chat delivery are covered by active deltas/design and existing current contracts.

**Historical outcome: implementation-mismatch (pre-fix snapshot).** The latest scoped disposition above records independently rechecked repairs, not a replacement final unit verdict. No independently established delta-mismatch; final frozen evidence and gate are still required before recommending PR.
