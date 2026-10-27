# M1 — bounded automatic review recovery

- [x] Read approved design/R1 and current workflow; verify sole checkout and clean HEAD abb0eba5.
- [x] Establish meaningful RED through actual RuntimeClient approval/observe seam.
- [x] Implement shared retry owner, structured failures, independent budgets, cancellation/drain and frozen evidence.
- [x] Preserve Guardian lifecycle/native retry suppression; collect attempts and available child usage.
- [x] Verify narrow deterministic timing/risk tests, native errors and persisted observe roundtrip.
- [x] Build/typecheck, 49 affected tests and 13 dependency-boundary checks; prepare scoped commit with evidence.

## Test ownership

- `approval.test.ts`: keep routing/exemptions/deny counts; extend existing invalid fault and reopen assertions (no parallel routing suite).
- `codex-approval-native.test.ts`: keep isolation/delta/fork/inspection/failed-cache protection; rewrite real 90-second deadline fixture to deterministic accelerated clock with unchanged production 90 seconds. Extend native finish/thrown errors and provider always cap here.
- New `approval-retry.test.ts`: complete-attempt budget/mixed failures/backoff/noncooperative drain is new helper-owned behavior, tested with fake timers, not 270 seconds of wall clock.
- `approval-retry-native.test.ts`: public RuntimeClient wiring/structured native errors, frozen actual inputs and persisted/reopened observe; 148 lines, separate from pure retry arithmetic.
- `approval-cancellation.test.ts`: real pre-execute waterfall with uncooperative storage/preparation services, protecting bounded dispatch return during audit I/O; 38 lines. This failure cause cannot be deterministically exposed by the real disk fixture.
- Existing Codex lifecycle/context/unit tests remain their risk owners. Lifecycle fixtures now supply public stream records, use fake timers instead of spying on the old AbortSignal.timeout implementation, and retain native overflow semantics via structured code rather than text matching.
- CC context-window overflow keeps no_verdict/no-model/no-effect/return_to_agent protection. Its assertion now checks config category, one attempt and zero extras rather than the old raw diagnostic string.
- Guardian cancel now invalidates the trunk even when cancellation arrives after strategy completion. The native lifecycle fixture therefore correctly expects 3 seeded reviewers instead of 6: its three post-cancel deadline reviewers start full, not from a canceled trunk. Total created/disposed remains 8/8.

Product IM environment, independent reviews, final sync and acceptance remain executor-owned; worker only uses isolated native test homes.
