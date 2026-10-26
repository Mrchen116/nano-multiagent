# Verification Report: feat-625-auto-review-bounded-retry

> Validation snapshot: `d72e220f1d21827c65e046f704c13837ea39d7c2 → 4282c0488510c4a46a81d4b5632ebaa236f619ac`

## Round 1 — full

- `verification_mode`: `full`; `review_round`: `1`
- `verify_worktree_dir`: `/Users/czj/.nanoassistant/workspaces/nano-engineering-r2-1026/.worktrees/unit-feat-625-r2-361`
- Branch: `unit/feat-625-r2-361`; validated tree: `d571923726b267eb65c8f48907fa9e82c073b59e`
- Approved design: `407b6e096ec4e6b0bdc9a4a30774dd2e2bed0148`, Gate 2 R5 full + R6 closure. Design and delta were unchanged between that approval and the validated implementation.
- `requires_full_verification`: `false` (this was already a full verification, not a narrow closure).
- `report_commit`: not committed; coordinator owns report commit/integration. Reports are new files in the authorized shared worktree. No other files were changed by this verifier; no new worktree, service or background job was started.
- Author repairs began during review with coordinator approval. All findings below retain the frozen `4282c048...` version; subsequent source inspections used fixed Git objects, not the dirty repair tree. No inferred `effective_*` values are asserted.

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 not complete: core implementation present, but required product evidence/final validation remain outstanding; 17 original scenarios mapped below, not all accepted |
| Correctness | One confirmed implementation mismatch in actual final-route trace; one confirmed test-structure/CI violation; no claim of new permission bypass |
| Coherence | Most approved design boundaries followed; final-route trace deviates under concurrency, and full exit criteria are not closed |

**Verdict: NOT PASS — 1 CRITICAL issue, 2 WARNING issues, 0 SUGGESTION. Fix/complete before PR.** The CRITICAL is an unfinished milestone/evidence gate, not a claim that an untested real-model behavior is a proven product defect. No corrected-delta or Q product-acceptance signature is given.

## Completeness

- Milestones: **0/1 accepted**. `design.md:264` defines a single M1 and its reviewer/worker exit criteria. The core recovery/transport/lifecycle/audit implementation and reusable deterministic fixture/driver exist; M1's own progress explicitly calls this an engineering checkpoint rather than a passing milestone (`M1-review-recovery/progress.md:7,38–40,69–73`). The simplified process does not require a separate tasks file.
- Requirement implementation is present for shared quotas, complete per-attempt budgets, cancellation/cleanup, permanent/error classification and existing routes. Original Scenario 16 has a confirmed trace mismatch; Scenario 17's required independent real-provider daily/Global plugin evidence was still pending at this snapshot.
- Required whole-CI closure, independent Q acceptance, final delta/canonical-spec reconciliation and final integration evidence are not complete. The unmerged active delta describes target behavior; it does not silently change current spec or make a corrected-delta verdict valid.
- Prototype / Reference: **N/A**. Design explicitly introduces no new UI or prototype (`design.md:31`); Work/user journey still requires real evidence, not a subjective visual review.

### Evidence use and limitations

This verifier reused the independently performed code/Context review in `code-review.md` rather than doing another complete Context review. Complete fixed diff and affected unchanged consumers/current contract were read. Source mapping was checked, not inferred from test-file counts.

Applicable engineering evidence is preserved in frozen `M1-review-recovery/progress.md:25–73`:

| Evidence | Command / locator and observed scope | Limit |
|---|---|---|
| Narrow policy/context/attribution | `pnpm exec vitest run` for `review-recovery`, `approval-retry`, `codex-approval-lifecycle`, `codex-approval`, `approval-sources`, `llm-attribution`; reported final-source delta 54/54; recovery suite 19/19 | Controlled clocks/services. Does not imply all applicable native/default-concurrency tests passed |
| Public native HTTP failures | `pnpm --filter @nano/dsh-integration build && pnpm exec vitest run packages/dsh-integration/tests/approval-retry-native.test.ts`; 20 dual-strategy cases, reported exit 0 | Native loop/adapter and real HTTP fixture, not a real provider |
| Configuration transaction semantics | `pnpm exec vitest run packages/dsh-integration/tests/approval-retry-configuration-native.test.ts`; 20 native controls reported exit 0 | Later expanded parallel run had admission-barrier failures; isolated pass is retained but not whole-run closure |
| Concurrent identity / cache reuse | `pnpm exec vitest run packages/dsh-integration/tests/approval-retry-concurrency-native.test.ts`; reported exit 0 | Native fixture; unmarked synthetic auxiliary stream, not every compaction path |
| True IM deterministic faults | `test_auto_review_retry_critical_path.py -k http_retry`, basetemp `output/feat625-im-faults-r5`; 20 cases reported pass | IM → Node → native DSH → fixture HTTP; not live model behavior |
| True IM complete default budgets / cancel | Same file `-k 'stop_request or default_full'`, `output/feat625-im-cancel-timeout-r1`: 3 passed, 184.01s; `-k cc_stages`, `output/feat625-im-stage2-r1`: 3 controls, 74.71s | Actual 30/60/90s timeout paths; no production timer shortening. Controlled model output |
| True IM rejected transaction | Same file `-k rejected_configuration`, `output/feat625-im-config-r1`: 4 controls reported pass | Actual capability-in-use/release path, not real-model acceptance |
| Export/build | `.venv/bin/python -m pytest tests/unit/test_review_trace_export.py -q`: 2/2 reported; ruff/build/typecheck reported exit 0 | Earlier build label was not an attestation of final SHA; final CI still needed |

Independent evidence added by this reviewer:

1. `git rev-parse HEAD`, tree, merge-base, clean initial status, fixed `git diff` and `git show` source inspection; original author test changes were observed later and excluded.
2. Real facade/counter methods + synthetic reviewer/table reproduced CR-1 (exit 0), with `[deny, ask]` but B's stored `finalRoute=deny`; complete runnable probe and limits are in `code-review.md`.
3. Read-only structural assertions on 80 captured HTTP request rows in `output/feat625-im-faults-r5/test_real_im_http_retry_and_in0/requests.jsonl` passed: equal frozen retry messages/actions, distinct failed/recovery Guardian IDs, exact read-only tool schemas, absent unsupported effort, cached delta replaced by clean full. These are true-IM/native HTTP fixture inputs, not live-provider inputs. Hashes and scope are in the code review report.
4. Fixed `git show 4282c048...:tests/e2e/critical_paths/test_auto_review_retry_critical_path.py` has **451 lines**; path does not exist at executed base. Read contract `tests/contract/test_test_naming_and_size_contract.py:130–155`: new files over 400 lines fail. This independently corroborates the parent's exact structural-CI failure report without rerunning against the author's already-splitting working tree.

The worker's local evidence record `output/feat625-parallel-regression-4282.md:5–47` was subsequently read by this verifier. It supplies the complete 9-file approval/PA/native command, 114.58s/exit1 result (7 files passed, 2 failed; 26 tests passed, 3 failed), exact assertions, and unchanged-source serial command/result. Configuration-native `keeps nano recovery alive across configuration reservation release but revokes it on cancel/disable` and its Codex counterpart failed at line69: default reviewer-HTTP admission poll expected1/received0. `approval.test.ts` `skips the reviewer only for verified owner messages and reviews other public recipients with host facts` failed at line52: default terminal observation poll expected truthy/received undefined. Two daily runtimes were active. The affected 2-file `--maxWorkers=1` rerun passed 11 tests in37.78s with both daily runtimes still active and no source change. The record links worker-collected raw outputs `bash-135`/`bash-139`; those raw job results were not independently rerun or inspected by this verifier. This evidence supports resource-sensitive short admission/observation windows, not a confirmed production fault. Neither a passing normal parallel command nor closure follows from one serial pass. The author is repairing bounded test-only windows; final new-SHA command/log and meaningful concurrent-load result must be attached before closure, with this original failure retained.

## Correctness

All locations refer to the validated revision, not current line shifts during repair. `recovery.ts` line 152 owns normal-attempt loops, `classifier.ts:26–43` owns stage-specific attempts, `codex.ts:141–211` owns Guardian judgment/full recovery. Test names and engineering runs above show the observable seam; `covered` below means implementation plus bounded engineering coverage, **not Q product acceptance**.

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 1 短暂故障后放行 (`spec.md:93`) | `recovery.ts:152–185`, `classifier.ts:33`, `codex.ts:141–211`, `approval.ts:175–179` | Native and true-IM dual-strategy HTTP matrix: retries then one effect, zero before allow | covered at deterministic seam; real journey pending |
| 2 混合失败共享额外两次 (`:99`) | `recovery.ts:99–185`; same controller passed across CC stages / Guardian | Recovery mixed quota tests; native/true-IM mixed and CC stage-shared quota | covered |
| 3 CC完整30/60预算 (`:106`) | `classifier.ts:26–43`, `recovery.ts:152–185` | Fake-clock full budgets; actual true-IM stage-one30/stage-two60 timeout/recovery | covered |
| 4 Codex完整90预算 (`:111`) | `codex.ts:141–211`, `recovery.ts:152–185` | Native and true-IM actual90 timeout; lifecycle context rebuild shares current attempt | covered |
| 5 几分钟等待但有界 (`:116`) | `recovery.ts:99–119,144–205` | Prepare15/action360/backoff/cleanup tests and real-budget timeout runs | covered; not every worst-case wall-clock combination run |
| 6 首次格式失败后有效判定 (`:123`) | `recovery.ts:31–46,171–183`, current classifier/Codex parsers | Dual-strategy malformed→allow, current bare/embedded parser tests | covered |
| 7 重复格式/总额耗尽 (`:128`) | `recovery.ts:171–183` | Repeated-invalid/mixed/exhausted native+IM cases | covered |
| 8 CC正常两阶段/最终deny (`:135`) | `classifier.ts:26–43`, `approval.ts:167–180` | Stage-two-only retry, unchanged valid denial route tests | permission behavior covered; trace threshold mismatch is CR-1 |
| 9 Codex风险/授权/检查约束 (`:140`) | `codex.ts:52–64,106–211,228–272`; unchanged `codex-context.ts`, inspection/source modules | Native isolation/forks/killable inspection, lifecycle and context/source/parser tests | covered within deterministic evidence; rich provenance+failure combinations not directly captured |
| 10 有效deny/永久错误不恢复 (`:145`) | `recovery.ts:34–46,171–183`; strategy parser before classification | Native/IM 401, permanent/unknown/context categorization, valid-denial tests | covered |
| 11 请求/退避取消且晚到不执行 (`:152`) | `approval.ts:36–45,158–165,177`; `recovery.ts:152–205`; `codex.ts:213–243` | True IM stop during request/backoff; lifecycle late-create/delayed-dispose; owner controls | covered; pending normal-parallel regression closure |
| 12 非主动单次timeout可恢复 (`:157`) | `recovery.ts:160–183`, strategy complete-budget boundaries | Actual CC30/60 and Guardian90 timeout, fake-clock repeated quota | covered |
| 13 interactive耗尽走人工 (`:164`) | `approval.ts:79–86,103–109,158–165` | Existing route tests; true IM exhausted card denied, zero effect | covered; independent Q assessment pending |
| 14 Global/child return_to_agent (`:169`) | `approval.ts:79–86,103–109` | Existing facade/native route assertions, not a new retry-owned approval system | implementation consistent; independent Q/live journey pending |
| 15 unattended allow/deny配置 (`:174`) | `approval.ts:79–86,103–109,158–165` | Existing schedule/fallback assertions and policy fixtures | original semantics retained; Q audit-route smoke pending |
| 16 可区分action/attempt/request及最终路由 (`:182`) | `recovery.ts:9–28,48–98,120–142`, `audit.ts`, export script; `approval.ts:169–179` | Usage/cap/old-row/export coverage; independent concurrent counter reproduction | **implementation mismatch CR-1**: trace may disagree with actual escalation |
| 17 真全局插件旅程及受控证据分开 (`:187`) | Long-term true-IM driver, fixture/export/runbook exist; Work uses current product surface | Controlled matrix available; no independent real-provider dual-daily create/install/two-call180/55/Work result at freeze | **required exit evidence pending C-1** |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| integration-only declared DSH APIs; no new Agent loop/kernel service | Yes by source/dependency review | Production changes confined to integration; root public `LlmError`/`isAgentLoopRequest` and existing create/cancel/dispose; no PA/Channels/IM DSH import change. Final runtime dependency contract run pending |
| One action controller, CC retry only failed stage, legacy single-stage | Yes | `approval.ts:134–154`, `classifier.ts:13–43`, `recovery.ts:152–185` |
| Guardian technical failure = new full from same frozen evidence; context rebuild once/action | Yes at inspected implementation and captured subset | `codex.ts:106,129–130,141–211`, controller `takeContextRebuild`; native/full request evidence in code review |
| Complete budgets; separate bounded prepare/backoff/cleanup/action safety | Yes at implemented/tested seam | `recovery.ts:99–119,144–205`, `classifier.ts:33`, Guardian `recovery.run` |
| Structured public failures / real HTTP facts; no string-regex retry or global native retry multiplication | Yes | `recovery.ts:28–46`, `review-http.ts:16–43`, `llm-attribution.ts:11–34`, Guardian scoped request-error handler; native HTTP fixture |
| Native marker + exact session before attempt access, ALS facts per request | Yes, within inspected/native fixture coverage | `codex.ts:52–64`, `review-http.ts`, existing attribution owner; concurrent fixture includes main/CC/disclosure/other parent/fork |
| Reservation release != stop; metadata-only frozen config; actual owner cancel isolated | Yes in code/controlled tests; parallel test reliability not closed | `approval.ts:110–145`, unchanged configuration transaction path; native 20 controls and true IM rejected transaction; active actions cancel only on real lifetime |
| idle config fingerprint/cache invalidation; no active release republish | Yes at source/lifecycle seam | `codex.ts:66–72,110–124,188–226`; lifecycle changed-config/rewrite tests |
| Current source/parser/admission/effort/PA strict consumer preserved | No code deviation found; some combined model evidence remains pending | Unchanged source/admission helpers and default config; `classifier.ts:25`, `codex.ts:94–108,129–136`; source/parser/lifecycle tests and captured request subset |
| Actual final route, one usage-bearing row, unknown usage not zero, old v1 rows | **Partial; route mismatch** | `approval.ts:169–179` CR-1; otherwise `recovery.ts:68–98,120–142`, optional schema/export regression coverage |
| Audit failures must not fall back to allow | Consistent by control-flow inspection | Audit errors escape reviewer/fallback path before returned allow; native dispatch also checks cancellation. No end-to-end injected audit-write-failure product test was claimed |
| Full test/CI/product evidence and final canonical merge | **Not complete** | `design.md:264`; progress explicitly defers these gates; new451-line test violates current size contract |

### Prototype / Reference Contract

N/A — no explicit UI prototype/reference must-match contract. Work/user-visible results are required product evidence under C-1 and cannot be replaced by static UI review.

### Agent Context reconciliation

Reuse Mode B coverage and actual fixture-input checks in `code-review.md`. **Implementation mismatch:** CR-1 affects diagnostic route, not a demonstrated source authorization change. **Design defect:** none established; do not rewrite approved spec to accommodate the trace race. **Model behavior not verified:** live-provider dual-daily journey, real tools/parameters/state interpretation and independent product verdict were pending. Existing source cases and plain fixture retry captures do not together prove all same-epoch/cross-epoch provenance+503 combinations; request a narrow captured combined case where required for M1's source-fidelity evidence, not a fabricated model pass. PA disclosure remains its own strict consumer, not a fallback retry permission.

## Issues

### CRITICAL（提 PR 前必须修/完成）

- **C-1 — M1 full exit criteria are unfinished.** Contract: `design.md:264`, `spec.md:187–192`; acknowledged gap: frozen `M1-review-recovery/progress.md:38–40,69–73`. No independently accepted real-provider CC/Codex daily Global self-created-plugin→install→two-call180/55/Work/user result exists at this freeze; expanded regression run and whole CI are not closed; final delta/canonical reconciliation is pending. These are explicit milestone deliverables, not optional follow-up and not a proven model failure. **Action:** original author/coordinator provide attested final build/SHA, finish normal applicable regression/CI (including source/PA/native cross-risks and runtime dependency/docs checks), let the same independent Q complete actual daily route/model and plugin journey, preserve deterministic versus real-provider evidence separately, then complete final delta/current reconciliation and assigned independent closure. Q may continue independent work while the author fixes the confirmed issues. This verifier does not replace Q or certify corrected delta.

### WARNING（提 PR 前必须修）

- **W-1 / CR-1 — durable final route is predicted before atomic counters.** `packages/dsh-integration/src/policy/approval.ts:169–179`; contract `spec.md:182`, `design.md:219–227`. Two concurrent low-risk denies read identical prior rows, but the second actual increment reaches escalation; its stored route remains `deny` while decision is `ask` (or unattended fallback). **CONFIRMED** by deterministic real-method probe, with no native/live-model claim. **Action:** derive/finalize trace route from the same authoritative serialized counter result before durable return, retaining one cost-bearing row and actual configured fallback; add concurrent threshold regression plus independent closure. Full evidence in `code-review.md`.
- **W-2 — frozen new true-IM test fails the repository's structural contract.** `tests/e2e/critical_paths/test_auto_review_retry_critical_path.py:401–451` is a new451-line file relative to executed base; `tests/contract/test_test_naming_and_size_contract.py:130–155` rejects new files over400. Parent reported this exact CI failure, independently corroborated from the frozen file and contract. **Action:** split by stable behavior boundaries with reusable fixture helpers, without dropping public IM/configuration/complete-budget semantics or coverage; rerun the contract and affected tests on the new frozen SHA. Do not count the author's already-dirty split as closure of this old snapshot.

### SUGGESTION（可以修）

None. Default-concurrency admission timeouts are recorded as unclosed regression evidence under C-1, not misclassified as a proven production bug or hidden by a serial rerun.

## Handoff

`validated_issues`: C-1 (required exit evidence incomplete), W-1 (confirmed actual-route mismatch), W-2 (confirmed structural contract violation). `top_concern`: fix atomic route/trace consistency and close real independent product/CI evidence before claiming the milestone or Ready PR. The two new reports are the only reviewer writes; coordinator will commit them. Existing shared worktree is intentionally retained for the same author's repairs, Q and this reviewer's follow-up; no cleanup or version checkout was performed by the reviewer.
