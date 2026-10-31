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
- **Evidence:** [native pre-step](<../../../../packages/dsh-integration/src/task-context.ts#L21-L25>), [product synchronization](<../../../../packages/personal-assistant/src/task-context.ts#L30-L71>), [witness A](<review-witnesses.md#L10>), [architecture availability](<../../../../SPEC.md#L22>), [approved synchronization/degradation design](<design.md#L157-L191>).

### C2: Alternate unread projection survives terminal Task revocation

- **Surface:** frozen Inbox cursor → new tool result → next native model input.
- **Expected:** every not-yet-consumed projection of a withdrawn Task is retracted, including pending cached read fragments; already-consumed canonical history remains intact.
- **Observed:** `revokeSystemContext` leaves frozen snapshots; a fresh cursor read first exposes the Task after revocation.
- **Impact:** withdrawn Task facts reenter an actionable unread tool surface after their direct/native route was correctly revoked. This witness does not claim exposure of otherwise-private source data or prove model behavior.
- **Recommendation:** terminalize/filter affected pending fragments in all snapshots and saved-but-unconsumed read projections; add the exact multi-page/public-read regression and verify direct-consumption deduplication too.
- **Severity:** CRITICAL / P1 (Task revocation boundary).
- **Evidence:** [revocation](<../../../../packages/personal-assistant/src/inbox.ts#L233-L235>), [frozen cursor path](<../../../../packages/personal-assistant/src/inbox.ts#L293-L317>), [Global call](<../../../../packages/personal-assistant/src/global-agent.ts#L460-L473>), [witness B](<review-witnesses.md#L56>), [active revocation scenario](<specs/im/task-graphs.md#L37-L41>).

### C3: Original task notice lacks business facts that the replacement path requires

- **Surface:** transactionally persisted task system message, shared by humans and direct Agent context.
- **Expected:** old/new responsibility roles and both relation endpoints/business direction are self-locatable in the one original business message; no private replacement snapshot is needed.
- **Observed:** generic relation labels plus one task reference, or generic reassignment plus unlabelled mentions.
- **Impact:** the receiver cannot determine which dependency/parent/replacement changed or who handed responsibility to whom without reconstructing absent historical facts.
- **Recommendation:** preserve one original message but encode the missing endpoints and explicit old→new responsibility roles; test visible text and structured references, including deletion/old-parent cases. Do not weaken the active delta to match the omission.
- **Severity:** WARNING / P2.
- **Evidence:** [assignment wording](<../../../../apps/im-server/src/task-notifications.ts#L21>), [relationship wording](<../../../../apps/im-server/src/task-notifications.ts#L32-L39>), [one-node metadata](<../../../../apps/im-server/src/task-notifications.ts#L48-L52>), [approved business-message contract](<design.md#L126-L140>), [active IM delta](<specs/im/task-graphs.md#L11-L24>).

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
