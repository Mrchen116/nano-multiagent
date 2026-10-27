# Code Review — feat-669-auto-review-retry

> 最终交付编号669；625/668为本任务先前编号。历史执行版本不变，最新范围裁定及同步有效性见本报告末节和 [sync-review.md](sync-review.md)。

> 历史审查对应原创unit625；当前main集成后必须full复验，旧PASS不自动有效。迁移及失效矩阵见 [sync-review.md](sync-review.md)。

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

## Round 2 — targeted Context closure and evidence patch review

- Reviewer unchanged; `validated_at`: `1862af639681defdb91651f50cc6e01459e63e0b`; `executed_base`: `5454f3140f9c92532c690db8dec80b9f77080384` (same caller-authorized shallow baseline).
- `pre_fix_head`: `af0f2c3324aa924b2d1fa27ef87a795bd83d24c8`; reviewed fix delta `af0f2c3..1862af6`, including the two fixture edits and test-only synthetic encoder. Independently checked exact HEAD, clean pre-review status, diff-check, and empty production-source delta from R1 `dfee3df`.
- Scope is V-R1-2 and this patch, not a second full review. R1 static conclusions and its attributed full-suite/build/typecheck evidence remain applicable to unchanged production source; no new full-suite execution is claimed. Executor supplies final narrow **2 files / 2 tests PASS, 17.24s**; independently inspected fixture assertions and reconstructed artifacts rather than redundantly rerunning that suite.

### Actual composed Context inspected

Read `M1-auto-review-retry/{native-context-evidence.json,guardian-context-evidence.json}` and the R1 correction section of `validation.md`. Recursively reconstructed sole-key `$syntheticText` references using the supplied full `textPool`. Independently recomputed both reconstructed payload hashes, each pooled-text hash and both fixture-source hashes against current source, all matching. The encoder explicitly requires syntheticOnly, deduplicates long strings, and asserts lossless JSON round-trip; it neither sanitizes real captures nor authorizes their collection. No runtime product data was accessed.

Semantic inspection, not just hash comparison:

- Native evidence has 14 scenarios and 28 complete stream compositions; four preparation observations never reached stream and correctly have no stream composition. CC system plus user message, empty tools, exact action/transcript and stage-specific options are retained. `cc-stage` preserves stage-1 conservative guidance, stage-2 intent/exception handling, then restarts the complete strategy at stage 1 after technical failure. Replay does not append failed reviewer prose as human permission.
- Guardian system policy is present in `messages[role=system]` even though standalone `system` is null. Its policy explicitly distinguishes human/direct-parent/permission origins, private assistant prose, untrusted tool evidence, exact planned action, prior verdicts versus authorization, and read-only investigation. Tools are precisely `guardian_stat`, `guardian_read`, `guardian_list` with their bounded schemas; the pending fixture action is evidence, not an executable reviewer tool.
- The 18 Guardian compositions include initial full input, incremental history, inspection round-trip, concurrent forks, invalid failure and next action, overflow full rebuild, cancellation and deadline retries. Reviewed source prefixes and actual histories: new user messages retain host human origin, assistant prose stays private, final tool failures stay `untrusted-evidence`. A failed main-tool result can legitimately occur in later history; that is distinct from publishing failed reviewer checkpoint/diagnostic content as a successful cached verdict. Forks retain separate exact action IDs; rebuild restores prior transcript plus the current pending action.
- Main-Agent result messages preserve role/toolCallId/source linkage. Exhausted service/invalid/auth/timeout results say reviewer unavailable with classifier_unavailable/return_to_agent, rather than asserting a substantive policy violation or recommending bypass. Successful execution and explicit unattended fallback remain distinct in audit. Canceled turns do not require a nonexistent successful result; absence is not fabricated as model delivery.

**V-R1-2 is CLOSED at the required synthetic native-assembly level.** No confirmed implementation or encoder defect identified; code findings remain `[]`. This is not provider-wire capture or proof of real model interpretation. R1 Context pending item 1 is superseded by this closure; product pending items 2–3 remain open under V-R1-1. Overall full gate remains **PENDING**, not final approval/archive readiness.

Permission clarification supplied by executor: the prior denial concerned raw product evidence persistence; a later consumer-script edit was also blocked before RuntimeClient execution. These facts must not be generalized into a blanket denial of all originally authorized read-only product observations. This reviewer neither retries those methods nor collects product evidence. Final main synchronization still requires executor-recorded effective base/through and delta invalidation assessment. Only these two review reports were appended, with no implementation edits or reviewer commit.

## Integrated round 1 — full review against current main

- Independent reviewer unchanged; implementation/design author is not this reviewer.
- `validated_at`: `334bf62260225e5c350aafe3bc8a23af66f1fda9`; `executed_base`: `c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5`; range is that base through the frozen implementation. HEAD and range whitespace checks independently confirmed. The two new integrated synthetic artifacts were untracked supplied evidence at inspection; no production working-tree changes were present.
- This is a **new full code and Context review**, not inheritance of historical PASS. Read the complete seven-file production diff, all changed tests, original feature requirements, current sync decisions and the relevant current-main source/protection consumers. The other main-owned feat-625 design was not read or changed. No fetch, implementation repair, test modification, commit or product access occurred.

### Static result

**No confirmed implementation defect identified; code findings `[]`.** This is not full verification or product acceptance PASS. Current integrated full-suite failures and outstanding new-tree product evidence are tracked in verification.md.

| Boundary | Independently inspected integrated evidence | Result |
|---|---|---|
| Whole-review recovery | approval.ts:138–154; retry.ts:82–130; all retry arithmetic/native tests | Frozen arguments/config/reviewer, first evidence assembly reused; two shared extras and one invalid recovery; verdict/permanent failures stop; tool execution is not replayed. Fresh90s outer budgets and CC30/60 stage limits remain. |
| Current-main authority | approval.ts:69–81,112–154; sources.ts:96–192; personal-security.test.ts:10–58 | Effective history and native human/task-control/source projection retained. No ordinary review call to full-owner-database authorization; exact action stays separate. Earlier tool outcomes and private assistant prose do not become original human grants. |
| Disclosure separation | codex.ts:50–56,64–117; index.ts:535–583; personal-security.ts:42–70,97–103; lifecycle test | Tool recovery only. Disclosure retains its separate strict policy/parser, namespace, host-bound lineage/audience/payload/restrictions and native90s deadline. Tool cancellation releases only tool cache; configuration/disposal releases both. Added lifecycle assertion checks that disclosure checkpoint survives tool release. |
| Cancellation/publication | approval.ts:83–103,155–182; retry.ts:44–64,94–128; codex.ts:142–194 | Cancellation wins before allow return, invalidates owned cache and substitutes same-review audit. Unconfirmed drain ends recovery rather than issuing overlapping replacements; detached child collectors prevent late audit mutation. |
| Guardian isolation | codex.ts:198–235; integrated native fixture | Scoped read-only inspection tools, host system policy, pre-step filtering and native request-error interception retained. Failed reviewer is discarded, successful live checkpoint publication requires trunk identity; context rebuild remains distinct from service retry. |
| Accounting and compatibility | audit.ts; types.ts; classifier.ts; codex.ts:153–181 | Optional retry aggregate/children preserved through observe storage; multi-stage usage is not falsely represented as last-stage total, missing usage not synthesized as zero. Disclosure without a collector does not decode test stub streams. |

The integration's human matcher, explicit nano defaults, effective-inherited preparation seam and purpose-aware usage/deadline fixes correspond to current-main behavior rather than dropping assertions. The native deadline fixture's500ms scheduler acceleration changes only synthetic wall time; production still requests90000ms, and exact budgets/created/disposed/effects assertions remain. Its reported full-suite cleanup failure is **not dismissed** as harmless merely because the focused run passes; it remains an unresolved verification result pending isolated execution/diagnosis.

### Integrated Agent Context Implementation Review

Independently reconstructed `M1-auto-review-retry/integrated-native-context-evidence.json` and `integrated-guardian-context-evidence.json`. Both payload hashes, every text-pool hash and fixture-source hashes match; both identify frozen334bf622. These are complete synthetic native `llm/stream` compositions, **not real-provider wire captures or real-model interpretation**.

Semantic checks cover14 native scenarios/28 stream compositions (four preparation observations correctly have none), and18 Guardian compositions. The current system policy includes current-main human/task-control provenance, exact-action and original-scope constraints, historical/restored distinctions, actual-sent versus private-proposal distinction, and explicit nonauthority of assistant/tool/reviewer output. Guardian policy is carried in system-role messages when top-level system is null. Its schemas expose only guardian_list/read/stat; pending business action remains evidence, not an executable reviewer tool.

Inspected exact action IDs, frozen repeated inputs, CC stage restart, Guardian full/delta/fork/overflow rebuild/failed-cache paths and inspection round-trip. Human origin fields remain intact; assistant prose is private; previous technical-failure tool results are untrusted evidence, not authorization. Main final tool messages retain call linkage and technical-unavailable/return_to_agent semantics, and successful execution remains separate from explicitly configured unattended fallback. No failure diagnostic is promoted into owner intent.

**Synthetic native Context composition passes at this integrated freeze.** Current-main PA host identity/audience/restriction protection was additionally traced in unchanged source and its regression tests; synthetic ordinary-tool fixtures are not represented as live PA disclosure acceptance. Real product/new-tree outcome and audit correlation remain the independent product gate, not supplied by these artifacts. No new test runner was launched while the executor's full-suite rerun was resource-contended; current reported RED and later isolated results must retain their own provenance.
