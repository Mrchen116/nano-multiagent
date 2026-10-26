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
