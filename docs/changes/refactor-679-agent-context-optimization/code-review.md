# Independent code review — refactor-679-agent-context-optimization

## Status and scope

**Pre-freeze review; not a final gate verdict.** Latest scoped repair results below supersede the original findings only for independently rechecked paths. The historical findings apply to the dirty implementation at baseline HEAD `4b27d962c1cc09a27a567619bd5cabc3db2ee934`, before the parent fixes. A separate final freeze/regression/product/provider gate remains required. Upstream target: `unit/feat-676`, not main. No final PASS is authorized by this report.

Fresh independent context, inheriting current model as an approved SDK limitation substitute; the SDK did not configure model or effort. **Do not interpret this as use of `gpt-6.1-sol/high`.** The reviewer read the approved [design](<docs/changes/refactor-679-agent-context-optimization/design.md>), [Gate 2 report](<docs/changes/refactor-679-agent-context-optimization/design-review.md>), active deltas, current contracts, actual dirty diff and untracked production code. No production/test/spec fixes were made.

## Latest scoped repair recheck — not a final gate

The parent narrowed this round to the prior two CRITICAL findings and one business-semantic WARNING, not the entire frozen gate. Using the approved inherited-model substitute and required Node v24.22.1, this reviewer independently reran actual native RuntimeClient + PA TaskContext/Inbox witnesses and actual public Global/Inbox reads. Full evidence, intermediate failures, built-input hashes and replayable temporary native code are in [review-witnesses](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate>).

| Prior finding / repair-chain issue | Latest scoped result |
|---|---|
| C1: center outage blocks unrelated external input | Repaired for ordinary human web/Feishu, feature on/off; provider receives ordinary input with one current D9 while uncertain originals remain pending |
| C1 negative boundary and recovery | Task-only outage reaches no provider/no observed idle hotloop; changed retries once; restored original is natively consumed exactly once |
| C2: revoked unconsumed Task leaks through old public unread cursor | Exact counterexample repaired; direct native consumption also deduplicates an old cursor; saved ordinary consumed read preserved |
| C3: original notices lack assignment roles/relation endpoints | Actual formatter assertions confirm explicit old/new roles, directed relation/dependency endpoints, references and directly affected owners |
| Intermediate omission: D9 without executable Task tool gate | Independently identified; parent added native pre-execute denial; actual feature-off allowlisted Task apply cannot reach product while unavailable |
| Intermediate sticky authority flag after recovery | Actual native same-session counterexample reproduced, then repaired by per-tool current snapshot revalidation; exact rerun now denies offline and allows one product call after recovery |

Latest native job `bash-2f630a1037a04d46` completed exit 0 with four relevant built hashes unchanged before/after. Original C1/C2/C3 counterexamples and both repair-chain residuals are closed **only in these rechecked working-snapshot paths**. No unresolved finding from this narrow recheck is asserted:

```json
[]
```

No final PASS, PR recommendation, M1 signoff, whole-diff assurance, child-cold result or real-model/product acceptance is given. Those require a separate frozen gate and parent evidence. No production or permanent test was modified. Historical findings below are retained for audit, not counted as current unresolved defects.

## Historical pre-fix findings (required JSON)

```json
[
  {
    "file": "packages/dsh-integration/src/task-context.ts",
    "line": 25,
    "summary": "[P1] Keep independent external input available when IM Task sync is unavailable",
    "failure_scenario": "Every bound root pre-step unconditionally calls product.task_context.prepare, whose product implementation unconditionally requests task_context.sync. With task_graph=false, no tasks or pending context and an ordinary human Feishu question, an offline IM makes the native turn terminate before any provider invocation. The authorized native witness produced accepted=true, terminal CENTER_OFFLINE_NO_TASKS and providerCalls=0. This violates the existing local-autonomy boundary and approved independent-input degradation; fail-closed stale Task processing must not become fail-closed all conversation.",
    "review_mode": "static chain review + authorized native provider witness",
    "status": "CONFIRMED"
  },
  {
    "file": "packages/personal-assistant/src/inbox.ts",
    "line": 235,
    "summary": "[P1] Retract revoked unconsumed Task fragments from frozen unread cursors",
    "failure_scenario": "Create an unread snapshot with an ordinary first message and Task on its second page; consume only the first page, then revoke the Task before it was ever returned or natively consumed. revokeSystemContext marks its inbox row consumed and removes reads, but leaves snapshots.fragments; a new GlobalAgent.call(inbox read) with the old cursor returns the full revoked Task. A still-public readable source passes info authorization even after Task handling eligibility shrinks. The exact witness confirms check.sources=[] followed by the withdrawn title/requirements on the old cursor, so this is not preserved consumed history.",
    "review_mode": "static chain review + authorized public-source Global/Inbox witness",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/im-server/src/task-notifications.ts",
    "line": 32,
    "summary": "[P2] Include relation endpoints/direction and explicit old-to-new assignee roles in original notices",
    "failure_scenario": "A parent/derived/replacement/dependency edit emits only generic relationship-updated wording and the changed node link; metadata.task_refs also contains only that node, so the other endpoint, the old/new relation and business direction cannot be recovered from the original message. Reassignment similarly emits only 已改派 and appends unlabelled new/old mentions, not from A to B. The active IM delta explicitly requires locatable endpoints/business meaning and from-@A-to-@B wording. Mentioning affected owners alone does not supply the missing task identities or roles.",
    "review_mode": "static implementation and approved-contract review",
    "status": "CONFIRMED"
  }
]
```

## Historical pre-fix agent-context implementation review

### C1: Unconditional synchronization replaces independent-input availability

- **Surface:** root native pre-step, product context RPC and IM catch-up.
- **Expected:** unavailable Task synchronization blocks adoption of stale Task originals/automatic Task steps, preserves pending state without a hot loop, but independent external input retains its existing local-autonomy behavior.
- **Observed:** unconditional await fails the whole native turn, including `task_graph=false`, empty Task state and a plain external question.
- **Impact:** IM downtime prevents unrelated external-channel conversations from reaching the provider.
- **Recommendation:** distinguish unavailable Task context from independent input; do not admit old queued/claimed Task candidates or run automatic Task continuation while allowing an explicit, bounded independent-input degradation.
- **Severity:** CRITICAL / P1.
- **Evidence:** [native pre-step](<packages/dsh-integration/src/task-context.ts#L21-L25>), [product synchronization](<packages/personal-assistant/src/task-context.ts#L30-L71>), [witness A](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#L10>), [architecture availability](<SPEC.md#L22>), [approved synchronization/degradation design](<docs/changes/refactor-679-agent-context-optimization/design.md#L157-L191>).

### C2: Alternate unread projection survives terminal Task revocation

- **Surface:** frozen Inbox cursor → new tool result → next native model input.
- **Expected:** every not-yet-consumed projection of a withdrawn Task is retracted, including pending cached read fragments; already-consumed canonical history remains intact.
- **Observed:** `revokeSystemContext` leaves frozen snapshots; a fresh cursor read first exposes the Task after revocation.
- **Impact:** withdrawn Task facts reenter an actionable unread tool surface after their direct/native route was correctly revoked. This witness does not claim exposure of otherwise-private source data or prove model behavior.
- **Recommendation:** terminalize/filter affected pending fragments in all snapshots and saved-but-unconsumed read projections; add the exact multi-page/public-read regression and verify direct-consumption deduplication too.
- **Severity:** CRITICAL / P1 (Task revocation boundary).
- **Evidence:** [revocation](<packages/personal-assistant/src/inbox.ts#L233-L235>), [frozen cursor path](<packages/personal-assistant/src/inbox.ts#L293-L317>), [Global call](<packages/personal-assistant/src/global-agent.ts#L460-L473>), [witness B](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#L56>), [active revocation scenario](<docs/changes/refactor-679-agent-context-optimization/specs/im/task-graphs.md#L37-L41>).

### C3: Original task notice lacks business facts that the replacement path requires

- **Surface:** transactionally persisted task system message, shared by humans and direct Agent context.
- **Expected:** old/new responsibility roles and both relation endpoints/business direction are self-locatable in the one original business message; no private replacement snapshot is needed.
- **Observed:** generic relation labels plus one task reference, or generic reassignment plus unlabelled mentions.
- **Impact:** the receiver cannot determine which dependency/parent/replacement changed or who handed responsibility to whom without reconstructing absent historical facts.
- **Recommendation:** preserve one original message but encode the missing endpoints and explicit old→new responsibility roles; test visible text and structured references, including deletion/old-parent cases. Do not weaken the active delta to match the omission.
- **Severity:** WARNING / P2.
- **Evidence:** [assignment wording](<apps/im-server/src/task-notifications.ts#L21>), [relationship wording](<apps/im-server/src/task-notifications.ts#L32-L39>), [one-node metadata](<apps/im-server/src/task-notifications.ts#L48-L52>), [approved business-message contract](<docs/changes/refactor-679-agent-context-optimization/design.md#L126-L140>), [active IM delta](<docs/changes/refactor-679-agent-context-optimization/specs/im/task-graphs.md#L11-L24>).

## Non-findings / evidence limitations

- No private DSH runtime import or second Agent Loop was found in inspected production changes; declared public integration remains the runtime boundary. This is static inspection, not a substitute for the final dependency-contract run.
- Root runtime/catalog ordering preserves other message identities; memory remains a separate source. Native/provider fixtures were inspected rather than rerun by this reviewer.
- Worker P2 and read-only reviewer P2R remain separate in inspected policy assembly; this is not an independent real-model security verdict.
- Durable Schedule deletion intents distinguish missing from unavailable and separate Schedule-change from Task-repair notifications. Parent is completing native child/restart fixtures; this reviewer does not claim those pending exits passed.
- The initial review executed only the original two authorized narrow witnesses; subsequent Node24 repair rechecks are explicitly recorded above. Default regression, whole-unit final native results, isolated product journeys, first/running/offline/summary provider captures, real-model behavior and final source freeze remain separate handoff/gate requirements.

## Required final closure outside this recheck

The scoped repairs were reopened and rechecked as recorded above. Bind a separate whole-unit review to the final frozen source and authoritative regression, native, milestone, product and provider evidence before a merge recommendation. Historical findings remain an audit record, not a current unresolved count, final design-verification verdict or product acceptance.
