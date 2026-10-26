# M1 implementation progress

## Baseline and responsibility

- Approved design integrated by fast-forward at `407b6e096ec4e6b0bdc9a4a30774dd2e2bed0148`; main `d72e220f1d21827c65e046f704c13837ea39d7c2`. Gate 2 remains as recorded in the unit report, not an implementation verdict.
- Persistent implementation branch `unit/feat-625-r2-361`; one existing isolated engineering worktree. No production/user checkout changes, merge, deployment or release.
- This is an in-progress implementation checkpoint, **not** a frozen review/Q package or a passing milestone. Remaining obligations include transaction/owner and exact concurrent-stream regression, IM HTTP fixture/trace export, isolated daily resource handoff, independent gates and final delivery.

## Meaningful Red → Green

2026-10-26 13:27 +08:00, before product changes: `pnpm exec vitest run packages/dsh-integration/tests/approval-retry.test.ts` failed at `recovers a CC stage-two service failure without replaying the valid first stage or executing a tool` with the fixture's real public `LlmError('temporary','SERVER',{status:503})`. The valid first-stage non-allow had already completed; the second-stage failure escaped immediately. The preceding constructor-misuse probe was corrected and is not counted as the meaningful red.

After action-local recovery/classifier integration, the same test passed: three requests, only second-stage input repeated; original supported-effort examples also passed. Integration typecheck initially exposed unbuilt workspace `product-contracts` declarations, resolved by its normal build; no lock/config change.

## Implemented at this checkpoint

- One recovery controller shared across CC stages / Guardian normal attempts, complete budgets, shared two-extra/one-format ceiling, bounded prepare/backoff/action/cleanup and cancellation generations.
- Guardian failures retire and drain exact reviewer identities, technical recovery uses fresh full evidence; context rebuild remains action-scoped. Disclosure retains its independent parser/namespace and original single normal deadline.
- Existing dispatcher observes only allowlisted request-local HTTP failure facts; exact native loop identity gates Guardian sinks, while main/CC/disclosure/auxiliary streams remain transparent.
- Optional durable approval trace retains review/attempt/request facts, failure categories and known usage without inventing missing counts. Existing counter/fallback paths retained; configuration transaction release unchanged.

## Executed engineering checks (not independent acceptance)

Commands are run in the above unit worktree with Node 24.22.1, locked DSH 0.2.1-alpha.1. Until a checkpoint commit is referenced below, these results describe the implementation tree in the containing commit or its documented prior delta, not an approved final product.

- `pnpm --filter @nano/product-contracts build`; `pnpm --filter @nano/dsh-integration typecheck`: exit 0.
- `pnpm exec vitest run packages/dsh-integration/tests/review-recovery.test.ts packages/dsh-integration/tests/approval-retry.test.ts`: 18/18, exit 0 (13:39). Fake clocks prove complete 30/60/90 budgets, mixed shared quotas, permanent/context/unknown errors, Retry-After 15s refusal, cancel during request/backoff, uncooperative cleanup and bounded prepare. Later trace-accounting/cleanup tracking deltas require rerun before freeze.
- `pnpm exec vitest run packages/dsh-integration/tests/review-recovery.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts packages/dsh-integration/tests/codex-approval.test.ts`: 33/33, exit 0 (13:47).
- `pnpm --filter @nano/dsh-integration build && pnpm exec vitest run packages/dsh-integration/tests/approval-retry-native.test.ts packages/dsh-integration/tests/codex-approval-native.test.ts`: 4/4, exit 0 (13:47–13:49). Real native loop and Anthropic HTTP, plus an actual default first Guardian 90-second timeout followed by successful fresh full recovery; native isolation/read-only inspection, concurrent forks and killable blocked filesystem checks retained. No shortening of production timers.
- Expanded `approval-retry-native.test.ts`: 20 dual-strategy cases across actual HTTP 503, 429 seconds/date, transport socket disconnect, malformed/repeated-invalid output, mixed shared quota, persistent failure, 401 and over-budget Retry-After; `pnpm --filter @nano/dsh-integration build && pnpm exec vitest run packages/dsh-integration/tests/approval-retry-native.test.ts`: 1 test / 20 cases, 25.09s, exit 0 (13:54). Native provider `retryPolicy=always/maxRetries=5` did not multiply review recoveries. Each allowed case executed one isolated effect; blocked cases executed none. Failed Guardian identities differed from recovery identities; actual HTTP facts arrived through the existing dispatcher.

## Affected existing-test disposition

- `approval*.test.ts`, source/admission/parser, personal-security and attribution tests: keep; their original product/permission seams still matter. Full applicable rerun remains due.
- `codex-approval-lifecycle.test.ts`: rewrite-merge the obsolete mocked `AbortSignal.timeout` assumption into cancellation of a context rebuild inside the unchanged judgment budget. The new controller's complete-budget/timeouts live at the narrow recovery seam; service tests retain evidence/cache/disposal protection.
- `codex-approval-native.test.ts`: keep native isolation/fork/inspection/timeout risk. Replace the fixture's unstructured context-error text with public `LlmError` code (production must not infer context by message regex); update old no-retry deadline expectation to actual complete-90s recovery and replace brittle fixed handle totals with failed-identity disposal / one retained committed cache assertions.
- New `review-recovery.test.ts` owns the previously absent action quota/timing policy seam. `approval-retry.test.ts` owns CC stage integration; `approval-retry-native.test.ts` owns public native-loop/adapter/HTTP/transport and real side-effect integration, not duplicate mock-policy assertions.

## Limits and next steps

These tests do not establish independent code/Context verification or Q product acceptance, and native HTTP is not a true IM journey. No daily services or real providers have been started at this checkpoint. Required next checks include request/backoff configuration rejected-release, persist/metadata release, true owner disable/cancel isolation, concurrent exact owner/ALS attribution, late-create/quarantine and capped usage accounting; then durable true-IM fixture/readonly export, daily preparation and neutral frozen handoff to the parent for independent reviewers/Q.
