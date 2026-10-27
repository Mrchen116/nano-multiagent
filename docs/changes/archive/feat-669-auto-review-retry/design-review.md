# Design Review — feat-669-auto-review-retry

> 最终交付编号669；625/668为本任务先前编号。历史执行版本不变，最新范围裁定及同步有效性见本报告末节和 [sync-review.md](sync-review.md)。

> 以下历史审查执行时本原创unit编号625；final sync只迁移本unit到668，详见 [sync-review.md](sync-review.md)。

## Round 1

### Metadata

- reviewer_target: independent design reviewer `ca8c1017-6db6-4c90-b3e6-a994cea8bffa`; delegated by `54612f0b-8c6a-41bd-a908-0427784264c0`. Not the design author or implementer.
- review_mode: `full`
- mode_reason: first independent Gate 2 review; original spec, design, delta and milestone skeleton all reviewed.
- started_at: `2026-10-27T08:57:46Z`
- completed_at: `2026-10-27T09:02:41Z`
- duration: 4m55s (review and evidence collection; report written afterward).
- checkout: `/Users/czj/.codex/experiments/pa667-issue361/repository`
- branch: `codex/feat-625-ab-e2e`
- validated_at: `5454f3140f9c92532c690db8dec80b9f77080384` plus the untracked original design-unit snapshot fingerprinted below. This is not a claim that HEAD contains these documents.
- executed_base: supplied isolated baseline `5454f3140f9c92532c690db8dec80b9f77080384`; no local `main` or `origin/main` ref exists. An initial ref query failed; `git show-ref` confirmed only the assigned branch. No history fetch or claim of independently checking current remote main.
- effective_base / effective_through: not asserted beyond this reviewed snapshot; final integration/sync invalidation belongs to executor.
- authority: supplied `current-workflow/AGENTS.md`, `docs/development/change-workflow.md`, design-reviewer Skill and report reference; agent-context-review Design Review mode and agent-context-engineering. Baseline `docs/specs/CONTRIBUTING.md` used for delta format.

Reviewed file SHA-256:

| File (relative to unit) | SHA-256 |
|---|---|
| `spec.md` | `292c486734382c7ada2bf1e3991121e0021591e704bdf32cdb0abe7c5c3d1156` |
| `design.md` | `0dd169df7071b65ee2d9b92fa8725b977dd806128348b741c5fa73a47bc93d81` |
| `specs/gateway/agent-capabilities.md` | `3577d5c7572b662ce5d2969e550060acbcb7f5422f7099fb58666f0143b32132` |
| `M1-auto-review-retry/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

### Verdict

**Approved — 0 CRITICAL / 0 WARNING.**

This approves the implementation design, not the implementation, real provider availability, cancellation/drain behavior in a running system, or product acceptance. Author must still verify recommendations and record its Gate 2 closure. Material changes require independent re-review.

### Coverage and evidence

#### Requirements, current behavior and architecture

- Read issue #361 directly using `gh issue view`; its old baseline/results are not this review's evidence. The original requirements and delegated numerical limits are represented by spec lines 46–83 and design decisions 1–5.
- Grounded the actual tool interception path in `packages/dsh-integration/src/policy/approval.ts:99-145`, not a test-only classifier. Downstream checks, safe/explicit exemptions, manual mode, policy selection and final routing precede/follow the planned retry owner appropriately. Existing unattended explicit allow is acknowledged, rather than falsely claiming every technical failure implies tool zero.
- Read `cc.ts:11-16`, `classifier.ts:9-38` and `codex.ts:39-156`. CC first-stage non-allow proceeds normally to stage two; it is not a transient-recovery event. Workspace exemption remains before classification. Guardian full/delta/fork and one evidence-budget rebuild remain distinct from outer attempts.
- A small product-owned policy helper is justified: native retry is request-scoped, whereas the product requirement counts a complete review including CC stages, preparation and Guardian inspection. Reusing the public failure types and policy resolver while retaining native Agent execution avoids a second Agent loop. No PA/IM dependency on DSH or private runtime import is proposed.
- The shared two-extra cap, invalid recovery sub-cap of one, permanent-error precedence, immutable action/reviewer/evidence and single final routing point are sufficiently explicit. Model requests/stages are not falsely equated to complete attempts. The timeout budget is fresh per attempt, with CC 30/60 sub-budgets intact, and bounded backoff is separated from the next attempt's budget.

#### Native retries on all error paths

- Independently read installed `@deepseek-ai/dsh-agent` public root export/package declarations and `lib/types/runtime-types.d.ts:334-356`: undefined without `next()` is terminal at `agent/request-error`.
- Read installed `@deepseek-ai/dsh-llm` root declarations (`index.d.ts:16-25,48-71`) and `retry-policy.d.ts`: structured failures and resolver are public; normal default maxRetries is five, and always is unbounded. Design explicitly does not inherit these budgets.
- Inspected the installed root implementation (read-only, no import/patch) of `dsh-agent-loop/lib/index.js:1049-1199`: terminal stream finish error/aborted dispatches request-error and loops only on `{kind:'retry'}`; thrown preparation/stream errors exit instead, reaching the turn error path at 1008–1033. There is not a second retry loop on those thrown paths in this baseline.
- Inspected `dsh-llm-retry/lib/index.js:151-178`: always mode can retry despite a downstream terminal result if that plugin is reached. Thus design's **prepend, reviewer-scoped terminal interception without next** is essential, not merely a local maxRetries value. Baseline `codex.ts:151` has that interception; design lines 34–37,120,154 require preserving it and testing always mode. The design does not rely on an inner retry budget multiplying the outer cap.
- Evidence-budget rebuild must remain limited to actual context/budget failures, not message text accidentally matching service/invalid errors. Design lines 55,65–78 require structured categories and explicitly exclude this multiplication route. W1–W4 cover relevant regression classes; recommendation R1-R1 makes the two native failure seams particularly explicit.

#### Cancellation, failed cache publication and drain

- Baseline `codex.ts:91-121,125,155` waits for idle/dispose and publishes a successful checkpoint; simply racing the outer Promise would not be sufficient. Design lines 80–95 explicitly require abort checks inside publication, discard/quarantine of failed reviewers, ownership protection against stale completions, and no next attempt until prior work is confirmed ended.
- For an uncooperative source, design distinguishes bounded caller return from actual local drain and unknowable remote computation. It chooses technical unavailability instead of concurrent retries when termination cannot be established, consumes late rejection, and bars late verdict/cache publication. This is an implementable fail-closed choice; the 290-second active budget is not represented as proof of physical remote termination or durable-I/O latency.
- Parent cancel wins over deadline and late allow, including after audit persistence. Active/preparation/backoff/allow races and subsequent/concurrent Guardian reuse are explicit W4 acceptance criteria. No canceled/failed reviewer is permitted to commit reusable evidence. These are design requirements, not runtime results observed in this review.

#### Audit schema and honest consumer access

- Read actual `policy/audit.ts:4-19` and `policy/types.ts`. Baseline schema does not yet retain the proposed retry data. Design lines 98–104 explicitly changes the schema/types and requires persistence/reopen/observe round-trip, not an unsupported claim that arbitrary metadata will survive.
- Read `src/index.ts:370-375`: approvals are returned from the real Nano durable domain by `session.observe`; they are not native session event retry cards. `reviewId`, original `callId`, executed attempts, extra counters, categories, reviewer/model, timing and available usage provide an inspectable distinction from another main-Agent tool call. Cancel and unconfirmed cleanup are required to be recorded without changing safety-deny counters.
- Work remains the real tool trajectory. It is **not** the retry-audit UI. The parent separately confirmed its PA consumer currently consumes events/modelRuns rather than approvals and proposed a diagnostic using the exported `RuntimeClient` after stopping the isolated stack, restoring original trusted bindings against the same profile, never running concurrent owners. I checked the public client export in package.json, `client.ts:38-64`, and the real observe handler/binding guard. This is a viable operator evidence route consistent with design104, not proof it has been executed and not a new user-visible endpoint.
- Product evidence must retain a reproducible session/callId locator and actual observe result alongside Work evidence. If the authorized diagnostic cannot retrieve it, design104 requires resolving the consumer gap and re-reviewing a new access surface; raw DB reads cannot silently substitute. This limitation is explicit and does not justify a speculative new product API at design time.

#### Agent Context Design Review

- Trigger: retry changes reviewer input lifecycle, Guardian checkpoint reuse and when the main Agent sees failure, despite not intentionally changing policy wording.
- Consumers/surfaces: CC system/transcript/stage suffix; Guardian trusted evidence/action plus inspection results and cached history; main Agent's final tool result. Expected knowledge is exact action and provenance, not new authorization inferred from a provider error or prior failed verdict.
- Design92–110 fixes model/action/source evidence across attempts, excludes failed reviewer messages from committed checkpoints, preserves missing-evidence labels, and keeps intermediate retry failures out of owner-message context. The final unavailable result is technical failure rather than policy denial or permission to bypass.
- W7 requires actual assembled reviewer requests and main-Agent final tool results, including delta/fork/rebuild and source-boundary cases. This is adequate design-level validation; no real model context or behavior was captured here. Source-policy changes during later work must remain governed by existing product controls, not inferred from a stale retry success.

#### Delta, milestone and validation gates

- Delta targets the correct canonical `docs/specs/gateway/agent-capabilities.md`. It adds recovery/observability requirements without deleting existing policy selection, CC two-stage or Codex evidence scenarios (canonical lines508–579 inspected). Its at-most-one tool execution wording composes with spec's exactly-one successful operation and cancellation constraints.
- Skeleton contains only `M1-auto-review-retry/.gitkeep`; no fabricated tasks/progress. Single milestone is appropriate because retries, cache lifecycle, audit and permission routing cannot independently satisfy this feature. W1–W7 cover mixed failures, full budgets, exemptions, non-retry classes, cancellation, single tool execution, route preservation, schema persistence and actual Context.
- Runbook128–140 and milestone gates retain independent product review, static code review/verifier and final CI/merge work. `scripts/e2e-up.sh` supports only default/feishu profiles (lines123–135), isolates ports/identity/workspace, and refuses live PID ownership. The parent-approved isolated **default equivalent** is accurately named, not claimed to be daily. Real plugin creation→installation→two calls must be independent product evidence, separated from deterministic failure injection.
- No migration/prototype is required: this design introduces neither deployment migration nor a UI redesign. No services, tests, browser, inbox/chat or production runtime were accessed or started in this review.

### Historical issue closure

None: this is the original R1, not a review of earlier feat625 materials. No historical findings or test outputs were used.

### Issues

None.

### Recommendations (non-blocking)

- **R1-R1 — Name both native error seams in implementation evidence.** In W3/native always coverage, separately show a structured finish failure and a thrown preparation/stream `LlmError`, plus invalid→service and service→invalid mixtures. Assert actual request count, absence of native `llm/retry` recovery, preserved category and unchanged main-Agent callId; a fake `review()` rejection alone would not prove native-cap enforcement. Existing W1–W4 already require the underlying invariant.
- **R1-R2 — Make diagnostic evidence reproducible.** In the eventual runbook/evidence, record stopped-stack ownership check, same-profile/original-binding restore command, session/callId and the saved `session.observe.approvals` locator. Label it operator diagnostic evidence, separately from the Work tool trajectory; do not label the stack daily or the raw approvals a Work UI feature. This operational detail implements the already approved design104/136 distinction.

### Scope and limitations

Only this report was written. No design/code edits, commit, other checkout, history fetch, old feat625 files/results, external IM, `/tmp/pa667-issue361-runtime`, or shared4000 service operations. Source/declaration inspection establishes feasibility and requirement coverage, not passing tests. Final gate validity must be reassessed for material edits, implementation discoveries and any later main-base change.

### R1 final committed-snapshot confirmation

At `2026-10-27T09:05:35Z`, before handoff, the parent reported committing the four reviewed documents without edits. I independently rechecked HEAD, working-tree status and all four SHA-256 fingerprints: they exactly match the reviewed table. Only this report remains untracked. Therefore the final **validated_at is `388139af40da5fe9c7ab6deca6586c7d8d1dc0ab`**, with **executed_base `5454f3140f9c92532c690db8dec80b9f77080384`**. This supersedes the initial untracked-snapshot locator above, not the reviewed content or verdict. Final completion including snapshot confirmation is `2026-10-27T09:05:35Z` (7m49s from start). No material change or new Round was needed; **Approved, 0 CRITICAL / 0 WARNING** remains valid for that exact committed snapshot.

### Author Resolutions

Author: `478c29d9-b9f6-4866-81d7-a02c31132d78`, original spec/design author; not the independent reviewer.

- **R1-R1 — accepted.** The recommendation is a concrete evidence refinement of W1/W3/W4, not a new recovery design. Native terminal finish and thrown preparation/stream errors must be exercised separately through real strategy/native seams, with request counts, category, unchanged main tool callId and no native `llm/retry` events. Preserve the reviewer-scoped prepend handler without next across full/delta/fork/rebuild and both failure paths; do not alter final decision parsing or risk/authorization semantics. Mixed invalid/service coverage remains required. Author previously verified the public request-error terminal contract and now checked the independent report's two-seam grounding; this resolution does not claim those tests have run. Executor owns actual implementation evidence.
- **R1-R2 — accepted.** Author directly checked `packages/dsh-integration/src/client.ts:38-64`: exported RuntimeClient starts the official nano profile with the supplied home and provides drain/shutdown; it does not by itself restore product authorization bindings. Executor reports a viable same-profile path via NodeConfiguration.read/runtime and original trusted bindings, with isolated home `.dsh-runtime/wt-repository-95829` and session obtained from the public Work ID. Treat this as an implementation/diagnostic plan, not completed retrieval evidence. Before operator inspection, stop and verify ownership of the isolated stack, restore its exact runtime configuration and original trusted bindings, then retrieve `session.observe.approvals` with the corresponding public session/callId and save an evidence locator. Never run concurrent owners, invent bindings, read raw DB as a substitute, touch shared4000, or label this default stack daily. Work remains tool trajectory; approvals remain operator diagnostics. This realizes the existing design consumer boundary without a new product API; inability to execute it remains an evidence gap to resolve before product acceptance.

Author verified HEAD `388139af40da5fe9c7ab6deca6586c7d8d1dc0ab` and all four reviewed file hashes against R1 before editing. There are no CRITICAL/WARNING issues and no material author disagreement; both non-blocking recommendations are accepted as downstream evidence obligations. Gate 2 is closed for the approved design, not for implementation correctness or real-provider availability.

**Non-material retained change:** only the status sentence in `design.md` line 3 changes from pending R1 to Approved with a link to this report and an explicit reminder that implementation/product gates are not passed. No requirement, architecture, budget, scope, delta or milestone changed; spec/delta/skeleton remain byte-identical to the reviewed fingerprints. This Author Resolutions section records closure and evidence responsibilities, without rewriting the independent Round. R1 is retained across this status-only correction; no new Round is required. Final integrated effective-through remains executor-owned and must be recorded against the actual subsequent tree.
