# Final frozen full code review — refactor-679

> Review mode: **full** plus **agent-context-review / Implementation Review**. Executed base `4b27d962c1cc09a27a567619bd5cabc3db2ee934`; full-reviewed source `b610b02b56bb3760448208dfd567f1fba8034e51`, with targeted repair deltas reviewed through `6881952b96ea3a1575f5fbad44d6a717d8fb48c9`; branch `codex/refactor-679-on-memory`; integration target `unit/feat-676`, not main. The reviewer did not participate in implementation and changed only this report and verification.md. HEAD and clean implementation state were checked before review. Documentation changes after the validated source do not change that source fingerprint.

## Final closure

**Final code review: `[]`; final verifier: PASS; corrected-delta: aligned.** Source freeze remains `6881952b96ea3a1575f5fbad44d6a717d8fb48c9`; all five actual product findings are independently closed in [acceptance final-4](acceptance.md). The final verifier also cross-checked native current-permission lookup → latest revision8 Task read → correct private delivery, with both Tasks still todo. Representative real-model behavior and controlled raw HTTP serialization remain separate evidence classes; no production/deployment claim is made.

Retain this full-plus-targeted result through exact canonical merge of the three audited deltas, whole-unit archive and relative-link migration. Those documentation-only steps require docs-check, not another full code/Context/product review. No additional design/spec semantic change is required. Caller owns final commit/PR/CI/Memory merge and cleanup; this reviewer stops writing reports after this closure.

## Full code-review result

```json
[]
```

No surviving confirmed or plausible correctness defect was found in the complete specified diff and affected consumers. The later authorized doing-Task tool denial (PA679-1) was traced to missing Channels typed reply correlation and is repaired; the parent's real-model recheck read the existing Task, delivered its result to the fixed group and marked it done without needing the user to paste the body. See the delta review below. Product PA679-2/3 are now independently closed in acceptance final-3. PA679-4/5 have targeted implementation repairs reviewed below and are independently closed by final-4 acceptance. The final full verifier is PASS with V-FINAL-1 closed. This is a code-review conclusion, not an M1 product-acceptance or deployment claim. Historical findings below are retained as history; their pre-fix counts are not current unresolved issues.

The full review traced the original Task business message through the transaction, durable index, relay, bounded fixed-cut catch-up, persistent product mapping, native claimed candidates, actual-consumption evidence and Inbox alternate read/cursor projection. It also checked ordinary Global, PA and SingleThread wiring, stop restoration, automatic continuation and held-action safeguards, root-private child projection, native child cold recovery, Schedule user/tool deletion and independent receipt recovery, the rewritten prompt consumers, four independent approval assemblers, and the Memory owner-workspace write-policy repair.

| Historical defect / repair | Final source disposition and regression seam |
|---|---|
| C1: authority outage blocked independent input | Closed: TaskContext returns explicit unavailable; native admission retains independent input, Task driver supplies D9 and blocks Task tools; pending Task-only candidates do not enter provider. `task-context-sync.test.ts` and prior [scoped witnesses](review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate) cover outage, recovery and no idle loop. |
| C2: frozen unread cursor exposed revoked Task | Closed: unread-page filtering rechecks current consumption/revocation and direct consumption invalidates pending read receipts; consumed history is retained. [Prior public-source witness](review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate), Inbox regression and native originals cover alternate projection and claimed candidates. |
| C3: reassignment/relation notice omitted business identities | Closed: original formatter states old/new assignee roles, old/new relation endpoints and directed dependency changes, with current-member mentions and task_refs. `task-notifications.test.ts` protects the user-visible semantics. |
| Intermediate offline Task-tool gate / recovered availability | Closed in the scoped witness and current pre-execute gate; current snapshot revalidation remains independent of Feature selection. |
| Owner-workspace document writes | Initialization and publication pass the configured owner root and preserve the backend sandbox mode; read-only remains read-only. `memory-documents.test.ts` and `memory-workspace-native.test.ts` cover both policy preservation and a runtime cwd outside the owner workspace. |

## Targeted repair delta — b610b02 → 6dc940cf6

**Mode: delta code review + targeted verifier repair check + affected Context Implementation Review.** This review covers only the 11-file repair delta, retains the full b610b02 review above and does not reopen the whole unit. HEAD was exactly `6dc940cf693830ee92bd06c4e1f2d734ceaf758f`; only authorized report changes and the acceptance/review reports were dirty. The approved design timing change is [Gate 2 Round 6](design-review.md#round-6).

```json
[]
```

| Fix / observation | Independent static closure and applicable evidence |
|---|---|
| PA679-1: Task sync reply never resolved through real Channels | `packages/channels/src/index.ts` now matches `task.context.sync.result` by `request_id`; existing real WebSocket correlation/rejection/FIFO test includes Task sync. Parent reports 16 Channels tests passed; the actual product Task read/delivery/done recovery is recorded in [acceptance final-2](acceptance.md). **Closed.** |
| PA empty-unread source authority lagged current Memory assembly | `TaskContextDriver` prepares before outer `system-prompt/assemble.next()`, then consumes one Agent-local preparation in native pre-step. Only bound root assemblies carrying the native turn signal participate; preview/child/Dreaming skip. Current native order claim→assemble→runtime project→pre-step guarantees the per-step preparation. Claimed-candidate revocation, independent-input rejection and persisted consumption evidence stay in their original owners. Round 6 approves the timing. New real cross-package native fixture proves generation 1 before exclusion and generation 2/entry_basis_stale/stop-use in the immediately next request despite empty unread. **Closed in native seam.** |
| PA679-2: delete returned before persisting business originals | Shared persistNotices closure runs inside the same existing mutation transaction before delete receipt/return for both root and subtree. Existing post-COMMIT publication remains unchanged; replayed receipts create no new messages. Permanent root/subtree cases verify original messages, current mentions, no dead detail links, durable index and no replay publication. **Implementation repaired; subsequent independent final-3 product recheck passed.** |
| PA679-3: self-deletion repair only reached next turn | Running native Agent now uses inject so concrete current D7 reaches its next step; idle uses followup, explicit stop remains passive. New held-tool native test proves the next request contains the stable repair input, specific Task and exactly one current package. **Implementation repaired; subsequent independent final-3 product recheck passed.** |
| Existing child-tool fixture diagnostic | Adds only a child.kind assertion before dereferencing child.events; no fallback/skip or product behavior change. Both PA=false/true cases pass in final isolated rerun. |

Reused final evidence: `final-fix-focused.log` (8 files/41 passed; all affected assembly/delete/native-original/source-sync seams), `repair-child-focus.log` (2 files/4 passed, final running repair and Global child-tool isolation). The preceding red logs are retained as counterexamples and are not counted as final passing runs. The broad suite had 938 passed plus six timeouts; five affected files/12 tests then passed, with the remaining global-child transient diagnostic closed by the final two-case rerun. This is scoped closure of every observed failed case, not a claim that the original broad command exited zero. Exact commands and evidence accounting are in [verification](verification.md#targeted-repair-verification--6dc940cf6).

No new confirmed/plausible code or Context defect was found in this repair delta. **At this round V-FINAL-1 remained open for product evidence; later final-3 acceptance closes PA679-2/3, while the next targeted round below tracks the remaining issues.** No code, test or design was modified by this reviewer.

## Second targeted repair delta — 6dc940cf6 → 6881952b9

**Mode: delta code review + targeted verifier repair check + affected Context Implementation Review.** Only the five-file repair delta and directly affected publication/projection/consumer paths were rechecked; retained full and first-delta conclusions are not reopened. Frozen HEAD `6881952b96ea3a1575f5fbad44d6a717d8fb48c9`; no source/test/design edits were made by this reviewer. Gate 2 [Round 7](design-review.md#round-7) approves the D3 wording refinement.

```json
[]
```

| Issue / Surface | Expected, observed and disposition |
|---|---|
| PA679-4: current collaborator's visible revocation fact | Current readers need the affected subject and Tasks; withdrawn Agent must receive only the minimal fact. The same authority transaction now writes the visible original with escaped Agent display name/ID plus assigned Task titles/links/refs. Message/event/preview share that visible version. The separate same-ID `taskContextRevocation` object still builds the lost-source index sync and relay without those names/titles/links/refs; current-reader publication uses the existing current read ACL. New real HTTP member-removal regression inspects persisted/publicized original, sync projection and actual durable relay equality; 6 files/53 tests pass in `visible-revocation-green.log`, including rollback/migration/identity/Task flows. **Implementation repaired; actual final-4 product recheck passed.** |
| PA679-5: historical D3 loss treated as permanent after restored current access | Revised Inbox D3 body exactly matches approved design: revocation is at supplied event_time; a later independently authorized request may verify current permissions through available tools; restored access does not resume paused Tasks or authorize previously denied actions. Minimal event data remains only message/conversation/time and contains no withdrawn original body. No ACL, lifecycle, Task state, input provenance or automatic resumption path changes. Inbox/Task-context regression: 2 files/18 tests passed in `eligibility-tests.log`. **Implementation/design aligned; final-4 actual model/tool/product recheck passed without starting todo work.** |

The new visible-original regression was intentionally red while the broad runtime command collected it: `final-runtime-tests.log` has **180 passed files/949 passed tests plus one failed red test**. The later 53-test green run closes that exact observed failure; the original broad run is not reported as exit zero. The current `task-sync-green.log` was also read and confirms the previously reported 16 Channels tests.

The reviewer independently parsed `/tmp/nano-refactor679-daily/provider-wire-DOCUMENT.json` (3 HTTP requests; SHA-256 `021573e38a18afce5cfb111d934aad24b0504233153a86171a7a4c838cffd760`) and `provider-wire-LEGACY.json` (4 requests including one summary; SHA-256 `cd72a9951081dfd880d7ddbc8d851979460ceb717399da35821dc2407e714790`). Actual request paths are `/v1/messages?beta=true`, root/session `wire-session`, model `fixture`. Document and legacy entry markers are mutually exclusive; both retain fixed creator guidance and new Task originals. Final document request contains actual manual-window reset, and final legacy request contains the actual native summary output. These are controlled provider HTTP payloads and support assembly/recovery, not autonomous model reliability or revised-D3 behavior.

No new confirmed/plausible code or Context defect was found. Product final-3 independently closes PA679-2/3; **PA679-4/5 and final M1 product verdict are now PASS; V-FINAL-1 is closed in verification.md**.

## Context implementation review

**Trigger and scope:** System Prompt, native runtime/Skill ordering, D3–D10 input assembly, authority provenance, Task lifecycle, Schedule reminders, root/child projection and affected document/legacy Memory composition. The consumer is the model at its actual request boundary; source objects and persisted messages alone were not counted as consumption.

- **Prompt and tool composition:** P0/P1/P1S/P1C, shared P2 versus independent-review P2R, P3/P3C, enabled P5/P6 and unchanged P7–P9 were checked against the approved design. The four independent review consumers keep read-only source semantics and their original decision/output contracts. Fixed skill-creator/P9 remain independent of obsolete skill_creation flags and configurable Skill selection. Existing custom guidance is not backfilled.
- **Actual native/HTTP seams:** `context-order-provider.test.ts` captures serialized Anthropic requests before/after native restart, configuration and Skill changes. `context-revalidation-provider.test.ts` performs actual native window reset and native summarization, captures the resulting HTTP requests, consumes the real built-in creator Skill and document read tools, and verifies document/legacy exclusivity and Task original native receipts. `task-child-context.test.ts` captures one-shot/continuable fork and cold-resume requests; only inherited root-private Task packages are hidden, while canonical events, business originals, authority evidence and local child inputs remain.
- **Trust and parameters:** model parameters remain discoverable through original IDs, fixed Task references/conversations and native tool schemas. Product agent/owner/session, authenticated stop control, deletion actor and operation identity are host-derived; ordinary message bodies and task titles cannot create human control provenance. Revoked unconsumed content is removed from both queued and claimed native candidates, with minimal withdrawal facts retained.
- **Persistence and recovery:** fixed cut is independent of consumed position; messages/terminal references persist before cursor advancement; old unfinished relay migration uses authoritative IDs. Stop and lifecycle fences restore before recovery. Schedule deletion has one durable intent plus independent user-change and Task-repair receipts; missing/unavailable and normal due occurrences remain distinct. Cold unsupported one-shot notification remains pending instead of inventing a continuation.
- **Memory preservation:** foreground formal memory remains read-only and Dreaming remains the durable writer. Task prepare invokes the complete PA source refresh before catch-up; the separate document assembly and explicit legacy branch retain their owners. Unchanged Memory baselines were also inspected: `memory-runtime.test.ts` captures current entry-version invalidation; `memory-child-runtime.test.ts` captures four requests from the same native child through pending/excluded source state while preserving foreground read-only; PA `personal-attention.test.ts` checks source-withdrawal stop-use and original-child guidance. The affected empty-unread Task-prepare/PA-sync cross-package connection is now covered by the passing new native fixture in the targeted repair delta above.

**Evidence limits:** focused recovery logs include earlier failures and are not blanket PASS evidence. The final HTTP revalidation rerun is `output/refactor-679/recovery-wire.log` (2/2 passed). The two Memory fixtures passed 8 tests in `recovery-fix.log`; its unrelated HTTP fixture failure is superseded only by the later wire rerun. `recovery-focused.log` validly supports the passed child/deletion/Task-sync fixtures, not its failed Memory/provider cells. Final regression closure, R1–R6 product PASS, representative real-model behavior and affected PA-source evidence are accepted in [verification](verification.md). A controlled provider proves serialized delivery and deterministic tool consumption, not autonomous model understanding.

No new Context finding is asserted. The formerly missing final evidence is now supplied and V-FINAL-1 is explicitly closed in verification.md; historical limitations and failed runs remain recorded.

---

# Historical review records (superseded by the frozen full code review above)

# Independent code review — refactor-679-agent-context-optimization

## Status and scope

**Pre-freeze review; not a final gate verdict.** Latest scoped repair results below supersede the original findings only for independently rechecked paths. The historical findings apply to the dirty implementation at baseline HEAD `4b27d962c1cc09a27a567619bd5cabc3db2ee934`, before the parent fixes. A separate final freeze/regression/product/provider gate remains required. Upstream target: `unit/feat-676`, not main. No final PASS is authorized by this report.

Fresh independent context, inheriting current model as an approved SDK limitation substitute; the SDK did not configure model or effort. **Do not interpret this as use of `gpt-6.1-sol/high`.** The reviewer read the approved [design](<design.md>), [Gate 2 report](<design-review.md>), active deltas, current contracts, actual dirty diff and untracked production code. No production/test/spec fixes were made.

## Latest scoped repair recheck — not a final gate

The parent narrowed this round to the prior two CRITICAL findings and one business-semantic WARNING, not the entire frozen gate. Using the approved inherited-model substitute and required Node v24.22.1, this reviewer independently reran actual native RuntimeClient + PA TaskContext/Inbox witnesses and actual public Global/Inbox reads. Full evidence, intermediate failures, built-input hashes and replayable temporary native code are in [review-witnesses](<review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate>).

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
- **Evidence:** [native pre-step](../../../../packages/dsh-integration/src/task-context.ts#L21-L25), [product synchronization](../../../../packages/personal-assistant/src/task-context.ts#L30-L71), [witness A](<review-witnesses.md#L10>), [architecture availability](../../../../SPEC.md#L22), [approved synchronization/degradation design](<design.md#L157-L191>).

### C2: Alternate unread projection survives terminal Task revocation

- **Surface:** frozen Inbox cursor → new tool result → next native model input.
- **Expected:** every not-yet-consumed projection of a withdrawn Task is retracted, including pending cached read fragments; already-consumed canonical history remains intact.
- **Observed:** `revokeSystemContext` leaves frozen snapshots; a fresh cursor read first exposes the Task after revocation.
- **Impact:** withdrawn Task facts reenter an actionable unread tool surface after their direct/native route was correctly revoked. This witness does not claim exposure of otherwise-private source data or prove model behavior.
- **Recommendation:** terminalize/filter affected pending fragments in all snapshots and saved-but-unconsumed read projections; add the exact multi-page/public-read regression and verify direct-consumption deduplication too.
- **Severity:** CRITICAL / P1 (Task revocation boundary).
- **Evidence:** [revocation](../../../../packages/personal-assistant/src/inbox.ts#L233-L235), [frozen cursor path](../../../../packages/personal-assistant/src/inbox.ts#L293-L317), [Global call](../../../../packages/personal-assistant/src/global-agent.ts#L460-L473), [witness B](<review-witnesses.md#L56>), [active revocation scenario](<specs/im/task-graphs.md#L37-L41>).

### C3: Original task notice lacks business facts that the replacement path requires

- **Surface:** transactionally persisted task system message, shared by humans and direct Agent context.
- **Expected:** old/new responsibility roles and both relation endpoints/business direction are self-locatable in the one original business message; no private replacement snapshot is needed.
- **Observed:** generic relation labels plus one task reference, or generic reassignment plus unlabelled mentions.
- **Impact:** the receiver cannot determine which dependency/parent/replacement changed or who handed responsibility to whom without reconstructing absent historical facts.
- **Recommendation:** preserve one original message but encode the missing endpoints and explicit old→new responsibility roles; test visible text and structured references, including deletion/old-parent cases. Do not weaken the active delta to match the omission.
- **Severity:** WARNING / P2.
- **Evidence:** [assignment wording](../../../../apps/im-server/src/task-notifications.ts#L21), [relationship wording](../../../../apps/im-server/src/task-notifications.ts#L32-L39), [one-node metadata](../../../../apps/im-server/src/task-notifications.ts#L48-L52), [approved business-message contract](<design.md#L126-L140>), [active IM delta](<specs/im/task-graphs.md#L11-L24>).

## Non-findings / evidence limitations

- No private DSH runtime import or second Agent Loop was found in inspected production changes; declared public integration remains the runtime boundary. This is static inspection, not a substitute for the final dependency-contract run.
- Root runtime/catalog ordering preserves other message identities; memory remains a separate source. Native/provider fixtures were inspected rather than rerun by this reviewer.
- Worker P2 and read-only reviewer P2R remain separate in inspected policy assembly; this is not an independent real-model security verdict.
- Durable Schedule deletion intents distinguish missing from unavailable and separate Schedule-change from Task-repair notifications. Parent is completing native child/restart fixtures; this reviewer does not claim those pending exits passed.
- The initial review executed only the original two authorized narrow witnesses; subsequent Node24 repair rechecks are explicitly recorded above. Default regression, whole-unit final native results, isolated product journeys, first/running/offline/summary provider captures, real-model behavior and final source freeze remain separate handoff/gate requirements.

## Required final closure outside this recheck

The scoped repairs were reopened and rechecked as recorded above. Bind a separate whole-unit review to the final frozen source and authoritative regression, native, milestone, product and provider evidence before a merge recommendation. Historical findings remain an audit record, not a current unresolved count, final design-verification verdict or product acceptance.


## User-acceptance follow-up — independent delta review (2026-10-31)

This is the latest review round. Earlier frozen-source PASS records remain historical/retained for unaffected behavior; they do not certify the new dirty implementation or the pending product/provider acceptance.

- Mode: **change-code-review delta + Agent Context Implementation Review**; no whole-unit rereview.
- Nano checkout: `codex/refactor-679-context-followup`, base/HEAD `5e5d3fcc801c6ad766910b126a10ee25076627a9`, reviewed working diff under apps/packages/pnpm-lock, SHA-256 `96590047ea4fc55b6a13866c3c651baa3171b8f2b15194522b23ff5cab4ae901` (dependency URL still local at this snapshot).
- Owned plugin: `/Users/czj/Repos/opensource-hub/dsh-agent-context-feat-676`, branch `codex/refactor-679-window-identity`, base/HEAD `fa2b47d470b5cd51f569b678da17fb3b4f43188d`; complete seven-file working diff SHA-256 `668ecd5e7d8563bd97f9a484833a3fefa35bea2598a91c894fedf08c56f85aca`.
- Authority: approved [Round 8 design review](design-review.md#round-8), appended user-acceptance design/motivation and affected Gateway capability/Task deltas. Only this and verification.md were written by the reviewer; no source/test/design changes, release publication, real-model calls or services were performed.

### Findings

```json
[]
```

No confirmed or plausible correctness defect found in the reviewed scope. Missing final evidence below is a verifier gap, not an invented product defect. The temporary local tarball is a declared integration intermediate and must be replaced/locked before final delivery; it is not accepted as a portable final dependency.

### Actual coverage and Context evidence

| Surface / risk | Independent source and relevant regression check |
|---|---|
| Node displayName → root/PA/child identity | Canonical title/display_name fallback is carried through both configuration contracts. Agent-local identity section JSON-quotes name and ID, disables interpolation, distinguishes internal child ownership and reads the effective config object updated by the existing idle commit path. Existing custom prompts and actual public communication capabilities remain separate. Node configuration tests and actual HTTP provider order/rename/child fixtures exercise the changed seam. |
| Owned context-window plugin | All seven plugin files checked. Initial window and reset checkpoint stop labeling runtime session ID as Agent name; unused argument is removed at all callers. Window IDs, Notes/History isolation, archived recovery and native session identity remain. Real native engine tests cover initial/reset serialized absence. No node_modules patch, private runtime import or DSH kernel change. |
| Object-scoped Task failure and native-visible deduplication | Failed PA preparation returns only local pending input/conversation references and applies SingleThread scope filtering; revoked refs stay excluded. Task driver retains hard Task-tool/source/automatic-step gates and emits no D9 without known active Task or pending-input objects. Limitation text contains deterministic sorted references without per-step time noise. Dedup scans native visible surface and treats later Task facts or successful Task tools as boundaries, so runtime object restart alone is not a new fact. Native tests cover no-object actual tool rejection, scoped pending inputs, repeated request/restart dedup, current-task outage and recovery consumption; no arbitrary title/body is delivered while authority is unknown. |
| One-page Memory provenance/content | Dynamic document context identifies fixed Agent-owned directory and complete MEMORY.md path, uses explicit memory_content boundaries, retains role/source eligibility/current-correction/read-only/Dreaming-only writer rules and removes routine backup/missing-foreground-tool prose. Invalid entries stay invalid rather than copying old bytes. Explicit legacy import still discovers registered backups through its existing manifest. Shared Skill and Dreaming instructions now describe useful key memory rather than only an index. HTTP window/summary and same-child memory fixtures are updated at their existing seams. |
| Dreaming frontend/backend separation | start no longer checks the parent's read/write/edit/memory_maintenance selection. Shared feature dependencies, Node capability projection, Node validation and native configuration validation consistently remove obsolete foreground dependency exceptions. Automatic toggle does not add foreground tools. Unchanged runDreamingAgent creates its own empty-seed maintenance scope with explicit tools, generation checks, read-before-write and staging-path restrictions; feature disable/hold/mode/timing/budget/lifecycle remain. Real native automatic Dreaming fixture verifies foreground lacks write/edit/maintenance while background writes staged pages and emits actual saved receipt. |

### Reused execution evidence and limits

- `/tmp/refactor679-followup-focus.log`: 9 files/51 tests passed plus one then-failing automatic Dreaming fixture. The failure was its default unrelated Feature dependencies, not declared successful behavior. Corrected fixture explicitly disables unrelated features and `/tmp/refactor679-dreaming-green.log` passes all 6 Dreaming cases.
- `/tmp/refactor679-plugin-test.log`: 9 files/32 plugin tests passed; plugin typecheck also passed. This proves native window/history behavior under controlled tests, not a published artifact or live model.
- `/tmp/refactor679-followup-typecheck.log`: all workspace typechecks pass. The older broad build log retains its title-union compile error; the current guarded source and subsequent `/tmp/refactor679-followup-node-build.log` supersede that Node error. Final complete build/lock evidence remains with caller.
- Actual serialized provider fixture tests prove delivery and deterministic tool consumption. Independent Global/PA natural first-request complete System/messages/tools and real replies are still required by the appended design. They are not replaced with a static prompt preview or controlled provider choice.

**Code delta conclusion: `[]`; final verification remains pending final portable plugin lock/artifact, gate results and independent Global/PA actual initial-context acceptance.** Later dependency-only immutable-release replacement requires only package/lock/artifact identity check, not a new full review. A material source repair should be checked only as its relevant delta.


## User-acceptance follow-up — final bounded closure at 326dac00e

This latest section supersedes the pending status of the preceding follow-up round. **Code review: `[]`; delta verifier: PASS; affected corrected-delta: aligned. V-FOLLOWUP-1 closed.** Base `5e5d3fcc801c6ad766910b126a10ee25076627a9` → final implementation `326dac00ed5d78daaa6464032a94a24daba5d794`; branch `codex/refactor-679-context-followup`.

The closure checked only the final release URL/lock and package identity, the final frontend Dreaming fixture correction, the affected canonical delta blocks and handed-over evidence. The previously reviewed identity/Task/Memory/Dreaming business source is retained; no full rereview, whole test run or model task was repeated.

- **Plugin artifact/source:** final tag v0.3.0-rc.7 resolves to `00f61960a6a81078cb9102347a277aa9147fe30b`. Its complete `fa2b47d..tag` diff SHA-256 is `668ecd5e7d8563bd97f9a484833a3fefa35bea2598a91c894fedf08c56f85aca`, exactly the prior audited seven-file working diff. The locally preserved anonymously downloaded release package is byte-for-byte equal to the tested tarball, SHA-256 `e3409381a9cd77546093dcd5cd133021347d6cc650c8bddfdb20a555442848c2`; recomputed SHA-512 equals pnpm-lock integrity. Final dependency/lock use the fixed [v0.3.0-rc.7 release tarball](https://github.com/Mrchen116/dsh-agent-context/releases/download/v0.3.0-rc.7/dsh-agent-context-0.3.0-rc.7.tgz), with no /tmp tarball reference. Packed checkpoint bytes match the tested plugin build and omit the misleading Agent-name row. Frozen-lock installation and final complete build passed.
- **Frontend fixture delta:** the unchanged save behavior now receives the real Dreaming contract `requires.tools=[]`, with independently configured foreground tool selection and catalog. This repairs the obsolete test premise; it adds no product code, skip or weakened save assertion. Final affected page: 28/28 passed. The earlier full Web run remains recorded as 107 files/1,030 passed plus this one then-failing old fixture. Remote CI must still run the final complete tree; no remote-CI success is claimed here.
- **Actual Context and behavior:** independent [acceptance Round followup-1](acceptance.md#round-followup-12026-10-31用户初始上下文修复-delta) is PASS. The verifier checked the preserved Global/PA first-request artifact hashes and key source/role boundaries, actual sent/completed native events and later PA valid-memory snapshot. Global has 4 messages/23 tools, PA 4 messages/38 tools, correct display names/IDs, no unscoped Task failure or routine backup/missing-tool noise. PA's first request legitimately has entry_basis_stale and no valid memory body; only later after actual Dreaming receipts is the fully sourced one-page body supplied. This distinction remains explicit. The independent reviewer read the complete inputs and tool schemas; no keyword summary substitutes for that review.
- **Evidence boundary:** this follow-up's complete inputs are native request/header/context and persisted model surface associated with real tool calls and sent receipts. They are not final upstream HTTP-wire captures. Prior controlled raw HTTP fixtures remain separate retained mechanism evidence. Automatic Dreaming with missing frontend maintenance/write tools is proved by the native runtime regression, not by the live PA journey where maintenance was selected.

The local final source passes 181 native files/953 tests, workspace typecheck, final release-installed build, Python 127 non-e2e tests (28 deselected), shared iOS runtime, ruff and docs-check 294 sources/68 routes; exact commands/logs remain in [M1 evidence](M1-context-flow/evidence.md). No open confirmed/plausible finding remains. New and old isolated previews remain caller-managed and retained for user viewing, not abandoned production processes.

The three appended Requirement blocks in the two Gateway active deltas exactly match their canonical copies; index counts are 58 capability and 23 Task Requirements. No additional design/spec semantic change is required. Retain this scoped code/Context/verifier result through whole-unit archive, relative-link/index migration and the resulting docs-check. Remote CI, final PR, Memory merge and lifecycle cleanup remain separate caller delivery steps. Reviewer stops writing reports after this closure.


## Consumer interface and continuous-memory delta — Round 9 (2026-10-31)

Latest independent round; earlier full and follow-up results are retained only for unaffected behavior. Mode: **change-code-review delta + Agent Context Implementation Review**. Initial range Memory `2724ea8d1d455c40fcc9f7798154a93b2aa6a0b5` → `81bff879b4ac723e2b40fccc43bf52bce31e5065`; one confirmed bootstrap defect then received bounded closure at **`0718cbd3b881bf0262373e1ee502abe2173461c3`**. Branch `codex/refactor-679-context-followup`; checkout/source freeze and clean source state were checked. Only code-review.md and verification.md were written; no model, preview, production, source/test/design or service changes by reviewer.

### Current findings at 0718cbd3b

```json
[]
```

No surviving confirmed/plausible defect remains in the specified implementation and its small fix delta. This is the code conclusion; final real-model/default-tool/maintenance acceptance and broad evidence handoff are still pending under the separate verifier issue below.

### Confirmed finding and bounded repair

**R9-C1, P1, CONFIRMED at 81bff879b — `scripts/e2e_catalog.py:60`: bootstrap must send the real configuration API contract.** When a current default/fixed/Feature tool is missing, the original bootstrap PATCH sent only profile_version/tool_allowlist. The real HTTP parser requires display_name and group_reply_policy; omission returns 422 and prevents default/daily startup before ready. The reviewer independently imported the actual built public configuration parser under Node24: original payload returned `{status:422,message:"display_name is required"}`; complete configuration accepted. Caller independently reproduced the same real daily 422 (`/tmp/refactor679-consumer-bootstrap-422.log`). The old unit mock had accepted a payload the production contract rejects.

At 0718cbd3b the two-file repair sends the previously fetched complete current config plus the new allowlist, preserving unrelated role/prompt/model/selection fields. The regression now asserts display_name, group_reply_policy, custom_prompt and default_model preservation; error output retains bounded server details. 10 Python tests pass (`/tmp/refactor679-bootstrap-green.log`). The repaired same public startup reaches daily ready at port58220 (`/tmp/refactor679-consumer-up.log`), and the four-role capabilities/config audit has missing_defaults=[] for P/E/Q/PA. Fixed PA tools are correctly accounted for as selected∪host-fixed rather than forced into the stored allowlist. **R9-C1: closed; no full review repeated.** Final model tools are still the product reviewer's distinct observation seam.

### Context Implementation Review and retained boundaries

| Consumer / changed seam | Checked behavior and direct evidence |
|---|---|
| Working P2 versus independent approval | Working guidance now uses actual Inbox fields, newly received/restored/history semantics and public sending call results; private inbox_result/observation/result-wrapper terminology is removed only there. The separate reviewInboxSourceInstructions, ApprovalSources transcript and reviewer output protocols are unchanged. Sender, participant/observer, partial messages, historical scope, sent/held/unknown and internal accepted distinctions remain. Existing actual native/provider tests exercise the new work-consumer text; no reviewer-reliability claim is made. |
| Public write/edit assembly | Only known tool:write/tool:edit sections lose the explanatory fs-observation-policy name through public assembly. Prior-read/edit-first behavior and runtime enforcement are unchanged. read/glob/grep guidance stays. DSH jobs/bash behavior and loaded-but-allowlist-hidden jobs guidance are explicitly user-accepted out-of-scope cases, not an unconditional tool mismatch finding or remaining fix request. |
| Current formal memory for root/PA/child | MemoryDocuments.context reads current saved MEMORY.md irrespective of pending source checks, generation or checkpoint; length cap still gives a complete path to read. Dynamic context keeps fixed owner/path/content boundaries, current correction priority, only-Dreaming writing, actual save semantics and changed-detail paths. Ordinary source/message/new-chat/file changes no longer suppress the whole foreground entry. Updated unit/native same-child and real read/write-denial fixtures protect these observable changes. |
| Stop-use and backend publication | Explicit exclusion remains immediately visible with targeted constraints and original-child guidance; saved old bytes are data, not renewed permission. Foreground write protection remains. Existing full source synchronization, backend generation/permission checks, frozen plans, version conflicts and publication receipts are retained. New needsVerification preserves the backend pending/generation/version-basis check without relying on a foreground reason field. User-excluded observation/history-linking scope is not added back as a requirement. |
| Maintenance status / results | Frontend status/exclude projects source-check pending, explicit requests and path-level saved/version/commit/error facts; removes full source sets, generation, backupRoot and operation/hash fields. Dreaming status keeps active state, bounded pending counts, child consolidation states, blocked reasons and result/times; no owner streams/seen/rotation/integrated/retry cursor. Internal owner state remains in backend storage and is still used for scheduling/recovery. Incomplete Dreaming regression checks failed-progress invariants against persisted backend state rather than leaking it through the tool. |
| Test-default tools | Shared bootstrap derives defaults, fixed items, enabled-Feature tools and valid explicit extras from real product capability/config APIs; retired names are filtered. Default/daily call it before ready; explicit --main-config returns without reading or modifying it. PA creation keeps its host-fixed tool semantics. Repaired actual startup and four-role config audit cover API wiring; actual native request tool lists remain final product evidence. |

### Reused evidence and limits

`/tmp/refactor679-consumer-focused.log` is mixed (4 files/12 passing tests and a six-case then-failing Dreaming fixture); it is not a blanket green run. `/tmp/refactor679-consumer-regression.log` subsequently passes all 5 files/41 tests, including the corrected fixture and native memory/current-source/foreground-write protections. Three original current-memory red cases are retained in `/tmp/refactor679-consumer-red.log`. Bootstrap missing-function red and initial 10-pass mock do not supersede the actual 422; the repair and live ready evidence above do. Workspace typecheck and complete build logs pass. Final full native/Web/Python/docs and the independent new daily Global/PA complete input, returned maintenance status and real behavior are pending handoff; no historical task journey was rerun by reviewer.

**Code-review result `[]`; verifier pending V-CONSUMER-FINAL-1 only.** Existing sol/high configuration and previews were not changed by this reviewer. Only relevant fixes need further delta closure; do not reopen unrelated full-unit review.


## Round 9 — loaded nano-memory Skill targeted delta at 5fcb9b18a

**Mode: code-review delta + affected Context Implementation Review; no full rereview.** Validated HEAD `5fcb9b18a288e5b1c8007c27ce41448d50637c7e`; the commit changes only seven lines of the existing bundled nano-memory Skill. The earlier 0718cbd3b implementation/real-bootstrap closure remains retained. The product review's consumer-1 C1 identified this real loaded-Skill seam rather than a speculative wording concern.

```json
[]
```

No new surviving code/Context defect found in the seven-line diff. The Skill now points to the actual contextual memory directory and personal-assistant/independent-expert role rather than an unavailable memoryRoot/profile field. “Existing children” identifies the correction recipients without the misleading atomic-execution wording. Dreaming uses the same staging-copy concept expressed in ordinary language; it still alone writes formal memory through host application. Foreground write/edit/shell bypass remains prohibited, current corrections and stop-use remain immediate, request_ref/importLegacy selection and truthful saved-versus-version receipts remain. The obsolete foreground-checkpoint/backing warning is removed without adding a checkpoint tool or weakening host checks. Backlog language states the next-batch count boundary and avoids old per-step terminology. Explicit read/glob/grep guidance is unchanged; no jobs/plugin exception is reopened.

The supplied native consumer-1 seq27 proves the old Skill had actually loaded, so source inspection alone does not close the product finding. Caller managed-restarted only this round's Node, installed the new bundled Skill and compared bytes; independent actual reload/consumer behavior is still pending. **consumer-1 C1: implementation repaired; product closure pending.** V-CONSUMER-FINAL-1 remains open until that evidence is handed over.

Retained gate accounting: `/tmp/refactor679-consumer-full-tests.log` completes 181 native files/954 tests passed (345.86s); no native full-suite failure remains. Current 129 Python passed/28 deselected, build/typecheck, ruff, shared iOS runtime and docs295/68 remain applicable to unchanged code. This prose-only delta does not require rerunning full tests/models; actual Skill-load evidence is the effective remaining seam. The reviewer changed only these two reports and did not alter source, services, role models or previews.


## Round 9 — final consumer-2 evidence closure at 5fcb9b18a

**Latest code-review result: `[]`; final delta verifier: PASS; affected corrected-delta: aligned.** Validated source `5fcb9b18a288e5b1c8007c27ce41448d50637c7e`, base Memory `2724ea8d1d455c40fcc9f7798154a93b2aa6a0b5`. This section closes the preceding consumer evidence pending status; no whole-unit rereview, model run, test or preview mutation was performed.

Independent product acceptance consumer-2 is PASS at the same source, with consumer-1 C1 closed and zero unresolved findings. The reviewer corroborated the actual native reload artifact `output/refactor-679-consumer/pa-skill-reload-full.json` (SHA-256 `fd136993eb5400051b6edf50e7f37cae2fd96de8073e7be27343b4e8dada3300`): seq127 calls skill; seq128 contains the entire current bundled nano-memory body, with no memoryRoot/PA-specialist-profile/checkpoint/old per-step text; seq132/133 queries and returns the current status. That result has only mode/sourcesPending/exclusions/receipts and maintenance.active/backlog/reviews, active=false and pending next-batch units=8, with no private owner protocol/streams/seen/rotation/integrated/cursor/retry fields. Actual seq138 returns sent, message `2e7be5234a9740a0830bc759d0f003e1`; seq143 completes. This is actual newly loaded consumption, not merely a changed installed file. The old seq27 text remains historical and was not rewritten.

The independent complete-input/37-39-tool-schema and natural Global/PA journey review in consumer-1 remains retained: real default tools, file lookup, current memory on first/newer requests, actual Dreaming save/version receipts, sanitized status and immediate explicit stop-use all passed. Consumer-2's response correctly separates the immediate correction from formal memory not yet rewritten and next-batch count from total history; it did not run maintenance or modify files. The sole loaded-Skill issue is therefore closed by its actual replacement and subsequent behavior.

Local evidence is complete: 181 files/954 native tests, 129 Python passed/28 deselected, complete build/typecheck, shared iOS runtime, ruff and docs295/68 passed; source/logic checks and the small Skill review remain retained. Native request/header/context/surface observations and actual sent/model behavior are not upstream final HTTP-wire capture; historical controlled HTTP serialization evidence remains a separate class. User-approved read/glob/grep and constrained-jobs exceptions remain as specified, not open defects.

**V-CONSUMER-FINAL-1 closed; no remaining implementation or evidence issue in this bounded round.** Current canonical delta merge, whole-unit archive, relative-link/index correction and final docs-check may retain this code/Context/verifier result without another full review, provided they add no semantics. PR, remote CI, Memory merge and preview lifecycle remain caller delivery work; this local PASS does not claim those have occurred. Existing previews are intentionally retained for user viewing. Reviewer stops writing files after handing back this closure.


## CI confirmed-stop test wait — bounded review (2026-10-31)

**Review mode: test-only delta**, HEAD `0b7f7a6e13132cd8d733bc8c2af0d71d07b6ff63` plus the single dirty change in `packages/dsh-integration/tests/task-execution.test.ts`. No product/runtime/Context implementation changes. Prior implementation, product and verifier PASS conclusions remain retained; this review does not reopen them.

```json
[]
```

The revised wait preserves the declared stop-fence and notice-retention assertions at the observable boundary: the stopped session settles idle with no model call; releasing the fence stays quiet; the next actual human request's first provider invocation includes HOST_STOP_NOTICE; prior Schedule and queued human input remain present; the unconfirmed doing Task is absent. It removes the assumption that an injected notice must appear in at least two internal inbox insertion events. The required outcome is notification retention before the next model decision, whether the native queue kept or reinserted the notice. No later behavioral assertion was deleted, and no skip/retry or product fallback was introduced.

PR #436 CI run `41196290600` remains a real failed run: this assertion observed one insertion where the old test required at least two (953 other tests passed). The unchanged focused local reproduction passed in 4.07s. The exact CI scheduling/interleaving cause was not captured and is **not proven**; this test repair must not be described as a confirmed runtime batching fix. The replacement verifies observable settling/absence of premature calls and later actual notice consumption without asserting private batching counts.

Caller reran the owning `task-execution.test.ts` regression: **13/13 passed**, 17.93s, `/tmp/refactor679-ci-stop-regression.log`. Reviewer inspected the complete owning scenario and retained downstream assertions, did not run tests/models/services and changed only this report. Remote CI after the test repair is still a separate pending delivery check, not implied by the local regression. No new full review or verifier change is needed.


## Round 10 — child/fork/Dreaming/forgetting independent delta review (2026-11-01)

**Code review: PASS; current findings `[]`.** Review mode: delta plus finding closure; Agent Context mode: **Implementation Review** by this same independent reviewer. Executed base `8c9d34780d04ce9d43ed68950fde88abc6e26a6a`; validated source `fea88c1878f70d112364382236ecb5cb81a01a59` (including source-history fix `2b1582620`). Scope includes this round's working design/deltas, approved Round 10, and only the affected child/fork, Dreaming projection and forgetting chains. Earlier valid code/product results are retained for unchanged Task, approval, delivery, default tools and UI mechanisms; they are not claimed as new-round acceptance.

```json
[]
```

### Confirmed findings and bounded closure

| Finding | Concrete consumer failure / evidence | Final closure |
|---|---|---|
| R10-C1 — `knowledge/dreaming-history.ts:110`, source_history tool result | CONFIRMED/WARNING. System directory projection was clean, but actual tool output still returned the entire allowed_range, exposing root_session_id/baseline/through/cutoff host fields. Independent direct invocation of the registered production tool returned baseline=0/through=1 and raw cutoff; this confirms the interface defect without claiming observed model confusion. Expected only source identity, purpose and readable deadline; exposing the internal cursor contract burdens the consumer and violates the approved projection. | `2b1582620` projects exactly session_id/purpose/available_before while internal range/token/source guards remain. Permanent exact-key assertion: meaningful red then `/tmp/refactor679-history-range-green.log`, 3/3 passed. CLOSED. |
| R10-C2 — `agent-config.ts:148`, `global-mode.ts:39,103`, `capabilities.ts:68`, ordinary SingleThread child | CONFIRMED/WARNING. The shared SingleThread preset retained root public-delivery prose and combined product send schema even though the child had the new internal role. Actual assembled child regression reproduced the root-delivery sentence; ordinary-child requirement includes SingleThread. Expected native internal return/send behavior, not public target/text delivery or product conversations. This is a Context/tool-view mismatch, not a claimed guard escape. | `fea88c187` suppresses that section for ordinary children, hides conversations and locally projects native send_message to agent_id/message only; root preset remains intact. Actual assembly plus cold restore cover Global, PA and SingleThread; `/tmp/refactor679-final-patch-green.log` passes 10/10. Abandoned registration relocation is not final implementation. CLOSED. |
| R10-C3 — `knowledge/dreaming.ts:304`, consolidation input | CONFIRMED/WARNING. Task summary header still supplied root/events baseline–through/version after System cleanup; the actual maintenance messages regression failed on that header (`/tmp/refactor679-summary-fields-red.log`). These are host source bookkeeping, not evidence references the model needs. Expected usable source session identity and original qualified evidence; the obsolete header retained the forbidden maintenance contract. | `fea88c187` retains Source session_id and evidence text, removes root/range/version display, leaves frozen sourceVersion/hash/range verification internal. Owning 7-case Dreaming regression is included in the 10/10 final patch run. CLOSED. |

The executable recommendation for each was to fix its final consumer projection rather than weaken source checks or add another model instruction. All three have applicable permanent coverage and no surviving focus finding. No speculative edge-case or style finding is carried forward.

### Actual affected Context coverage

- Role selection uses public native session/descriptor data plus creation-local fork intent for an empty seed. Ordinary workers do not install the parent Persona, and their product identity explicitly marks an internal child. Global/PA/SingleThread assembly and cold-resume tests verify the tool/communication boundary. Forks retain parent Persona, feature sections and schemas, inherited Task history remains intact, and first-task tail guidance explains internal return and root-only actions. Existing host root guards continue to reject public delivery/representation and source/saved-task operations; visible schemas do not grant permission. Real GlobalAgent guard coverage in `/tmp/refactor679-child-rerun.log` is 2/2 passed.
- Controlled real HTTP serialization fixture verifies system/tools plus inherited completed-history prefixes for empty, seeded and restarted forks across Global/PA/SingleThread. The fixture's SSE is synthetic and is not cache-hit evidence. Separately, independently inspected actual daily wire bodies and responses in `output/refactor-679-child-live/`: Global root/ordinary/fork tools 37/33/37, PA 39/33/39; full fork System/tools equal their parents. Global wire 0015→0033 preserves the first 10 completed-prefix messages; PA 0039→0048 preserves the first 24. Actual response 0033 reports cache_read_input_tokens=15744 and response 0048 reports 19968. These observations demonstrate hits on this route/run, not a universal cache guarantee. Unchanged Global/PA prefix code retains this evidence across the final SingleThread/header-only fix.
- Forgetting removes the exclude action/arguments, persisted exclusions consumption and model injection, including legacy state loading. Current conversation corrections and original-child follow-ups replace the registry; Dreaming reads original qualified chat and preserves this-turn-only scope. Source permission filtering and personal_sources, foreground read-only documents, Dreaming-only formal writes, generation/frozen-plan/hash/version guards remain. Ordinary read/glob/grep guidance and previously accepted jobs behavior remain unchanged.
- Dreaming System, source_history output and consolidation messages now project only useful source identity/purpose/deadline and actual evidence/window/item references, not Run/cycle/generation/source baselines or summary versions. Qualified child material explicitly says it is not the complete execution transcript; omission counts describe additional capacity/provenance omissions.

### Evidence boundaries

Root's first full suite remains **181 passed files / 1 failed file, 956 passed / 1 failed tests**, `/tmp/refactor679-child-full-tests.log`; the failure was the newly collected source_history red assertion, subsequently closed by its exact 3/3 rerun. The first SingleThread patch run remains 14 passed/1 fixture failure (trajectory scope); final native-descendant recovery assertion fixes that fixture without weakening Global trajectory coverage. The final 10/10 owning regressions close the two additional defects. A fresh full run at fea88c187 is caller-owned and still pending here. Reviewer did not start models, services or tests, and only wrote this and the verifier report.

Code inspection/serialization/cache observations do not replace the independent real forgetting/this-turn exception/Dreaming-save journey or the latest header projection's actual model-input closure. Those remaining evidence requirements are recorded as V-CHILD-FINAL-1 in verification.md; they are not surviving code defects. No new design amendment is required. PR/CI/merge, canonical merge/archive and retained-preview lifecycle remain caller delivery work.


### Round 10 — durable-trajectory test-only closure at dfdfbd66b

**Bounded code review: `[]`; prior implementation/Context PASS retained.** Source is unchanged from fea88c187; `dfdfbd66b67a4912c00defad8ed0bf955b3100ac` changes only `dreaming-runtime.test.ts` warm/cold trajectory comparison. The failed frozen full run remains 181 passed files/1 failed, 958 passed tests/1 failed (`/tmp/refactor679-final-full-tests.log`). Its complete diff shows only live assistantStream.revision=20 versus cold=0 and absent delegationDepth versus persisted=0. The unchanged focused reproduction passed (1 passed/5 skipped, `/tmp/refactor679-auto-dreaming-repro.log`); that does not prove an exact scheduling cause.

The revised comparison is appropriate to the declared durable-view contract. Installed public DSH `SessionAssistantStreamBaseline` explicitly describes process-local state; its accumulator starts at revision=0. Nano's existing cold `trajectory.ts` follow projection supplies revision=0. Public session-query treats absent depth and 0 as equal; JSONL storage materializes delegationDepth=0. The test normalizes only those two representations. Spreads retain every other frame/header/assistantStream field, including activeAttempt, and the final deep equality still covers records, projections, cursor and the complete remaining response. The native descendant boundary and receipt/model evidence assertions remain. No product fix, retry, skip or weaker persisted-record subset was introduced. Owning Dreaming/trajectory/knowledge-review regression: 3 files/13 tests passed, `/tmp/refactor679-trajectory-green.log`. No new full regression/model/service was run by this reviewer. Final remote CI remains an explicit delivery gate.

Also independently parsed `output/refactor-679-child-live/source-history-runtime-results.json`: actual registered DSH tool results carry allowed_range only as session_id/purpose/available_before, preserving original evidence items. This is a real runtime/tool execution with an LLM fixture, not an actual provider choosing source_history; `/tmp/refactor679-sourcehistory-proof.log` is 1 passed/6 skipped. It strengthens R10-C1 closure without overstating model behavior.


### Round 10 — final evidence closure

**Final code/Agent Context result remains PASS, findings `[]`.** Actual implementation fea88c187, final HEAD dfdfbd66b is the reviewed test-only normalization. Independent product child-forget-2 is PASS with 0 open issues; CF1 is CLOSED. Reviewer read its final report and independently parsed actual wire0091: task-summary header contains only Source session_id, not root/events/version; useful evidence and stated limitations remain. Parsed subsequent wire0106 inherited tool results: latest completed maintenance integrated the new child summary, and both current receipt commits `755030c72e517d48973d1accbfa965d24d367883` / `8359886ef9ed573b0b86a5bf91ef5f510ccbe147` have saved=true/versionRecorded=true. Native seq233 confirms public sent receipt `14a13af9b7c340618330ab33f35c069c`. Real Chrome delivery review is supplied by the independent product reviewer, not a second UI trial by this static reviewer.

The earlier independently inspected natural forgetting seq158–185 and actual cache/provider checks remain applicable; source_history runtime fixture remains explicitly distinguished from autonomous real-model use. V-CHILD-FINAL-1 is now CLOSED in verification.md. No further source/design change or full rereview is required. Current canonical merge and 61-requirement index agree with this round's approved deltas. Caller may retain this conclusion through whole-unit archive and relative-link maintenance, followed by final docs-check; remote CI/PR/Memory merge and preview lifecycle are separate delivery gates. Reviewer stops writing both owned reports after this closure.


## PR #437 — context revalidation fixture race closure (2026-11-01)

**Bounded test-only code review: `[]`.** Reviewed HEAD `426cfe2e371fe5327b0fdecb4f1fafe6369fcff5` plus the sole working-tree patch to `packages/dsh-integration/tests/context-revalidation-provider.test.ts`. No product/runtime or model-visible implementation changes. Previous implementation/Agent Context/product PASS conclusions remain retained; no new full review is required.

The fixture previously set armed=true before session.submit, allowing session.ensure's asynchronous Task idle check to observe active responsibility and start an automatic turn before the human input. The original CI observed three requests where this controlled two-request scenario expected two; the captured turn order and the temporary submit delay reproduced that specific failure in `/tmp/refactor679-ci-context-race-red.log`. The temporary scheduling manipulation is absent from the final patch.

The patch arms fixture Task responsibility only when real product.task_context.prepare reads its pending originals during preparation of the submitted turn. Until then the snapshot remains quiescent. This aligns fixture activation with the scenario's intended human-triggered turn without changing production scheduling or hiding requests. It preserves exact request counts (two initial, one after native window reset/summary), all per-request System/Memory/Skill/Task/tool assertions, real tool result checks, source identity/consumption commit evidence and prepare/snapshot call checks. The added assertion that the first provider request includes HUMAN_before explicitly protects the intended first-request boundary rather than merely making a count pass. No assertion was removed, timeout extended, request filtered, retry or skip introduced.

Caller evidence: owning two cells **2/2 passed**, `/tmp/refactor679-ci-context-green.log`; combined context-revalidation plus three-mode fork HTTP regression **2 files/5 tests passed**, `/tmp/refactor679-ci-context-and-fork.log` (9.25s). Reviewer read the complete fixture and relevant production prepare/snapshot chain, started no service/model/test and changed only owned reports. PR #437's first remote run remains a real **958 passed/1 failed** run; final complete remote CI must still pass before merge into unit/feat-676. This repair does not claim a production scheduling defect was fixed.
