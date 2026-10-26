# Code Review — feat-625-auto-review-bounded-retry

## Round 1 — full

- `review_mode`: `full`; `review_round`: `1`
- `executed_base`: `d72e220f1d21827c65e046f704c13837ea39d7c2`
- `validated_at`: `4282c0488510c4a46a81d4b5632ebaa236f619ac`
- Tree: `d571923726b267eb65c8f48907fa9e82c073b59e`
- Diff: `d72e220f1d21827c65e046f704c13837ea39d7c2...4282c0488510c4a46a81d4b5632ebaa236f619ac`
- Independent reviewer did not author the implementation or design. This report also contains `agent-context-review` Mode B, not a separate gate. The separately assigned full verifier result is in `verification.md`.
- Initial checkout/branch/status, merge-base and tree were checked. During review the coordinator authorized the original author to begin repairs. Subsequent source checks used `git show 4282c048...:<path>`; this report does not evaluate the concurrent dirty test split or later fixes. No source/tests/config/design were modified by this reviewer; no commit was made.

**Result: changes requested — 0 CRITICAL, 1 WARNING.** Evidence status and severity are separate. Only the following finding is live.

```json
[
  {
    "file": "packages/dsh-integration/src/policy/approval.ts",
    "line": 169,
    "summary": "Compute the durable final route from the same atomic counter update that decides escalation",
    "failure_scenario": "Two concurrent low-risk denials for the same parent, initially empty audit rows and denyLimit=2/totalDenyLimit=99, both read the same prior counters at lines 169–171 and finish their trace with finalRoute=deny. record() serializes the actual increments to 1 and 2; line 179 therefore returns deny for A but ask for B. B's complete durable trace still says deny rather than interactive_pending. The analogous unattended threshold crossing can omit the actual fallback route/outcome. This violates the promised actual final route without changing the tool permission decision itself. Derive the trace route/fallback in the same serialized counter update as reached counts, or finalize it against those returned counts durably before returning; do not duplicate usage-bearing rows.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "severity": "WARNING"
  }
]
```

### CR-1 evidence and reproduction

Contract: `spec.md:182` (actual final result/route), `design.md:219–227` (complete durable review route/fallback and single cost-bearing row). Implementation: `approval.ts:88–101` increments counters inside `sessions.update`; `approval.ts:169–176` predicts from a separate read, whereas `:179` escalates from the actual returned counts.

Independent narrow reproduction executed successfully using the real built `NanoApproval.review/record/route/escalate` and `ReviewRecovery` methods, with a synthetic reviewer and an in-memory atomic table. The inspected build had the reviewed logic. It returned `[deny, ask]`; B had `consecutive=2` and `recovery.finalRoute=deny`. This is a deterministic policy/audit reproduction, **not** native-loop concurrency, a real storage implementation, a live provider or a product journey. The source read/update separation establishes the defect; native concurrent regression remains the author's responsibility.

Reproducer (run after building the frozen source; no file writes):

```bash
node --input-type=module <<'JS'
import assert from 'node:assert/strict';
import {NanoApproval} from './packages/dsh-integration/lib/policy/approval.js';
import {approvalDefaults} from './packages/product-contracts/lib/approval.js';
const rows=[];
const table={get:()=>rows,async update(_id,fn){const next=fn(rows);rows.splice(0,rows.length,...next);}};
const approval=Object.create(NanoApproval.prototype);
const config={agentId:'a',revision:'1',mode:'single_thread',provider:'fixture',model:'main',approval:{...approvalDefaults,rules:'codex',denyLimit:2,totalDenyLimit:99}};
Object.defineProperties(approval,{
 ctx:{value:{codexApproval:{review:async()=>({decision:{behavior:'deny',risk:'low',reason:'needs confirmation'}})}}},
 configOf:{value:()=>config},audit:{value:Promise.resolve({table:()=>table})},
 actions:{value:new Map()},cleanupActions:{value:new Set()},sources:{value:{}},inherited:{value:async()=>[]}
});
const agent={id:'parent',session:{header:{},requestHeader:()=>undefined,snapshotEvents:()=>[
 {type:'turn/start',seq:0},{type:'user/message',seq:1,data:{source:{kind:'user',actorId:'owner',channel:'test',messageId:'m'}}}
]}};
const decisions=await Promise.all(['A','B'].map(callId=>approval.review({agent,callId,name:'fixture_effect',arguments:{},signal:new AbortController().signal},async()=>({kind:'allow'}))));
console.log(JSON.stringify({decisions,evidence:rows.map(r=>({callId:r.callId,consecutive:r.consecutive,traceRoute:r.recovery?.finalRoute}))},null,2));
assert.deepEqual(decisions.map(d=>d.kind),['deny','ask']);
assert.equal(rows[1].recovery.finalRoute,'deny');
JS
```

## Coverage and evidence

Reviewed the complete fixed diff and its affected callers: the action controller/classification, CC stage progression and legacy path, Guardian full/delta/fork lifecycle, exact native stream ownership, HTTP observer/attribution, audit schema/write/export, changed regression tests and true-IM fixture. Also inspected the unchanged source/projection, context admission, inspection and approval/fallback consumers where their invariants are relevant. The approved design/delta were checked against `407b6e096ec4e6b0bdc9a4a30774dd2e2bed0148`; no intervening design/delta change was found. Gate 2 reference is R5 full + R6 closure, not the earlier historical rounds.

Engineering commands/results reused with their explicit limits are recorded in frozen `M1-review-recovery/progress.md:25–73`: narrow recovery/CC/lifecycle/source/parser/attribution checks; native HTTP failure matrix; request/backoff configuration controls; native concurrent identities; true IM HTTP, stop, full default 30/60/90-second timeout and stage-two/shared-quota controls; trace-export tests; build/typecheck. These do not by themselves prove final whole CI, independent Q acceptance or real-model behavior. No full rerun or new service was started by the reviewer.

Independent checks included fixed Git source/range/tree inspection, the CR-1 probe above, and read-only structural checks on captured HTTP requests (next section). A later independent frozen-source size check also corroborates the verifier's CI blocker: the new true-IM file has 451 lines versus the repository's 400-line contract. That delivery/test-structure issue is recorded in `verification.md`, not a second speculative product defect here.

## Agent Context Review — Mode B

### Trigger and consumption chain

The diff changes the lifetime of model-visible inputs and introduces technical recovery, so review followed actual consumers rather than only new fields:

| Surface / lifecycle | Checked chain and outcome |
|---|---|
| Current effective authorization/history | `ApprovalSources.history/transcript/codexEntries` → CC transcript / Guardian `reviewInput`; existing retained-history, restored/live, represented-user, Task/UI-stop, actual-send and host identity rules remain outside the retry controller. No newly added all-library or PA authorization fallback read was found. |
| Frozen action/config/model | `approval.ts:110–145`, `classifier.ts:16–35`, `codex.ts:106–136`: clone pending arguments/config, prepare source projection once, choose the existing model-capability effort, reuse the frozen projection on recovery. Unsupported effort is not added to the native request. |
| Failed history / restoration | `codex.ts:141–211` and controller `takeContextRebuild`: successful checkpoint may seed initial delta/fork; technical failure retires that reviewer and retries clean full, not failed assistant/read fragments. One context rebuild remains action-scoped and inside the current 90-second attempt. |
| Request identity / scope | `codex.ts:52–64`: exact native marker/session/owner test precedes access to `currentAttempt`; only captured current generation gets the sink. Main, CC, disclosure and unmarked auxiliary traffic remain transparent. `review-http.ts` and existing attribution dispatcher retain request-local facts, not a new runtime fork. |
| Shared PA consumer | `reviewDisclosure` does not receive tool recovery; strict `parsePersonalDecision`, purpose cache, normal budget and host commit boundary remain separate. Tool bare/embedded defaults remain the current tool parser contract. |
| Revocation / lifetime | generation checks, quarantine/late-create/disposal and existing native pre-dispatch cancellation prevent late authorization revival. Configuration transaction reservation release is not an action stop. No finding was established merely from an asynchronous audit boundary: inspected native tool dispatch checks cancellation before execution. |

### Actual assembled-input evidence

Read and structurally checked local raw `output/feat625-im-faults-r5/test_real_im_http_retry_and_in0/requests.jsonl` (80 lines), produced by true IM → Node → native DSH → Anthropic HTTP fixture. The reviewer did not copy private raw bodies into this report.

- CC `nano-service`: the two requests had equal system/message hashes (`f53837e6d9ef87ac` / `3a805bca9d288c6a`), demonstrating the failed stage's assembled request is repeated without new parent evidence in this case.
- Guardian `codex-service`: two distinct native reviewer session IDs, identical system/message hashes (`81a133787bdbdd7d` / `7190ba7492ad9814`), one `user` input, and the exact pending `retry-codex-service.txt` action. Only `guardian_stat`, `guardian_read`, `guardian_list` tool schemas were present. The no-effort fixture model had no effort field.
- Guardian `codex-mixed`: initial cached delta had `user/assistant/user` roles; both fresh recovery inputs had only `user` and identical message hash `a29bd866c9a77937`. System remained identical while reviewer IDs changed. This directly distinguishes initial cache reuse from fresh full recovery.
- Read-only assertions passed (exit 0). Hashes are equality diagnostics, not a signature/attestation of the containing source commit.

These are **native/true-IM HTTP stub inputs**, not provider-captured real-model decisions. The fixture build was prepared before the final checkpoint and its supplied SHA label alone is not a frozen-build attestation; applicability was checked against the inspected request-assembly code. No claim is made that a live model selected inspection tools correctly, understood every provenance case, or completed the daily plugin task.

### Coverage limits / no additional Context finding

Existing source/admission/parser/lifecycle tests were read and applicable recorded runs reused, including live/restored normalization, represented user and Task/UI sources; the captured fixture is simpler than those source tests. No combined captured same-epoch+503 / cross-epoch+503 provenance case was available, nor a captured rich Inbox/Task source fixture proving every combination in the final HTTP body. No real-provider daily/Q behavior pass was available at this review. The native concurrent auxiliary case uses an unmarked synthetic auxiliary stream; it is not evidence for every live compaction path. These limits remain acceptance work, not an invented confirmed source-trust regression. No extra Mode B defect survived review; the one CR-1 finding concerns the actual final audit route.

## Follow-up boundary

CR-1 needs an author fix and regression, then independent closure at a new frozen SHA. Structural CI and the unresolved default-concurrency test run require delivery follow-through; see verifier issues. Product Q/daily, final delta/canonical reconciliation, whole CI/archive/Ready PR are not signed off by this static review. The same reviewer session can continue; this report intentionally retains the original round's fixed version.

## Round 2 — patch + CR-1 closure

- `review_mode`: `patch`; `review_round`: `2`; focus: `CR-1`.
- `pre_fix_head` / `finding_origin_head`: `4282c0488510c4a46a81d4b5632ebaa236f619ac`.
- `validated_at`: `32a45c7754463aecdc9e77aadf7dfe9f5121e483`; tree `b9d55267145df2ff955b90851d65b529f7b9160f`.
- `executed_base`: `d72e220f1d21827c65e046f704c13837ea39d7c2` (unchanged merge-base).
- Scope: exact `4282c048..32a45c77` repair delta, including newly committed R1 reports but not reopening unchanged full implementation. Initial HEAD/tree/clean status and fixed diff checked. Design/spec/delta are unchanged; original R1 text above is retained, not rewritten.

**Patch result: 0 CRITICAL / 0 WARNING; no live new finding.**

```json
[]
```

| Focus finding | Status | Closure evidence |
|---|---|---|
| CR-1 concurrent counter / durable final route mismatch | **closed** | `approval.ts:92–103,169–183` computes `finish()` details inside the same `sessions.update` callback as actual `reached` counts; actual escalation uses those returned counts. The old independent `entries()` prediction is removed. Interactive/return-to-agent/unattended routes and fallback retain existing policy; cost-bearing row is not duplicated. |

### Repair logic and regressions

Only one production file changes. `record` now accepts either unchanged static details or a private details callback. Counts are captured **before** the existing total-limit reset, so reaching `totalDenyLimit` still triggers escalation even though stored counters reset to zero. The callback is evaluated once inside the existing serialized mutation, not by a new counter store or retry loop. Inspected locked DSH storage implementation (`@deepseek-ai/dsh-storage-domain/lib/index.js:278–286`) enqueues each update, invokes its mutation once, persists, then publishes the next rows. No callback replay assumption or async work was added inside that mutation. Existing write-failure propagation still prevents returning an allow after failed persistence.

Author's new `approval-retry.test.ts:31–58` exercises the public Cordis `tools/pre-execute` chain with synthetic reviewer/atomic table: two concurrent denies return `[deny, ask]`, and B's complete durable trace is `interactive_pending`. It is a maintained regression at the policy seam, not a native/live-provider claim. Reported source recovery+retry21/21 and later narrow31/31/typecheck results are supplemental engineering evidence; closure does not rely on counts alone.

Independent reviewer probe used `node --input-type=module` and **only** `output/feat625-build-32a45c77/packages/dsh-integration/lib/policy/approval.js`, resolving Cordis from that snapshot's package manifest. A public `Context.waterfall('tools/pre-execute', …)` drove two concurrent tool candidates, a synthetic low-risk-deny reviewer and a serialized asynchronous table (callback → simulated persist → publish). Synthetic model streams supplied known usage17 input/3 output per action through real `ReviewRecovery.run/ReviewAttempt.stream`. Each row below ran twice: consecutive limit2/total99, and consecutive99/total limit2 (stored reset branch).

| Cases (10 total) | Actual decisions A/B | Durable review routes A/B | Required fallback |
|---|---|---|---|
| human interactive ×2 | deny / ask | deny / interactive_pending | absent |
| schedule unattended allow ×2 | deny / allow | deny / unattended | allow |
| schedule unattended deny ×2 | deny / deny | deny / unattended | deny |
| Global human ×2 | deny / deny | deny / return_to_agent | absent |
| child with schedule + configured allow ×2 | deny / deny | deny / return_to_agent | absent (child cannot gain unattended allow) |

All ten passed (exit0). Each had exactly two complete recovery/cost rows, two usage-bearing rows and summed audit input usage34; each recovery kept knownUsage17/3 and usageComplete=true. A non-interactive escalation added exactly one existing fallback row linked by reviewId, with no duplicate usage/recovery. Total-limit cases stored reset counters0 while choosing the correct escalation. This is an independent deterministic public-policy/artifact check, **not native-loop/storage durability/model behavior**. An initial probe failed before execution because root workspace does not export Cordis; resolving the same locked package from the snapshot fixed only the probe's module location, not product code.

### Other patch surfaces / evidence

- True-IM configuration scenario was moved, not weakened: independent AST comparison found all five original test functions/decorators identical after the split (four retained + one moved), and pytest collected the same six parameterized cases. Files are397 and64 lines. Naming/size contract independently passed2/2 using the executed base. Both driver paths were added to runbook/fixture instructions.
- Native changes give only demonstrated observation polls10s and the existing owner-routing test an outer60s allowance. They retain exact HTTP-count, route, owner-isolation, zero/one-effect assertions and unchanged production30/60/90/action360/cleanup5s. A longer admission observation is not permission to accept extra reviewer calls.
- Snapshot manifest/loader proof were read. The snapshot initially lacked runtime assets and unchanged PA peer links; original failed `parallel-native.log` remains. Added local snapshot links do not change tracked source. Initialization alone was not accepted as packaging proof. Corrected snapshot run `parallel-native-r2.log:4–35` directly shows9files/29tests passed in102.20s, overlapping suites and actual Guardian90s timeout coverage. Read `parallel-native-r2-receipt.json:1–30`: complete9-file command/config, source SHA, collected worker job `bash-197` exit0, actual start/duration and default concurrency/no maxWorkers override. The snapshot config only sets test include/testTimeout, not worker serialization. This is inspected worker evidence (not a reviewer rerun) and the applicable parallel run, not the prior serial run.
- Independent hashes confirm original Q artifact `packages/dsh-integration/lib/policy/approval.js` remains `b01ac3cb0e3f17117aacbe0ec3ba6d3c80d447c03aab1ddb0bdf539b74f97be4`; probe snapshot approval is `562a95df04e2df799fc44440f4ebd7dc37cf691907b0341074c695e7126e194c`. No original lib build or Q-service operation was performed by the reviewer.

### Context impact / remaining boundary

R1 Mode B coverage and its limits remain applicable: this patch changes when the already promised final audit route is derived, not prompts, source projection/admission, model/effort, schemas, reviewer identity, recovery quota or disclosure lifetime. The changed audit path was checked together with actual returned decisions and fallback linkage above. No new Context finding or need to repeat full Mode B was established. New true-IM route fixtures, later source changes, Q version reconciliation and corrected delta are outside this fixed patch. **CR-1 closed is not whole-unit/CI/Q acceptance**; retained verifier C-1 is still open. No full re-review is required by this delta.

## Round 3 — test-only patch

- `review_mode`: `patch`; `review_round`: `3`.
- Exact diff: `2190fb380..fe623b4bb8227f06d720cd5b11f81dd98e5af72f`.
- `validated_at`: `fe623b4bb8227f06d720cd5b11f81dd98e5af72f`; tree `b7b3f470d628b930c56ec594d48d952772acdaee`.
- `executed_base`: `d72e220f1d21827c65e046f704c13837ea39d7c2`; previous implementation review remains at32a45. Initial clean HEAD/tree/merge-base and fixed delta were independently checked. Ten changed files are tests, fixture/helper and progress only; no production/src/spec/design/target-delta change. R1/R2 remain historical, unchanged; their report commit03de1a917 and Q report commit2190fb380 are not reinterpreted as implementation changes.

**Result: 0 CRITICAL / 0 WARNING; no live patch finding.**

```json
[]
```

### Coverage and concrete checks

| Patch surface | Independent review result / limits |
|---|---|
| Shared `_auto_review_retry.py` extraction | Fixed-Git AST comparison confirms all pre-existing test/journey/configuration functions/decorators and moved `_records/_trace/_login` are unchanged. Resolving new `_stack`'s default basic-profile branch and removing only its added keyword defaults produces the exact old `_stack` AST. Root resolution remains correct at the same directory depth; owned stack/fixture finally cleanup is retained. |
| New real-IM route matrix | `test_auto_review_routes_critical_path.py:14–187`: seven profile/fallback parameter rows×two actual agent strategies, shared real IM HTTP/WS path, three pending-bash review requests, technical no_verdict with zero deny counters, exact finalRoute/retries2/transient, timer fallbackOutcome, zero effect except exactly one line under configured timer allow, no non-interactive permission card, stable config/Auto snapshot. Global/child deliberately configure allow yet assert return_to_agent/zero effect. |
| Genuine route entry rather than forged source | Fixture Global bootstrap calls Inbox check/read to acquire the real message; child emits a native subagent call and verifies two main session IDs. Schedule emits native schedule_create/after_seconds and waits for later timer execution; heartbeat writes substantive HEARTBEAT.md then enables the real IM heartbeat config. No synthetic RuntimeClient session.submit/source injection was added. Schedule/heartbeat markers and audit route are checked together, not treated as authorization by themselves. |
| Fixture discrimination | `_pending_tool` reads only explicit planned action/last CC action row. Ancillary route tools receive valid fixture allow; only the pending bash gets actual HTTP503 on every attempt. Per-session **main** ordinals are separated from reviewer ordinals (CC shares a native session with its parent); this prevents the prior fixture counter issue from skipping public ACK. This is a model stub, not live-model tool selection. |
| Complete continuous/mixed budgets | `review-recovery-budget.test.ts:9–69` checks three exact30/60/90s timeouts, timeout→503→timeout with the shared two-extra ceiling/no fourth call, CC normal stage progression sharing the quota, and generation revocation at360s/no successor. Fake timers drive real controller cancellation; the near-wall test intentionally starts a low-level attempt at359999ms, not a claim that a normal production action needs that preparation time. |
| Permanent configuration negative control | `review-recovery.test.ts:50–58` adds CONFIGURATION with status503 and requires permanent, one callback, retries0. It cannot pass merely because status503 was classified transient. |
| Context/technical-retry combination | `codex-approval-lifecycle.test.ts:142–164`: overflow→503→503→allow uses exactly one action rebuild/two service retries; repeated overflow after503 fails with no second rebuild. Assertions cover call/attempt counts,90s budgets, unique reviewer IDs and original evidence in every input. Synthetic create/turn handles, not native HTTP/provider input evidence. |
| Disposal harness correction | `pending.catch` in synthetic handle dispose drains an already failed judgment rather than rethrowing judgment failure as disposal failure. Explicit lifecycle disposing hook still runs before that catch, so its failure is not swallowed. Existing late-create/quarantine/blocked-disposal and cancellation tests remain; no production cleanup behavior changed. |
| Audit-write-failure negative controls | `approval-retry.test.ts:31–48`: public Cordis pre-execute, valid allow/deny/unavailable with existing unattended allow config; mutation then controlled persistence rejection must propagate. Exactly one review/write, zero synthetic effect and no durable row. This targets facade failure propagation, not service recovery or actual IM disk outage; it does not fake a durable row on error. |

### Executed evidence

- Independently ran the four source files at cleanfe623: `pnpm exec vitest run packages/dsh-integration/tests/review-recovery-budget.test.ts packages/dsh-integration/tests/review-recovery.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts packages/dsh-integration/tests/approval-retry.test.ts` → **45/45, four files, exit0**,15:59:53+08,948ms. These are fake-clock/in-memory tests; no native services, build or daily stack were started/touched.
- `NANO_TEST_BASE_REF=d72e220f1d21827c65e046f704c13837ea39d7c2 .venv/bin/python -m pytest tests/contract/test_test_naming_and_size_contract.py -q` → **2passed0.25s, exit0**. Shared helper201lines, retry246, configuration64, routes187; new tests stay within400.
- `pytest <retry/configuration/routes paths> --collect-only -q` → **13 parameterized cases**, exit0; old six remain plus seven route rows. Collection does not run a service.
- Read-only existing `output/feat625-routes-r3/test_real_im_exhaustion_preser{0,1}/requests.jsonl` and r5`{0,1,2,3}`:12 policy/profile captures each have exactly three pending-bash review HTTP requests; child has two main session IDs, schedule/heartbeat captures contain actual wake prompts. Structural assertions passed; no raw prompts/identities copied into this report. These are **4282 compiled-runtime captures**, not fe623 execution.
- Read worker-transcribed `output/feat625-post-q-r1-execution-receipts.json:1–38`: exact commands/env and job233/239 failures, job2414timer cases pass114.03s, job24345/source checks. Original stdout was not teed; this is an inspected transcription of native completion receipts, not independently read original stdout. The recorded fixture startup/assertion failures remain failures, not silently included in an all-green matrix. New same-SHA whole-stack/Q run remains pending.

### Context and gate boundary

Production consumers, prompts, source selection, effort/schema, context reconstruction and PA namespace/parser are unchanged, so R1 Mode B with R2's retained boundary remains applicable; another full Mode B would not inspect new production input behavior. The new tests' trust-sensitive route acquisition and synthetic evidence claims were specifically checked above. They add verification, not authority or a product debug switch. There is no new Context finding and no reason to widen to full code review.

CR-1/W-1/W-2 stay closed at their reviewed implementation/test versions. C-1 remains open: the Q R1 report is fail/inconclusive at4282, old fixture success cannot be relabeled fe623, and coordinated new build/whole matrix/Q/current-spec/corrected-delta/CI remain outside this patch signature. Reports are the reviewer's only writes; original author retains implementation, runtime and further fixes.
