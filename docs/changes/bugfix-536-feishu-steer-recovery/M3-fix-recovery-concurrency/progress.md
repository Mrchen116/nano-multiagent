# bugfix-536-M3 progress

## R1 — 2026-08-13: baseline and root cause

- Baseline: `fa4fd446facb1ee0b3a9b7f5c34272e53f13f279` on
  `unit/bugfix-536`; M3 starts from the same clean head in isolated worktree
  `milestone/bugfix-536-M3`.
- Root cause confirmed: `_await_recovery_handoff()` reads an empty successor
  suffix without the transition lock, returns to the failed-successor owner,
  then `_close_active_run()` reacquires that lock. `dispatch()` can own the lock
  in between, successfully call `try_steer()` and append a follower to the
  successor. Closing pops that accepted follower, but M2 discarded the returned
  collection and the outer abort only owns the old predecessor ledger.
- Intended linearization: under the same transition lock, inspect the
  successor's unconsumed suffix and, only when it is absent, close the active
  successor and capture every follower. A dispatch admitted first becomes a
  re-handoff suffix; a dispatch after closure becomes a normal queued turn.

## R2 — in progress

- Pending implementation and deterministic lock-held regression.

## R3 — pending

- Pending focused/aggregate/static checks, isolated true-stack smoke,
  integration, push, and worker cleanup.
