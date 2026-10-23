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
