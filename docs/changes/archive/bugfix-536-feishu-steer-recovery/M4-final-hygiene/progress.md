# bugfix-536-M4 progress

## R1 — 2026-08-13: scope and baseline

- Pre-fix head: `62c2f24110b2f98cf7eb30aef6849bffd603c752`; local and remote
  `unit/bugfix-536` matched before the isolated M4 worktree was created.
- The Round 3 verifier identified exactly two full-repository formatter drifts:
  `src/personal_assistant/gateway/inbound_models.py` and
  `tests/contract/test_kernel_sdk_behavior_contract.py`. The pre-change
  `ruff format --check` on only those paths reported exactly those two files.
- `liveness.py` behaviour already covers tool, LLM, permission, and compaction
  windows. Its module and API docstrings were stale; this M4 change is wording
  only. No new regression test is appropriate for documentation and mechanical
  formatting.
- M3 already has the concurrency regression at its lowest observable owner;
  its task record lacks the required testing strategy and affected-test
  disposition. M4 documents that ownership without changing test behavior.

## R2 — 2026-08-13: exact hygiene changes

- Ran repository Ruff's formatter on exactly the two named paths. Its only
  mechanical changes collapse the `RelayLifecycleUpdate.phase` `Literal` and
  wrap the contract-test continuation comprehension; no other file was passed
  to the formatting command.
- Updated only `liveness.py` documentation: the module now names long tool,
  non-stream LLM, permission, and parent-compaction waits, distinguishes the
  execution-update projection from direct heartbeats, and includes
  `"compaction"` in the `liveness_ticker` source examples. Runtime code is
  unchanged.
- Added the missing M3 testing strategy and affected-test table. It assigns the
  lock-held admission-wins interleaving to
  `test_recovery_handoff_concurrency.py`; the existing coordinator tests retain
  distinct no-suffix terminal/release, normal same-run, and control/shutdown
  responsibilities.

## R3 — 2026-08-13: gates

- Focused tests:
  `pytest -q tests/unit/test_liveness_ticker.py tests/unit/test_loop_compact.py
  tests/contract/test_kernel_sdk_behavior_contract.py
  tests/unit/personal_assistant/test_recovery_handoff_coordinator.py
  tests/unit/personal_assistant/test_recovery_handoff_concurrency.py` →
  `64 passed in 3.18s`.
- Required gates: `ruff format --check .` → `953 files already formatted`;
  `ruff check` on the three changed Python files passed;
  `scripts/docs_check.py` → `228 maintained Markdown sources, 70 required
  routes`; `git diff --check` passed.
- FL reuse: as the original M1–M3 worker, omitted a red test and a fresh
  runtime smoke because this M4 has only mechanical formatting and stale
  documentation corrections; focused existing tests and the full formatter
  gate protect the affected seams.
- M4 material range: `62c2f24110b2f98cf7eb30aef6849bffd603c752..4470ac10a3e702289bb07be44917d87349c5ea7c`.
  It comprises plan `62beb233c`, implementation `94ba411c6`, and the first
  no-ff unit integration `4470ac10a`; no code, test behavior, report, design,
  or delta-spec changed outside the declared scope.
- Exact validation commands run before integration:
  `pytest -q tests/unit/test_liveness_ticker.py tests/unit/test_loop_compact.py
  tests/contract/test_kernel_sdk_behavior_contract.py
  tests/unit/personal_assistant/test_recovery_handoff_coordinator.py
  tests/unit/personal_assistant/test_recovery_handoff_concurrency.py`;
  `ruff format --check .`; `ruff check
  src/personal_assistant/gateway/inbound_models.py
  tests/contract/test_kernel_sdk_behavior_contract.py
  src/agent/core/agent/liveness.py`; `python scripts/docs_check.py`; and
  `git diff --check origin/unit/bugfix-536..HEAD`.
- The first integration was pushed to `origin/unit/bugfix-536`; this final
  evidence record is documentation-only. No service was started, so no runtime
  process or port cleanup was required; the worktree and milestone branch are
  removed after this record is integrated.
