# M1 implementation evidence

## Baseline and RED

- Sole checkout `/Users/czj/.codex/experiments/pa667-issue361/repository`, branch `codex/feat-625-ab-e2e`, HEAD `abb0eba5a83abd89149d250132c4dd3015d6b784`, clean before test edit.
- Read approved original design W1–W7, R1 recommendations and author closure; no old change history used.
- Node 24 path supplied by executor; all tests unset `NANO_OWNER_CONFIG_ROOT`.
- RED before product changes: `pnpm exec vitest run packages/dsh-integration/tests/approval.test.ts -t 'uses the dedicated reviewer'`: 1 failed, 5 filtered; expected nested invalid recovery attempts absent from actual `session.observe.approvals`. Existing actual result was one classifier_unavailable/no_verdict with no retry data. This is behavior/schema RED, not missing-import failure.

## Implementation

- Single complete-review recovery owner in `approval.ts`/`retry.ts`; public DSH `resolveRetryPolicy`, `LlmError`, `HarnessError`, `EMPTY_RESPONSE_CODE`. Two shared extras, one invalid recovery, independent 90-second attempt timers, 500/1000ms backoff and 10-second provider-hint cap.
- CC still has 30/60-second stages; stage usage is recorded separately, never overwritten by the final stage or presented as a complete aggregate. Workspace exemptions retain their source and are not persisted as model attempts.
- Guardian retains evidence rebuild, delta/fork/checkpoint semantics. Structured context errors alone trigger rebuild; service/invalid errors cannot accidentally match an error-message regex. Reviewer-scoped prepend request-error remains terminal without `next`; public agent/error also captures thrown preparation/stream errors.
- Exact action/config/reviewer identity and first evidence assembly are retained across retries. Failed/late results cannot publish checkpoints. Cancel also invalidates a previously completed Guardian trunk while the final audit is pending.
- Signal races bound the caller even for noncooperative work. A 50ms cleanup grace permits cooperative local drain; unconfirmed termination stops recovery, not concurrent replacement. Nested wrappers preserve a child's unconfirmed-drain fact. This does not claim physical termination of a remote provider.
- Audit schema persists optional nested reviewId/attempts/category/timing/reviewer/failure/children/usage. Unknown usage stays absent. Cancellation upserts the same automatic review, leaves deny counters unchanged, and cannot await an uncooperative audit indefinitely.

## Validation history

All Node commands use supplied Node 24 PATH and `env -u NANO_OWNER_CONFIG_ROOT` for Vitest. No full suite was initiated by this worker.

1. RED: original native approval/observe assertion, **1 failed, 5 filtered** before product changes (above).
2. First build found a compile-only mismatch between frozen Guardian evidence `unknown[]` and the existing `Record<string, unknown>[]` contract; corrected the internal snapshot type. No test was claimed green from this failed build.
3. Narrow recovery/timing/native lifecycle batch: **19 passed, 5 filtered**, 3 files, 6.33s.
4. Native structured-error matrix: **1 integrated test passed**, initially 11 scenarios, 15.97s; subsequently extended to 14 scenarios including active/preparation/backoff cancel.
5. Cancellation/timing/native batch: **33 passed**, 6 files, 17.07s.
6. Build and typecheck passed; first final affected batch was **48 passed / 1 failed**. The sole failure was the lifecycle fixture's old seeded-reviewer count after intentional cancel-time trunk invalidation (expected 6, actual 3). Actual deadline audit still showed three cooperative timeouts, all cleanupConfirmed=true; total created/disposed still 8/8. Updated that expected cache lifecycle, not budgets or execution protection.
7. **Final affected batch: 10 files / 49 tests passed, 17.90s**, after a fresh package build. Files: approval-retry, approval-cancellation, approval-retry-native, approval, codex-approval, codex-approval-lifecycle, codex-approval-native, approval-workspace, approval-sources, workflow-approval.
8. `pnpm --filter @nano/dsh-integration typecheck`: passed (same product semantics as final; subsequent product edit was docstring-only).
9. `pytest tests/contract/test_runtime_dependency_contract.py -q`: **13 passed, 0.20s**. Initial `python3 -m pytest` could not import pytest from Apple's Python; used the already installed PATH `pytest` runner, no install or product workaround.
10. `git diff --check`: clean. New test sizes: **149 / 148 / 38 lines**, all below 400.

Executor separately reported a pre-freeze broad run of 490 passed / 1 failed. Its only failure was CC's old context-window reason substring. The retained test now asserts structured config classification, one attempt, zero extras, no_verdict and return_to_agent; its existing exact effect list and model-review count still prove no overflow effect/request. Raw diagnostic text is no longer the routing or authorization interface. This is not a worker claim of final full-suite success.

## W1–W7 evidence map

| Requirement | Actual protection / observation |
|---|---|
| W1 shared caps, mixed invalid/service | `approval-retry.test.ts` parameterized complete-attempt outcomes; actual CC/Codex structured finish, throw and mixed native scenarios below. |
| W2 full independent budgets, CC stages, hints | Fake clock produces starts 0/90,500/181,500ms, each elapsed 90,000ms, total 271,500ms; provider hints cap at 10,000ms. Actual classifier test observes 30,000 then 60,000 then successful attempts and 2112/2112/10240/2112 token limits. Native Guardian deadline fixture accelerates only scheduler wall time and records six unchanged 90,000ms timers, three cooperative timeout attempts. |
| W3 permanent failure, native always, exemptions | AUTH/credentials/config/quota/unknown and final deny stop in helper tests; current approval/workspace tests retained. Native preparation and stream throws plus terminal finish failures run with provider retryPolicy=always and no durable llm/retry events. |
| W4 cancel/drain/cache | Native CC active/backoff and Guardian preparation/active cancel, uncooperative Guardian late completion and fresh subsequent session, real pre-execute uncooperative authorization/audit gates, helper allow race and nested drain propagation; existing fork/delta/rebuild coverage retained. |
| W5 zero during review / one afterward / routing | All 32 native review/preparation observations report effects=0. Six resulting effects correspond exactly to five model allows plus one explicitly configured unattended fallback allow; exhausted non-allow paths remain zero. Existing interactive/human/return_to_agent/unattended-deny tests retained. |
| W6 schema/reopen/observe | Native fixture compares all 14 original approvals arrays to real RuntimeClient session.observe after shutdown/reinitialize with original bindings. Cancel and per-stage/request usage included; unknown native preparation usage absent. |
| W7 actual input and final result | `native-retry-evidence.json` contains actual input snapshots and hashes, fixed reviewer, callId/reviewId, classification/usage/timing, effect counts and final tool results. Failed diagnostic text is absent from reviewer inputs; CC replay inputs identical and Guardian planned-action content unchanged. Existing source provenance/context tests also pass. |

## Native evidence artifact

[`native-retry-evidence.json`](native-retry-evidence.json) was produced by the passing native matrix in the first final batch; its product semantics equal the final batch (only docstring and expected lifecycle seed count changed later). It is synthetic isolated RuntimeClient evidence, **not** live-provider or IM product acceptance. Temporary homes are removed by fixture cleanup; saved input cwd/session IDs identify that now-closed test run, not an operational instance.

| Scenario | Actual review stream/preparation entries | Actual tool effects |
|---|---:|---:|
| cc-finish | 2 | 1 |
| cc-exhaust | 3 | 0 |
| cc-mixed | 3 | 1 |
| cc-stage | 3 (two stages in first attempt) | 1 |
| guardian-finish | 2 | 1 |
| guardian-exhaust | 3 | 0 |
| guardian-stream | 3 | 1 |
| guardian-preparation | 3 (native preparation throws) | 0 |
| guardian-mixed | 3 | 0 |
| guardian-auth | 1 | 0 |
| guardian-cancel-preparation | 1 | 0 |
| cc-cancel-active | 1 | 0 |
| cc-cancel-backoff | 1 | 0 |
| unattended-explicit | 3 | 1 (explicit fallback, not model allow) |

There are 32 entries, not 32 complete attempts or HTTP calls: four entries stop in native preparation and one extra model request is CC's normal second stage. The native artifact includes `requestsBeforeEffect`, all zero, and `reopenedObserveIdentical=true` only after exact comparisons passed.

## Execution interruption

One authorized types.ts edit returned classifier_unavailable/TimeoutError and did not apply. Reported immediately. Parent confirmed one same-tool, byte-identical technical retry; after rereading unchanged file that retry succeeded. No tool substitution, identity change, runtime modification or repeated retry loop occurred.

## Boundaries / remaining gates

No services/shared runtime, external messages, worktrees, fetch, child agents, or canonical design/spec edits. Native tests use isolated temporary homes. No new UI or diagnostic endpoint. No blocking design gap was discovered; implementation details do not lower the approved budgets or permissions.

Independent code review/verifier, real isolated IM/Work/plugin journey, live provider availability, final full CI, final sync/rebase and acceptance remain executor-owned. The 50ms local-drain bound conservatively ends recovery when local cleanup is slower or unconfirmed; it never proves remote termination. The original approved 290-second envelope excludes canceled-resource cleanup and durable storage scheduling, as documented in design. This worker's scoped commit is implementation evidence, not independent acceptance.
