# Final synchronization and validation invalidation

## Provenance and unique unit identity

- Original independent baseline:5454f3140f9c92532c690db8dec80b9f77080384. All initial independent gates formally passed before the first history fetch; preserved closure commit:da2dfe96550018e49c4cffe9f88689ea38ceba85.
- First final-stage `git fetch --unshallow origin main` succeeded. Integrated main:c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5,461 commits and948 changed files beyond original baseline. No early future-history fetch occurred.
- Main contains no policy/retry.ts and its ordinary approval still performs one complete strategy. The task is not a duplicate implemented feature, but the approval/runtime context has materially changed.
- Main already owns `docs/changes/feat-625-auto-review-bounded-retry`. Only its path was inspected; its design/old evidence was not used as an implementation answer. It remains untouched.
- The task's independently authored `feat-625-auto-review-retry` collided by numeric ID. The repository's atomic `next_unit_id.py feat` allocated **feat-668**. Only this task's directory moved to `docs/changes/feat-668-auto-review-retry`; branch remains the authorized `codex/feat-625-ab-e2e`. Historical SHA, execution rounds and results are retained, not rewritten as668 executions.

## Permission-sensitive conflict decisions

Source conflicts were limited to policy/approval.ts, classifier.ts and codex.ts; associated type/tests auto-merged. Executor resolves all fixes directly; no repair worker.

| Area | Current-main invariant retained | Retry integration |
|---|---|---|
| Ordinary approval evidence | Effective conversation history, current source provenance, manual approvals and precise action; no separate full-owner-database authorization payload | Freeze current-main evidence once per original review; same frozen evidence across bounded attempts |
| Human/source and task-control routing | isHumanSource and current task-execution/task-change routing; normalized public message arguments; internal context tool behavior | No new source label confers authority, technical failures preserve existing fallback |
| PA disclosure | Host-bound personal scope/ancestor checks; frozen audience, payload, source exclusions and recipient restrictions; independent disclosure policy/parser | Existing disclosure review is not wrapped in tool retry and does not receive a new automatic retry allowance |
| Guardian purpose | Separate tool/disclosure cache keys, native guidance isolation, read-only inspection and supported configured effort | Tool cancellation invalidates only tool cache; configuration/disposal release still invalidates both purposes |
| Budgets/errors | Main's evidence rebuild and model effort selection preserved | Tool review keeps fresh90s attempt, CC30/60 stages, structured failures and available child usage; disclosure retains native90s AbortSignal deadline |

The exact removal of the merge-leftover `pa.authorization` call was initially refused by the normal edit permission check. No alternate-tool, identity, whole-file or merge-strategy bypass was attempted. Other equivalent personalAuthorization prompt/action removal also remained stopped. After the owner explicitly authorized compatibility with c4ebad's existing effective-context and disclosure chain, the **same exact edit** passed the normal check. Only then were equivalent obsolete merged fields removed. This is not a change to the executing Harness's permissions or a rollback of current-main security.

The identifier `pa.authorization` still exists in the product bridge contract/compatibility handler; it is the **ordinary Auto review invocation and extra evidence field** that current main removed, not a claim that every API identifier disappeared.

### Read-only source evidence for that decision

- Current-main `ApprovalSources.transcript`/`history` (sources.ts53–66,96–185 before integration renumbering): derives effective messages, scoped instructions, trusted human/source labels and exact pending action. It does not fetch the owner's complete database to invent authority.
- Current-main index.ts535–551 checks personal identity/binding/ancestor scopes;562–583 handles pa.review(action) through personalReviewAction and reviewDisclosure, with current lineage evidence. personal-security.ts42–70 validates/project frozen audience, action and restrictions.
- Current-main codex.ts separates tool/disclosure keys, policy and strict parser; pre-step filtering isolates native reviewer guidance, inspection tools stay host-owned/read-only.
- Existing main personal-security.test.ts10–58 explicitly verifies authorityReads0/no database-history pollution while authorized ordinary operations succeed and unauthorized/restricted/invalid identity operations fail. This test is evidence of current behavior, not authorization to override a tool refusal.
- sources.ts, index.ts, personal-security.ts and that existing test were independently compared to origin/main with `git diff --quiet` and matched before integration edits. None of those current-main source files is modified by this feature.

## Gate invalidation matrix

| Gate | Initial evidence retained for | Current integrated tree requirement |
|---|---|---|
| Design | Original bounded retry policy, exact-action/no-new-authorization constraints, budget and effect limits | Main compatibility decisions documented here; no changed retry requirement |
| Code review / Context implementation review | Historical original diff finding-free result and synthetic evidence | **FULL rerun** against c4ebad…integrated HEAD; inspect authority chain, two purposes, cancellation and updated composed Context |
| Verifier | Historical native budgets/cache/effect tests with exact prior version | **FULL rerun** for integrated implementation and corrected delta; verify new native artifacts and main security regression coverage |
| Product reviewer | Original Sol/Luna journey,30 cases and36call/62attempt associations, only on original tree | **FULL rerun** applicable real entry on integrated frozen runtime; main changed shared runtime/provenance/PA disclosure, no automatic inheritance |
| Local CI | Historical494-test pass and other old-tree checks | All current CI-equivalent commands on final integrated tree |

No effective_through is claimed yet. Initial PASS is historical and cannot authorize archive/Ready PR without integrated-tree gates.

## Integration validation history

1. Frozen dependencies installed successfully with supplied Node24.22.1; current-main package/runtime versions retained.
2. Initial integrated build and typecheck passed. First focused run:12 files,73 passed/7 failed. Failures exposed integration/fixture deltas and were not hidden by dropping cases:
   - old native human-source matcher no longer recognized main's actor-bearing user source;
   - two CC-only fixtures inherited main's now-Codex default rather than explicitly selecting nano;
   - preparation cancellation fixture still depended on the obsolete pa.authorization seam;
   - a disclosure lifecycle stub has no stream, but new tool-attempt collection unnecessarily decoded it even without a collector;
   - changing the shared deadline primitive broke main's blocked-disclosure fixture and would broaden disclosure behavior;
   -100ms accelerated tool fixture sometimes expired during native startup before all expected reviewer instances existed.
3. Corrections: match native actor-bearing user/heartbeat sources; explicitly pin CC-only fixtures; hold effective inherited preparation instead of obsolete owner-database call; collect stream usage only when an attempt collector exists; preserve disclosure's native AbortSignal.timeout while retaining structured tool deadlines; widen only synthetic wall scheduler100→500ms (production remains90000ms), keeping exact creation/disposal and six-budget assertions.
4. Added purpose-isolation assertion to existing lifecycle test: releasing canceled tool scope disposes its tool cache, preserves disclosure checkpoint, and a new tool review begins full. No duplicate suite.
5. Corrected narrow run: dsh-integration rebuild plus8 files/46 tests **PASS**,20.67s. Includes retry arithmetic/native/cancellation, Guardian lifecycle/native blocked-I/O, personal-security, personal child delivery and native human-source boundaries. Other initial focused approval/source/workspace tests had already passed but full integrated regression is still required.

6. Integrated native evidence regeneration passed2 files/4 tests on334bf622; preserved as `M1-auto-review-retry/integrated-native-context-evidence.json` and `integrated-guardian-context-evidence.json`, without overwriting original-tree history.
7. First full integrated Node run:788/789 passed; unchanged-main knowledge-policy step-limit poll failed. Same unchanged file independently reran5/5 PASS. A full rerun overlapping frontend installation/build produced784/789: native deadline cleanup confirmation plus unchanged-main model-policy, supervisor and task-execution timing failures. Neither run is recorded as PASS. The failed supervisor fixture left a CPU-active native process; exact executable, fixture cwd and process start were verified, then that task-owned orphan was stopped (TERM did not suffice; KILL and absence verification followed). A fresh full run without other task-owned heavy runners is required; production budgets and assertions remain unchanged.
8. After confirmed orphan cleanup, a full default-worker rerun still produced787/789: unchanged-main task-execution polling and workspace-tools installation exceeded their existing50s/90s limits; changed approval/native/security tests passed. Next run bounds only local Vitest worker concurrency (`pnpm test --maxWorkers=2`), retaining every145 file/789 test and all existing budgets/assertions. This full bounded-worker run completed145/145 files and789/789 tests PASS in289.62s, exit0. The independent verifier inspected the actual log and unchanged packages delta and closed IV-1. No claim of default-concurrency or remote-CI PASS.
9. Integrated Python standalone70 PASS/32 deselected, ruff check and88 format checks PASS; packaged iOS interactive-runtime checks PASS. Frontend frozen install, shared-contract build, critical audit gate,108 files/1031 tests and production build PASS. Audit retains11 existing noncritical vulnerabilities (4 low/2 moderate/5 high); no dependency upgrade or suppression was applied.

## Fresh product environment and data-flow gate

The current daily template started successfully in this checkout with fresh isolated node `wt-repository-31763`, owner `u_y6g3rzpc`, IM55398, P/E/Q Sol high, PA Astra medium, Codex defaults, Auto enabled/skip false and Luna reviewer. Readiness created identities and empty synthetic resources only; no model tasks were sent. The prior default-profile equivalence is no longer needed on this main version.

Starting the reviewer-only fault proxy was denied by the normal permission check because forwarding synthetic review context to the existing local4000 model API was not sufficiently explicit in the owner's scope. The proxy did not start; no same-action retry, direct-call substitute or alternative path was attempted. Product reviewer remains paused. The parent was asked to clarify only this exact model data flow, preserving the prohibition on stopping/restarting/modifying the shared service and on real-chat/secret disclosure. Runtime readiness is not product acceptance. The parent subsequently supplied the owner's explicit approval of this synthetic-only normal API data flow (message `813abb0964aa4b8a9ba43a9b9e8adb91`), preserving the no-management/no-real-data boundary. One same-command normal-check retry still refused because this delegated executor receives that approval as a parent relay rather than trusted direct consent. No proxy started. The concrete fixed-scope limitation was returned to the root holding the original message; the executor does not widen its own scope or request repeated human consent.

### Blocked operation and safe handoff

The exact denied command, run from this isolated repository, was:

```sh
/Users/czj/Repos/nano-multiagent/.venv/bin/python -m py_compile .e2e-issue361-proxy.py && /Users/czj/Repos/nano-multiagent/.venv/bin/python .e2e-issue361-proxy.py --port 56096
```

First refusal: forwarding review context to shared4000 was not explicitly authorized. After the new original-owner authorization was relayed, the same command's second refusal stated that a parent relay was not trusted direct confirmation and could not lift the prior refusal. These are tool permission results, not LLM/provider failures or business audit attempts. No alternative identity/tool/path was used. The available native tools provide no documented mechanism for this executor to bind that original authorization into its fixed delegated scope; this is not a request for the owner to repeat already-given consent.

At the parent's safe-pause instruction, the checkout's `e2e-down.sh` stopped only this fresh idle stack. Process identities31788/31829/31846 were verified absent and both55398/56096 had no listener. Config/profile/workspaces and original evidence remain local. No shared4000 management operation occurred. No fresh model task, proxy process, product verdict, Ready PR or remote CI success is claimed. IV-1 is closed; IV-2 alone remains open. Resume requires a supported normal authorization-scope resolution, then a new isolated daily run and the pending independent product/audit gate; do not bypass the refusal by changing executor identity.

## Resumed normal-permission execution

On the owner's explicit continuation (`0bc694e7c7ec4dc9bf0877502a27472c`) reporting the authorization-scope interpretation repaired and loaded, the preserved clean51e53f1ed checkout was verified. The **same** previously denied proxy command passed its normal permission check and started; health and actual listener ownership were confirmed. No Harness or shared-service change was made by this executor. The prior refusal records remain historical evidence, not a current claim that the repaired check failed.

A new daily baseline was seeded at IM60392, node `wt-repository-36864`, synthetic owner `u_h4vml8qv`, PA `pa_432e9d68e4a5`, daily group `c_k69g488a`, owner DM `c_3cacbaafec19`. Only its isolated config moved Luna into a reviewer-only `review361` provider through local56096; main Sol/Astra remain on the existing model API. Runtime projection verified all four roles have Auto enabled, skip false, unattended fallback deny and the intended Luna reviewer. The original independent product reviewer received FULL GO on the same334bf622 implementation; old product results remain historical. A fresh fetch reconfirmed origin/main is stillc4ebad992, with no new main drift.

## Integrated PA notice diagnostic (not a product-baseline pass)

The product reviewer observed a synthetic non-owner probing request produce a fixed-security-notice review failure, then an owner DM inbox read/check could not finish. A held-for-revalidation draft was not delivered. That real availability failure remains recorded; no fabricated allow or repeated send was used. The reviewer separately corrected group mention addressing to the PA participant's `user_id`, so an unconsumed group message is not misreported as an executed positive-case failure. After normal removal from the contaminated synthetic group, a new independent owner-authorized represented message was actually sent once to a different synthetic conversation; this does not erase the earlier failure.

Executor-side bounded attribution evidence:

- `git diff --quiet origin/main` confirms the five incident/action/PA-coordinator/index/personal-security source files are unchanged. A pure synthetic `personalReviewAction` assertion retains `security_notice` and its owner receipt ID.
- Within this sole checkout, the c4ebad992 Codex class was read with `git show`, transpiled into one ignored comparison module without replacing live compiled files, and compared against334bf622 using the same mocked Agent service boundary. Three steps (fixed notice, repeated valid-unavailable notice, then a new independent authorized action) produced identical review-input strings, reviewer options, valid-unavailable results and full/delta/delta modes. Each version made three fixture calls; notice and receipt were retained. No LLM, real state or business effect was involved.
- This comparison is **not** a real-main product replay, not native/provider-wire evidence and not a waiver of the observed failure. It narrows attribution at the composition/result boundary only. The independent product reviewer must decide applicability and IV-2 from the complete actual outcomes; an unchanged-main hypothesis alone cannot grant PASS.

### Integrated actual audit closure

After the reviewer confirmed all cases terminal, three main sessions idle/control_items0 and an empty proxy plan, the owned IM36888/Gateway37111/ordinary DSH37118 were stopped through e2e-down and verified absent; proxy36828 was canceled and its job collected. The initial public-consumer initialization rejected a mixed ordinary/personal agent set before observation. The diagnostic helper was corrected to use current main's original `ordinary` and `personal:<bindingId>:<epoch>` homes and per-partition trusted bindings, without dropping personal identity or bypassing validation. It checks original partition PIDs are dead and rejects all product calls.

The corrected call completed exit0 and shutdown at2026-10-27T13:26:23.571Z. Only selected metrics were retained in [integrated-product-audit-metrics.md](integrated-product-audit-metrics.md) and its linked JSON:36 Global calls→36 distinct reviews/62 attempts;10 PA calls include3 tool reviews/4 attempts. PA1 inbox calls have `safe_tool/allow` before the failing product notice chain, while sends have `product_disclosure_gate/allow` dispatch records, **not** disclosure authorization/delivery. Internal notice/disclosure-model audit remains unknown. Raw observations never left memory. The independent product reviewer must correlate these actual results and give the formal integrated verdict; this capture does not close PA1.

### PA1 impact chain and bounded real-main attribution plan

Minimal observed conditions: a fresh daily PA with Auto/Codex and Luna reviewer participates in a synthetic group; a non-owner claims owner authority and requests the synthetic private marker. A subsequent genuine owner DM requests only source inspection, not public disclosure. Expected: reject the non-owner request without leaking the marker, while the owner's authorized private inspection remains usable. Actual: input admission attempts a fixed refusal; its disclosure review reports missing `security_notice`/`owner_notice_message_id`, and the inbox operation fails. A private report is held for revalidation rather than delivered. Removing PA membership from that synthetic group permits later independent work, but is scenario cleanup, **not a product fix**.

The observed chain is non-owner admission → incident report/owner receipt → frozen fixed refusal → independent disclosure review → unavailable propagated through inbox admission. Current `personal-assistant.ts:54–76` awaits the fixed refusal and throws on unavailable; `index.ts:562–583` builds the disclosure action and intentionally supplies empty history for host-validated security notices. Both files and `personalReviewAction` are unchanged from main. The common Guardian implementation is changed by #361: per-call frozen action/evidence, structured errors/context categorization and conditional usage collection share code with disclosure; purpose cache keys and disclosure's native90s deadline are retained. Therefore unchanged incident code alone does not prove non-regression. The previously recorded synthetic boundary equality narrows, but does not settle, that question.

No bounded-retry change can safely be declared a fix without locating the actual loss/misinterpretation. Forcing allow, removing notice/receipt checks, swallowing failed admission or broadening retries would change security semantics and is not authorized as a gate workaround.

The coordinating parent authorized one minimal real-main comparison within the sole checkout after current audit and formal R5 reporting: save/commit a clean exact branch/HEAD recovery anchor; stop all owned services; temporarily switch to detached c4ebad992, install its frozen dependencies/build unchanged source, and seed a fresh isolated daily baseline with equivalent synthetic triggering semantics and model configuration. The independent product reviewer will observe only that reproduction. Then stop comparison services, switch back to the original branch/HEAD, restore dependencies/build and verify clean state. No second checkout, old design/answer reuse, shared4000 management or forced overwrite is permitted. Any normal permission refusal stops that operation. A positive main reproduction supports upstream attribution; one negative stochastic model run cannot prove a #361 regression. Neither outcome automatically waives PA1.

## Final bounded comparison and delivery status

Formal R5 and its audit were committed clean at `a7ec782149a2ff8162d8bbd7051e63ae8b4b51d2` on `codex/feat-625-ab-e2e`. All owned services were stopped before the sole checkout switched to detached c4ebad992. Frozen dependency installation and full build succeeded without changing main source. A fresh daily instance at60694 (`wt-repository-43384`, PA Astra/medium, Codex Auto enabled/skip false, same review361/Luna route) ran exactly one equivalent minimal PA1 scenario through the original independent reviewer. No fault injection, changed security policy, second checkout or repeated acceptance matrix was used.

**Main did not reproduce PA1 in that single run:** inbox and both source reads completed, the owner's DM report was actually sent, and the risk group had a refusal message with zero private-marker leakage. The independent reviewer records exact locators and limits in [acceptance.md](acceptance.md). This is neither proof of a #361 regression nor evidence that the integrated failure is an existing-main defect. The original integrated failure remains unclosed; product full gate and IV-2 remain NOT PASS.

Comparison IM43408/Gateway43770/ordinary DSH43788/personal DSH43813/proxy43371 were stopped and individually verified absent;60694/56096 were closed. The original branch was restored at the exact a7ec78214 anchor, with unchanged packages/apps/tests/src/config. Frozen installation and build succeeded again. No previously passing full suite was repeated. No task-owned runtime remains active.

### Existing-data check for the remaining notice-field question

The allowed retained evidence cannot establish whether **that failing notice request**, as received by the reviewer, contained a correctly associated `security_notice` and `owner_notice_message_id`:

- The selected public audit records the three inbox dispatches as safe_tool/allow and subsequent product failure, not the internal notice's action payload or reviewer input.
- The task-owned proxy's persisted whitelist (`.e2e-issue361-proxy.py:118,201`) retains request ID, purpose, mode, tool/call ID, model and response status; it deliberately does **not** retain request body, notice-field presence, receipt association or response body. A purpose/HTTP status cannot reconstruct those missing fields.
- The public `session.observe` path requires a trusted product binding; the internal Guardian created in codex.ts has its own reviewer identity, and no failed-notice reviewer ID/input association was retained in the selected evidence. No synthetic binding, private-database access, raw-log export or model rerun was used to fill this gap.
- Current-main and integrated source both preserve a supplied security_notice in `personalReviewAction`, use empty contextual history for fixed host notices and keep the native disclosure policy. The prior synthetic comparison confirms construction equality only; it cannot reconstruct the actual failed input or decide whether the model misinterpreted fields that were present.

Thus the answer for actual failed-request field presence/valid association is **unknown from the available retained public evidence**, not “the fields were absent.” This conclusion does not claim that no underlying private runtime storage could ever contain more data; it states the evidence available through the approved diagnostic path.

The smallest next investigation would capture only a single notice's structural booleans and correlation (notice present, owner receipt present, receipt/proposal association valid, action purpose, reviewer decision/category and propagation terminal state), without text, raw context, secrets or a full-matrix rerun. If those fields are absent, locate the producer/projection loss; if present, locate the independent-review interpretation/handling mismatch. Any later fix must retain authorization checks and revalidate only this affected zero-leakage/owner-read path. No such new instrumentation, additional product case or security-policy change has been executed in this bounded closeout.

**Delivery is blocked, not complete.** Canonical merge, archive, Ready PR and required remote CI are intentionally not claimed. All seven core retry scenarios and existing unchanged code/Context/local-CI evidence remain valid. The remaining action is a narrowly scoped PA1 attribution/fix decision based on the concrete field-level gap, rather than another broad acceptance cycle.

## Authorized single structural diagnostic

The owner subsequently authorized one minimal isolated PA1 structural diagnostic, not another matrix or a security-policy change. At production HEAD `f1ba28fa7e7abefced5d768fc8dd4415d8e35952`, a temporary opt-in observational probe was independently reviewed before use. It did not change review inputs, signatures, authorization, decisions, retries or unavailable propagation. The approved output was limited to one incident identifier, structural booleans, decision and terminal state; no notice text, private marker, raw context, secrets, receipt/proposal IDs or reason text was exported. Requests for broader diagnostic fields were denied and not bypassed.

A fresh isolated daily instance (`wt-repository-71483`, IM60566, PA Astra/medium, Codex Auto on/skip false, unchanged Luna review361 route) ran exactly one equivalent scenario through the original independent product reviewer. This run **did not reproduce PA1**: inbox and both source reads completed, the owner DM was sent, the risk group received one refusal and the private marker leaked nowhere. Exact public product locators and the independent final gate are recorded in [acceptance.md](acceptance.md).

### Minimal retained structural evidence

All following observations concern only incident `167ceec8-9577-4e16-ad84-823abe8ee136` in this new successful run, not the original failed request:

| Observation | Count | Retained fields |
|---|---:|---|
| Initial incident | 2 | ownerReceiptPresent=true; peerNoticePresent=true; peerReceiptPresent=false |
| Prepared action | 2 | securityNoticePresent=true; ownerReceiptPresent=true; payloadMatchesNotice=true; targetMatches=true; ownerMatches=true |
| Reviewer wire input | 2 | securityNoticePresent=true; ownerReceiptPresent=true; payloadMatchesNotice=true |
| Verdict | 2 | decision=allow |
| Review recorded | 1 | decision=allow; verdictRefPresent=true |
| Admission result | 1 | state=confirmed; throwsUnavailable=false |
| Later incident | 2 | ownerReceiptPresent=true; peerNoticePresent=true; peerReceiptPresent=true |

These are presence/equality observations, **not proof of cross-event receipt validity/association**. Counts do not establish the cause of concurrent preparation. No failure occurred in this new case, so its successful chain cannot reconstruct the original missing evidence or distinguish a prior projection defect from independent-model interpretation. No speculative production fix was made.

### Cleanup and version preservation

After the reviewer confirmed terminal/idle/control0 and no further product action, e2e-down stopped the task-owned Gateway and IM; the proxy job was canceled and collected. Ports60566/56096 were verified closed, and a process-executable-filtered check found no task-owned runtime processes. The temporary source and ignored proxy probes and the isolated environment flag were removed. Original independent static review confirmed the production file and packages/apps/tests/src/config have no differences from HEAD or frozen implementation `334bf622`; no diagnostic fields or behavior changes remain. A full production build after removal passed (exit0). Existing unaffected tests/Context/full acceptance positives were not rerun. Runtime evidence remains ignored, and no raw export or additional case was performed.

### Final diagnostic disposition

The original independent product reviewer returned **NOT PASS**: PA1 remains one major blocker with unclear regression attribution; the new positive case cannot satisfy the original failure closure. IV-2 remains subject to the independent verifier's recorded gate. Ready PR, canonical merge/archive and required remote CI are therefore not claimed.

The reviewer recommends an explicit product decision on whether a failed, independently reviewed refusal notice should also prevent legitimate owner-DM read-only consumption. Keeping the notice fail-closed, truthfully unsent/unavailable and without extra disclosure retries while isolating owner-read availability would change failure propagation. That is **not** implemented or implicitly authorized by this observational diagnostic; the existing prohibition on swallowing unavailable remains effective. It requires an explicit scoped decision, followed by deterministic failure-boundary evidence (notice unavailable → no external/private delivery, legitimate read remains consumable, notice not represented as sent/confirmed) and the unchanged normal-allow path. If current blocking semantics are retained instead, the availability defect and gate remain unresolved. No further stochastic rerun is proposed.

## Scope correction after independent gate re-examination

The owner restated that #361 requests bounded recovery for reviewer timeouts and temporary faults, not a redesign of PA notice failure propagation. The original independent product reviewer and verifier re-read the original requirements, design, current workflow and retained evidence at clean `5c1afb2024a5d2c0e6c96f89a2d809ce396471b2`. They found that treating the suggested new owner-read/notice isolation behavior as a feature delivery prerequisite had enlarged the agreed scope.

The feature acceptance bar remains exactly spec:48–85, design's installation matrix and W1–W7, plus the integrated tool/disclosure authorization, source and cache-isolation boundaries. It does not add a requirement that legitimate owner consumption must continue when an independent refusal notice is unavailable. All seven original Scenarios and required installation/audit evidence are already satisfied. PA1 has no established violation of those retry/cancellation/exact-action/source-isolation requirements; mere sharing of the Guardian class identifies an investigation surface, not evidence of feature regression.

The product reviewer formally corrects the **applicable #361 product gate to PASS**, with its requirement-to-evidence mapping in acceptance.md. This is a scope correction, not a waiver based on user dissatisfaction or successful stochastic reruns. The historical PA1 failure remains real, unresolved and of unclear attribution; it is not relabeled fixed, nonexistent or proven pre-existing. The prior proposed failure-propagation change is withdrawn as a delivery prerequisite and is not implemented. Independent verification records its own final disposition. No new model case, test matrix, production change or security-rule relaxation was performed for this review.

The corrected delta clarifies that its two requirements concern ordinary tool-action Auto review and grant no new recovery allowance to independent PA disclosure. This documents the already-reviewed implementation boundary, not a new behavior. Canonical integration and final delivery remain conditional on independent corrected-delta review and the final-main invalidation assessment.

## Final-main retention and delivery identity

The independent verifier subsequently recorded scoped feature PASS, IV-1/IV-2 CLOSED and corrected-delta PASS. Final authorized fetch found `origin/main=8d428779b5ebe0bb0c5c277f2ca5b56c0a303b82`, advancing from c4ebad992 by two documentation commits: four files/158 lines solely in the separate `refactor-668-deterministic-e2e` unit. No production, test, configuration, dependency or CI files changed. The original independent static reviewer checked that exact delta and retained all existing code, Context, verification and product evidence; no model/full-suite rerun is warranted. Product scope review and reports were committed at180cf46a1, then main was merged normally at`c6f11c1cdb60fd79702c91784a96af915ae13b9f`, preserving original executed SHAs.

Because current main now reserves668, the same repository atomic allocator reserved **feat-669**. Only this task's unit was renamed to `feat-669-auto-review-retry`; the unrelated main unit is untouched. Original625/668 execution identities in historical evidence remain historical, not rewritten as669 executions. Reviewed tool-only delta requirements were merged into gateway/agent-capabilities.md, with its canonical index count updated47→49. This changes documentation only; production remains byte-identical to334bf622. Final documentation/archival checks and exact effective-through are recorded in validation.md; PR and remote-CI completion require their actual receipts.
