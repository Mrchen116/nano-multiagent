# M1 implementation progress

## Baseline and responsibility

- Approved design integrated by fast-forward at `407b6e096ec4e6b0bdc9a4a30774dd2e2bed0148`; main `d72e220f1d21827c65e046f704c13837ea39d7c2`. Gate 2 remains as recorded in the unit report, not an implementation verdict.
- Persistent implementation branch `unit/feat-625-r2-361`; one existing isolated engineering worktree. No production/user checkout changes, merge, deployment or release.
- This is an engineering implementation/evidence freeze for independent static review, **not** a passing milestone, Q product acceptance or Ready PR. The exact containing commit is supplied by `git rev-parse HEAD` in the neutral handoff. Daily resource preparation runs in parallel with static gates; independent gates and final delivery remain outstanding.

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

These tests do not establish independent code/Context verification or Q product acceptance. True IM controlled-HTTP evidence below is now present, but no real-provider daily journey has been executed at this freeze. Reviewer/Q findings, final sync/delta/canonical merge, whole local CI, archive and Ready PR/remote CI remain outstanding. The parent schedules independent code review + Context Implementation Review + verification, and Q independently; the same implementation worker retains repairs and runtime/CI cleanup.

## Completion delta and additional Red → Green

- Freeze exact tool arguments and serialized Guardian action before asynchronous preparation; retain frozen config even when metadata revision mutates live config. A no-effort model exposed an actual native non-JSON-serializable request from explicit `undefined`: omit unsupported `reasoningEffort` entirely from route, options and agent request. Both strategies now pass actual no-effort HTTP admission.
- Lifecycle red tests exposed stale quarantine after successful delayed disposal and a busy trunk left set after failed cleanup. Normalize only the tracked judgment completion, retain real disposal rejection as quarantine, and clear busy in nested finally. Lifecycle suite now 10/10 including late-create, delayed-dispose and frozen-action protection.
- Recovery accounting red tests showed failed HTTP adapter all-zero usage incorrectly represented as known and capped canceled requests losing partial usage. Per-attempt private pending sinks seal all requests on revoke; unknown failed zero remains unknown, positive partial is retained beyond the 100 exported-row cap. Recovery suite now 19/19.

## Additional executed evidence (engineering only)

All commands use this worktree's `.venv/bin/python` 3.11.17 or locked pnpm dependencies. Owned test runtimes are under ignored `output/`; each test uses `finally` to down its stack and stop its own fixture. Raw request bodies/logs/config/DB remain ignored.

| Layer / command suffix | Result / limits |
|---|---|
| `pnpm build`; frontend `npm run build` | Both exit 0; rerun build for final frozen SHA before daily start. Earlier build carried checkpoint SHA while source dirty, not an attested frozen build. |
| `pnpm exec vitest run packages/dsh-integration/tests/approval-retry-configuration-native.test.ts` | 1 umbrella / 20 native HTTP controls, exit 0, 12.93s: both strategies × request/backoff × rejected prepare release, persist-failure release, metadata apply release, real cancel, owner disable. Another owner remains unaffected; allowed effects exactly once, revoked zero. |
| `pnpm exec vitest run packages/dsh-integration/tests/approval-retry-concurrency-native.test.ts` | 1 umbrella, exit 0, 4.02s: idle I, active A/fork B, other-parent C, hand-built CC D, disclosure P, main M and auxiliary X simultaneously; cancel B only, distinct HTTP/usage/identity, reuse C on next action. |
| `...pytest .../test_auto_review_retry_critical_path.py -k http_retry ... --basetemp=output/feat625-im-faults-r5` | True IM → Node → native DSH → HTTP, 1 umbrella / 20 dual-strategy cases passed 31.36s: 503, 429 seconds/date, socket disconnect, invalid/mixed output, 401, persistent failure, excessive Retry-After; original interactive card denied on exhaustion, exact zero/one effect, durable callId-correlated trace. |
| Same file `-k 'stop_request or default_full' --basetemp=output/feat625-im-cancel-timeout-r1` | 3 passed, 184.01s: true IM `/stop` during request/backoff both strategies, plus actual first CC 30s and Guardian 90s timeout with complete new budgets and one final effect. No production timers shortened. |
| Same file `-k rejected_configuration --basetemp=output/feat625-im-config-r1` | 1 umbrella / 4 controls passed, 17.90s: actual IM PATCH removes busy bash → 409 capability_in_use → PA/Node transaction release; original request/backoff continues and executes once both strategies. |
| Same file `-k cc_stages --basetemp=output/feat625-im-stage2-r1` | 1 umbrella / 3 controls passed, 74.71s: stage-two 503 only repeats failed stage; stage-one consumes two recoveries then stage-two failure escalates without new quota; actual full 60s stage-two timeout → new full 60s → one effect. |
| `...ruff check` four new Python files; `...pytest tests/unit/test_review_trace_export.py -q` | Exit 0, 2/2: old/recovery v1 rows, prompt/reason exclusion, exact filters and out-of-root symlink rejection. |
| Integration typecheck; six narrow files `review-recovery`, `approval-retry`, `codex-approval-lifecycle`, `codex-approval`, `approval-sources`, `llm-attribution` | Exit 0, 54/54 on final source delta (14:40). `git diff --check` exit 0. |

Fixture development failures were investigated, not counted as product failures or hidden passes: inherited bare IPv6 NO_PROXY made httpx reject URLs (sanitize only subprocess environment); stale ACK/permission WS frames needed exact case/call IDs; excessive new WS ticket creation hit 429 (reuse one socket per matrix); repo default 90s pytest timeout killed a production-budget test (file explicitly allows 1800s). The interrupted owned stack/fixture were stopped and ports checked; subsequent runs finish with normal cleanup. A Python lint failure was an unused fixture import and was removed before the successful rerun.

## Neutral review map / remaining gaps

- Production scope: `policy/recovery.ts`, `review-http.ts`, classifier/approval/codex/audit/types and the existing `llm-attribution.ts` dispatcher. No runtime fork/private import, no PA/Channels/IM DSH import, no new production debugging switch or attempts UI. New trace is optional in existing domain v1.
- Context Implementation Review: frozen current visible rows/action/config/model/effort; no all-library fallback read; technical Guardian retry fresh full from same frozen source, action-scoped context rebuild; exact native identity before owner read; disclosure/main/CC/aux transparency; live/restored provenance, current parser and PA input/output protections retained. Check captured requests and existing source tests rather than treating file presence as behavior proof.
- Verification: review all approved spec/design/delta requirements against code and evidence. Final corrected-delta/canonical spec has not yet been merged; explicitly report any unproven route, audit-failure or Context cross-regression rather than infer pass from the matrix.
- Product Q still requires both clean daily profiles, actual default models/efforts and audit route smoke, actual Global self-created/installed plugin with two real calls yielding 180/55, Work/user delivery, plus independent assessment of controlled faults and original fallback/child/schedule routes. No real-provider journey is claimed here.
- Same worker will supply exact daily identity/URL/PIDs/ports/build and neutral local evidence locators separately, fix findings after notifying parent of pre-fix SHA, then return a new frozen SHA. Static gates need not wait for daily readiness.
