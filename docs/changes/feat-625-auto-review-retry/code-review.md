# Code Review — feat-625-auto-review-retry

## Round 1 — full

- Reviewer: independent static reviewer `ea1605be-fdc6-4aee-8483-6ef5b67d6554`; neither implementation nor design author. Separately performs verification, not product review.
- Checkout: `/Users/czj/.codex/experiments/pa667-issue361/repository`
- Branch: `codex/feat-625-ab-e2e`
- `validated_at`: `dfee3df40116757346ef6a7edcaa5d10734c9a61`
- `executed_base`: `5454f3140f9c92532c690db8dec80b9f77080384`
- Range: `5454f3140f9c92532c690db8dec80b9f77080384...dfee3df40116757346ef6a7edcaa5d10734c9a61`
- The executed base is the caller-required isolated shallow baseline, **not independently fetched latest main**. No fetch or later history inspection. Effective-base/through after eventual integration remain executor-owned.
- Independently checked HEAD equals validated_at, initial status clean, and range diff-check clean.
- Authority: supplied `current-workflow` AGENTS/change-workflow/change-code-review and agent-context-review Implementation Review. Original active unit spec/design/delta/design-review and baseline current capabilities contract were read.

### Status

**No surviving concrete code defect identified in the inspected diff. Full gate is PENDING the outstanding actual Context/product evidence described below; this is not final approval or a claim that the user journey passed.**

Code findings (required JSON shape; empty rather than manufacturing a code defect from absent acceptance evidence):

```json
[]
```

## Static coverage

All changed product files were inspected: `policy/{approval,audit,cc,classifier,codex,retry,types}.ts`. All changed tests were inspected, alongside relevant existing source projection, decision parsing, Guardian input budgeting, native lifecycle/routing protection and the actual `session.observe` handler. The complete unit diff was enumerated; original design material was not treated as proof that implementation works.

| Risk | Evidence inspected | Result within this scope |
|---|---|---|
| Single owner / exact operation | approval.ts:108–148, retry.ts:86–130 | Downstream executes once before recovery; strategy attempts do not replay pre-execute or the tool. Action arguments/config/reviewer are detached, first evidence assembly retained. |
| Shared recovery and permanent-error precedence | retry.ts:21–32,92–125 | Two extras shared across service/transport/timeout/invalid; invalid recovery at most one; effective final verdict stops. Unknown text is not classified by regex; permanent codes do not become retryable from a 503 status. |
| Fresh budgets and CC semantics | retry.ts:94–117; classifier.ts:27–65 | 90s outer attempt timer includes preparation, new timer per attempt; 30/60 stage limits retained. Stage-one deny is ordinary second-stage review, not a failure retry. |
| Native retry multiplication | codex.ts:171–182; approval-retry-native.test.ts:19–22,38–59,71–74,105–120 | Reviewer-scoped prepend request-error remains terminal without next; thrown preparation/stream failures preserved separately. Native synthetic matrix uses provider always and checks actual calls. |
| Cancellation and noncooperation | retry.ts:44–64; approval.ts:149–176; codex.ts:100–150,185–186 | Abort races bound return, preserve unconfirmed nested drain, do not start replacement attempts without confirmed settlement. Late success cannot publish a verdict/checkpoint after signal abort. Audit is detached on cancellation rather than holding tool return hostage. |
| Guardian cache/fork/rebuild | codex.ts:34–38,54–78,84–150 | Existing checkpoint prefix/fingerprint rules retained; failed reviewer discarded; only successful live result publishes to still-owned trunk. Structured context errors, not service text, trigger evidence rebuild. |
| Routing and denial counters | approval.ts:79–106,159–173; approval.test.ts:66–151 | Technical unavailability distinct from classifier_block; final deny counted once; interactive, return_to_agent, unattended-deny and explicit unattended-allow remain separate. Explicit fallback is not model approval. |
| Audit/read consumer | audit.ts:4–20; classifier.ts:60–68; codex.ts:109–137; index.ts:370–375 | Optional schema retains nested attempts/children; CC multi-stage usage not presented as last-stage total; available native child usage retained; observe returns persisted approval domain. No new retry UI claim. |
| Architecture/API boundary | SPEC.md:7,40–50; public dsh-llm package exports and root declarations | Product changes stay in integration, reuse public failure/policy/stream APIs, introduce no second Agent loop or private import. |

Test changes preserve observable outcomes rather than only expected implementation counts: exact effects, reviewer request counts, no_verdict/category/routing, schema reopen equality, cancellation and late-cache protections. The revised overflow assertion preserves zero request/effect protection; dropping the old error substring is consistent with structured diagnostics. The changed seeded-reviewer count is accompanied by cancellation, deadline, created/disposed and subsequent-effect assertions, not accepted on its own.

## Independent execution and shared evidence

Independently executed at frozen tree (executor supplied current full build beforehand):

```bash
export PATH="/Users/czj/.npm/_npx/ef8b185be06dfeb4/node_modules/node/bin:$PATH"
env -u NANO_OWNER_CONFIG_ROOT -u NANO_REVIEW_EVIDENCE_PATH pnpm exec vitest run \
  packages/dsh-integration/tests/approval-retry-native.test.ts \
  packages/dsh-integration/tests/approval-cancellation.test.ts \
  packages/dsh-integration/tests/codex-approval-lifecycle.test.ts
```

Result: **3 files / 8 tests PASS**, start `18:10:50`, duration `17.12s`, exit code 0. The native matrix contains 14 scenarios, not 14 separately reported Vitest tests. Native fixtures created and cleaned their own temporary homes/DSH processes. No product acceptance stack, shared4000, excluded runtime, external IM or other checkout was accessed. No source/tests/design were changed.

Reused with limits: `M1-auto-review-retry/progress.md:23–34,38–69` records 49 affected tests and 13 dependency checks, and distinguishes pre-freeze failures and fixes. The executor separately reports full `pnpm build` and `pnpm typecheck` passing for the frozen tree. Subsequently inspected the executor-supplied frozen full-suite log `/tmp/pa667-issue361-dfee3df-tests.log:1–9`: **109 files / 494 tests PASS**, start `18:09:15`, duration `58.60s`. Attribution to frozen dfee3df is supplied by the executor (the log itself does not embed a SHA). No redundant full-suite run was started here.

## Agent Context Implementation Review

**Trigger and consumers:** replay/failure handling changes the input lifecycle for CC classifier and Guardian reviewer, and changes when the main Agent receives the final tool result. This is Mode B, not a new gate/role.

**Expected:** the same original action and trusted source evidence across recovery; no failure text promoted into owner intent; CC stage guidance preserved; Guardian delta/fork/rebuild and failed-cache disposal remain coherent; main Agent sees final technical unavailable rather than a policy-denial claim or a bypass instruction.

**Actually covered:**

- Inspected final native `llm/stream`/preparation seam fixture and persisted `M1-auto-review-retry/native-retry-evidence.json`; independently reran that fixture.
- CC snapshot examples at artifact lines 96–127 and 259–302 preserve host-origin human metadata and exact pending action, byte-identical messages across retries, and final executed/unavailable result. Native stage scenario separately checks stage 1/2.
- Guardian examples at artifact lines 610–741 and 744–922 preserve `<planned_action>` and host source identity; failed reviewer sessions differ and the failed diagnostic marker is excluded from captured inputs by the executable fixture. Final technical result is explicit. Source reconstruction rules in sources.ts:33–48,77–169 were traced, not inferred from hashes.
- Native lifecycle tests exercise delta/fork/rebuild and read-only tool restrictions; inspection results remain untrusted evidence, not permission. Code checks cached-publication identity and cancellation.
- No required new model parameter was introduced; retry bookkeeping is host-owned and is not an owner-message injection. Original parser/risk rules are unchanged.

**Limits / pending evidence:**

1. The stored artifact is explicitly **synthetic native seam evidence**, not provider-wire capture and not actual model selection/interpretation. It stores user-content snapshots plus system/messages hashes, not the complete final combined system/tool/message payload. Guardian `systemSha256` is the empty-field hash; system content can be in messages, so this is neither evidence that policy was absent nor proof of its full delivery. A hash cannot replace semantic inspection of that payload.
2. Need the independent product review's permitted locators/summary for representative real reviewer/main-Agent requests, corresponding responses/final tool results, original session/callId and operator `session.observe.approvals`. Check actual relevant fields/rounds, not a preview or raw DB substitute. Real-provider availability must remain separate from injected fault recovery.
3. The Global Agent plugin-create/install/two-call journey and CC/Codex injected product recovery/failure/stop paths are not executed by this static reviewer. Their completion is pending, not inferred from the native fixture.

The executor subsequently reports the product main model returned actual 402/QUOTA on two turns with zero tools, and that raw public Work evidence capture was explicitly denied. These are **reported service/permission blockers**, not independently observed implementation failures. No denied capture may be retried with another tool or identity. A permitted minimum remedy for the separate synthetic composition gap is to extend the existing all-synthetic fixture to retain the actual combined `llm/stream` system-bearing messages, tools/schema and relevant final-result messages (not real chat), with version/scenario/session locators; inspect their semantics, not only hashes. This would prove native assembly only, not provider wire or real behavior. Any code/test change and rerun is executor-owned.

The corresponding verification evidence blockers are tracked separately in `verification.md`; they are not relabeled as confirmed implementation defects. After permitted evidence arrives, complete only this outstanding coverage (or review an explicitly frozen fix delta), retaining still-valid static/test conclusions.
