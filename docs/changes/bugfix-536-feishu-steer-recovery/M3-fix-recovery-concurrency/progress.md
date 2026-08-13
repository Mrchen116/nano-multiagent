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

## R2 — 2026-08-13: atomic close and deterministic race

- Added `_close_active_run_locked()` and
  `_close_failed_successor_without_suffix()` in the coordinator. The latter
  checks the unconsumed successor suffix and closes/captures the active run
  while still holding the same transition lock used by `dispatch()`.
- The failed-successor owner emits a terminal failure for every captured
  concurrent follower. If a dispatch completed admission first, the helper
  instead returns `None` and preserves the existing nested re-handoff path.
- Added `test_recovery_handoff_concurrency.py`. Its blocking image resolver
  holds `dispatch()` inside transition preparation while the successor receives
  its failed terminal event. The dispatch then calls `try_steer()` and appends
  its follower before releasing the lock. The test drives a valid `run-3`
  recovery descriptor/settlement and asserts the racing follower has exactly
  one accepted and one completed lifecycle, no duplicate terminal, released
  busy state, and a following ordinary reply. The existing M2 no-suffix test
  remains the failure-settlement companion.
- Focused recovery validation:
  `pytest -q tests/unit/personal_assistant/test_recovery_handoff.py
  tests/unit/personal_assistant/test_recovery_handoff_coordinator.py
  tests/unit/personal_assistant/test_recovery_handoff_concurrency.py
  tests/integration/test_session_run_coordinator_recovery.py` →
  `14 passed in 2.55s`.
- M1/M2 aggregate plus this regression:
  `pytest -q` over the named compaction, Kernel pending/terminal/registry,
  SDK contract, coordinator admission/terminal/steer/lifecycle/recovery,
  real-Kernel recovery/reset suites → `162 passed in 13.56s`.

## R3 — 2026-08-13: validation and true-stack smoke

- `ruff check` and `ruff format --check` for the changed coordinator/test files
  passed. `scripts/docs_check.py` passed (`226 maintained Markdown sources,
  70 required routes`), and both baseline-to-HEAD and working-tree
  `git diff --check` were clean.
- Isolated true stack: `scripts/e2e-up.sh --wt` started IM on `53689` and
  Gateway pid `76807`; the public Web IM REST relay created conversation
  `85de0bffec0542849e6b232400c0004c` and received the exact normal reply
  `M3-SMOKE-CFA12398`. `scripts/e2e-down.sh --wt` ran through the shell trap;
  no `.im.pid`, `.gateway.pid`, or `.e2e-ports.env` remained. This smoke proves
  the common user entry still replies; the rare successor interleaving remains
  covered by the deterministic coordinator test above.
- No approved design or delta-spec changed: the fix only linearizes the existing
  Gateway logical-owner rule from Design Decision 3.
- M3 plan `9b2da8c4c` and implementation/evidence `8da962db8` were merged as
  unit commit `e49b64101` (`merge: bugfix-536 M3 recovery closure race`) and
  pushed to `origin/unit/bugfix-536`. Post-merge
  `git diff --check fa4fd446..e49b64101` passed; the exact range changes four
  files (`344 insertions`, `22 deletions`).
- Worker worktree/branch cleanup follows this final evidence-record commit; no
  service process or generated e2e PID/config file is retained.
