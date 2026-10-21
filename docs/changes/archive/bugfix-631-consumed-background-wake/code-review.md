# Code review

- Role: independent static code reviewer; no product-code changes, verifier work, or product acceptance.
- Review mode: `full`.
- Branch: `codex/bugfix-631-consumed-background-wake`.
- Executed base: `b6050dcfc9e85209533ab11a0efd25f1358bece0`.
- Validated at / reviewed HEAD: `f3a1fb94581cba4f0e0b9e1ede0e59144c679d37`.
- Diff range: `b6050dcfc9e85209533ab11a0efd25f1358bece0...f3a1fb94581cba4f0e0b9e1ede0e59144c679d37`.
- Initial checkout status: clean; reviewed all four changed paths, including `fix.md`, the milestone placeholder, production code, and the parameterized regression test.

## Evidence

- Read the unit's `fix.md` and current `docs/specs/gateway/personal-agent.md` scenarios for background batching, busy deferral, early consumption, and independent notification/consumption.
- Traced `GlobalAgent.notifyBackground`, its wake/timer/idle callers, `InboxStore.background` / `prepareBackground` / `admitBackground` / `commitRead`, and the runtime's `session.lookup` and `session.submit` handlers.
- The final batch read now follows the asynchronous runtime observation. A fully consumed, unreserved batch returns no batch and clears the idle-wait marker; a remaining unread batch proceeds synchronously to identity reservation and submission. Runtime `onlyIfIdle` still checks actual admission state, and an uncertain prior admission retains its original identity and lookup recovery.
- The test extends the existing consumption-cancellation scenario to consumption during idle observation, and verifies that later new background still notifies. Existing tests retain unread batching, busy/admission-race handling, direct steering, uncertain ACK recovery, source revocation, and timer shutdown coverage.
- Reused the implementation evidence recorded in `fix.md`: original implementation fails the new observation-window case; corrected implementation passes the three affected files with 56 tests.
- Independently ran `pnpm exec vitest run packages/personal-assistant/tests/personal-attention.test.ts` at the reviewed HEAD: 1 file, 8 tests passed. `git diff --check` for the reviewed range passed.

## Conclusion

No actionable correctness, contract, complexity, or runtime-cost defects found in the specified diff. This review does not claim production deployment or real-user acceptance.

```json
[]
```
