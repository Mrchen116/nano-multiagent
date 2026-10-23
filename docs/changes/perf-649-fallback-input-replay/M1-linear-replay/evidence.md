# M1 validation evidence

## Claim / baseline / method

Baseline `3814a7faae6617df3203fd58382ce7d53419090a`; Node v24.22.1, macOS arm64. Changed implementation: inputIdsForTurn performs a single transient replay; ModelFallback uses it at turn/end. Existing inputEvidence and session.lookup are unchanged. These are synthetic measurements, not production latency attribution.

Reproduce from repository root:

```sh
pnpm exec vitest run packages/dsh-integration/tests/input-evidence.test.ts packages/dsh-integration/tests/model-fallback.test.ts
pnpm exec tsx scripts/benchmarks/fallback-input-replay.ts
```

The benchmark uses 500/1000/2000 historical inputs plus one final input, five events per turn, empty queue between turns. It compares the previous repeated inputEvidence projection against the new helper, warms each once, and reports the median of seven uninstrumented iterations. Separate numeric-index Proxy reads count event visits without contaminating timing. Source fixture and assertions are committed; no private production histories are used.

## Result

| Historical inputs | Events | Previous visits | New visits | Previous median ms | New median ms | Ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 500 | 2505 | 1257510 | 2505 | 54.327 | 0.281208 | 193.2x |
| 1000 | 5005 | 5015010 | 5005 | 227.865 | 0.421833 | 540.2x |
| 2000 | 10005 | 20030010 | 10005 | 1276.197 | 0.984542 | 1296.2x |

The largest fixture removes 99.95% of event visits and exceeds the same-machine 5x timing target. Exact milliseconds are machine/load dependent and are not CI assertions. 1000-input regression with the old projection reproduced RED: 5,005,000 visits exceeds limit 10,000. The new projection passed the same test, all prefix semantic comparisons, and existing input evidence tests. Combined narrow run: **2 files / 20 tests passed**, 46.13s. `pnpm build` passed.

## State and memory boundary

No persistent cache/index or schema change. In this fixture there are I+1 inserted IDs and the same number of final-owner map keys, so the two collections have 2*(I+1) entries (4002 at the largest fixture), peak queue length 1. Those are fixture-derived cardinalities, not heap-byte measurements. General temporary state is O(I+U+Q), including transcript-only IDs and pending queues; O(E+S+I) time includes splice queue movement. Output is only current-turn IDs; state becomes reclaimable on return. The preexisting ModelRun retention is unchanged. Per-turn replay is still linear in full history; this unit does not promise constant-time turns or optimize actual-failure schedule scans.

## Coverage and existing test treatment

- Keep existing inputEvidence tests and all native fallback boundary tests: they protect accepted/claimed/unconsumed, queue cancellation, prepare/finish/exhaustion/context, published/tool boundary, cancellation/new input, forced runtime restart and pre-step withdrawal.
- Extend input-evidence owner suite with prefix differential ownership/order checks across both queues, replacement/negative start, duplicates, cancel, transcript-only and out-of-turn messages; one count-based performance regression guards the stated complexity boundary.
- Extend existing RuntimeClient suite with primary success, no-fallback success/error and three-attempt recovery; assert logical-run input isolation across four sequential inputs and restart. No new parallel test suite.
- Full-stack product acceptance remains separate; runtime restart evidence is not a claim of IM-level in-flight crash recovery.

## Independent gates and local checks

Independent code review and verification: PASS at `986cb0a237831795a2964e598112a501cd007d66`, executed_base `52b9a1ac831cc7f92709d12764cdd1a9410dea0f`; see unit reports. Independent true-stack product acceptance: PASS on the same tree, using IM HTTP APIs, including sequential ordinary messages, no-fallback failure, fallback/sticky reply, restart continuation and in-flight cancellation. Runtime interruption recovery and IM restart continuation are reported separately.

`pnpm typecheck`, `pnpm check:ios-runtime`, pytest non-E2E (**65 passed / 31 deselected**), ruff check, ruff format (**85 files**), docs-check (**297 sources / 67 routes**) passed. Frontend audit at critical threshold passed (existing 5 low / 2 moderate / 1 high advisories; dependencies unchanged).

First full frontend/backend attempts ran while several independent worktree suites occupied the shared machine. At 23:27 local time, load averages were 357.63 / 177.17 / 84.78; unrelated approval/tenancy/workspace-tools/frontend tests timed out. Those attempts were stopped, not reported as green. Only this unit's test processes were stopped; no other worktree processes were signaled. Serial rerun evidence follows after completion.

Isolated service cleanup: the reviewer restart helper stored a `/tmp` config path while the stop CLI resolved `/private/tmp`, so the stock down script refused identity comparison. Caller verified this unit's gateway PID 88061, DSH PID 88153, executable paths and runtime state, sent SIGTERM, confirmed both exited, saved the stale state locally and removed that stale state, then ran e2e-down to stop IM 83958. IM port 54179 released and task-owned fixture tmux stopped. This is an environment cleanup limitation; no product patch or claim of fixing that path mismatch.

The serial full-suite attempt also coincided with sustained machine overload: load 643 at 23:44 and 690.54 at 23:47, while other worktrees continued running. It produced additional timeouts in existing workspace-tools, personal-security, control-work, knowledge-policy, web-relay, trajectory-runs and providers suites. This attempt was stopped at 23:47 and is **incomplete / not passed**. No product change or timeout relaxation was made in response. Log: `/tmp/perf649-environment/backend-serial.log`. Completion requires a valid full local run (or explicit workflow adjustment) and required remote CI; the unit remains active until then.


## Frontend evidence reuse (2026-10-24)

With user-authorized cross-task coordination, reused perf-648 frontend evidence after checking exact source identity: `2c4b06abc`, `817f92040` and this unit `fd7acae2847451cda839652225267f8e3d3520aa` all have frontend tree `0432845539bbcf3bc413b54e081c5f866c033271` (including package-lock). `git diff` for the complete frontend, scripts/generate-interactive-ui.ts and packages/product-contracts is empty between both tested versions and this unit. This is shared evidence, not a claimed local execution by this unit.

Node 24.22.1, perf-648 frontend cwd: `npm run test -- --maxWorkers=1` started 23:30:43, 103 files / 963 tests, with 102 files / 962 tests passing and one permission-card-delayed timeout. The unchanged failed file was rerun using `npm run test -- --maxWorkers=1 src/features/chat/components/permission-card-delayed.test.tsx` at 23:40:56 and passed 2/2 in 6.67s. Together these cover all frontend tests, with the initial timeout disclosed; no timeout or assertion changes. Logs copied for task-owned retention: `/tmp/perf649-environment/shared-648-frontend-tests-bounded.log` and `shared-648-frontend-retry.log`. These frontend results do not substitute for this unit's changed backend runtime.
