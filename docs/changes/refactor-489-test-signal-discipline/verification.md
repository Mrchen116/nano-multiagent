# Verification Report: refactor-489

> Validation snapshot: `0b9607147df21e6e11e1c7b27cccba6005ce6ab6 → e8f31eb47fa1c75183868cf92591173ea82a7d85`

## Summary

Mode: `full`  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 16/16 milestone task records complete; 14/16 exit surfaces independently green, with two release-blocking warnings below |
| Correctness | 3/3 motivation requirements traced; final quality/live execution has two warnings |
| Coherence | Followed, except the M13 live-run environment is not self-contained |

## Completeness

- Tasks: all 16 `M*/tasks.md` files exist, each contains the required affected-test disposition table, and none contains an unchecked exit criterion (64 checked exit criteria total). Each has a corresponding `progress.md` with completed roadpoints.
- Milestones: M1 establishes the durable protocol; M2--M13 cover Python, contracts, CI, helpers and operational E2E; M14--M16 cover all frontend Vitest partitions. The final diff changes 374 paths from `executed_base`, and it contains no non-test `src/` product implementation change.
- Current authority: the M1 rule is owned by [`docs/development/testing.md`](../../development/testing.md#L15-L25); the worker skill routes to it and requires a per-milestone disposition in [`.claude/skills/change-impl-worker/SKILL.md`](../../../.claude/skills/change-impl-worker/SKILL.md#L192-L206); the copied task template provides the five-column table in [`.claude/skills/change-impl-worker/assets/tasks.md`](../../../.claude/skills/change-impl-worker/assets/tasks.md#L31-L42).
- Prototype / Reference coverage: N/A. This is a zero-user-surface testing-asset unit; the three frontend milestones explicitly contain no UI/product delta or reference contract.

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Maintenance refactors of prompts, docs, or internal structure do not fail only on historic noise | [`docs/development/testing.md`](../../development/testing.md#L15-L25) defines `keep` / `rewrite-merge` / `delete` and forbids text/layout/tombstone assertions as a reason to keep a test; M2--M16 each record its application | 16 completed disposition records; Python non-E2E lane passed 2,836 collected items; frontend Vitest passed 59 files / 555 tests | covered, subject to formatter warning W1 |
| A real user, public, operational, or architecture risk remains protected at the lowest adequate layer | Contract AST checks, unit/integration seam tests, and real-stack E2E are retained according to the per-domain tables; M13 records the genuine process/port/config/workspace routes in [`M13 tasks`](M13-operational-e2e/tasks.md#L17-L43) | `pytest -m "not e2e" -n 4 --dist worksteal` passed; E2E catalog collected all 20 nodes; lifecycle and fake-LLM true-stack paths passed; `#126` remains a strict tracked xfail | covered, subject to live-path warning W2 |
| Cleaned quality gates fail only for a real risk or executable rule | CI retains docs, Ruff lint/format, pytest, and frontend Vitest at [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml#L30-L40) | docs-check and Ruff lint passed; frontend Vitest and build passed; Ruff format check fails | **warning W1** |
| Worker changing an implementation path or test boundary records the disposition and lowest true regression protection | M1 exit criteria and its own disposition table are explicit in [`M1 tasks`](M1-test-discipline/tasks.md#L9-L30); the long-lived template has the same interface | workflow contract is included in the passed Python lane; all 16 actual milestone task files use the table | covered |

The strict xfail for known product bug `#126` is correctly retained with `strict=True` and a tracked reason in [`test_heartbeat_bubble_critical_path.py`](../../../tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py#L29-L35). Its GitHub issue is open. M7 also records the separate expired-`at` finding as out-of-unit rather than deleting the contrary regression test.

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. Every affected existing test receives `keep` / `rewrite-merge` / `delete`; no whole-repository ledger | 是 | Canonical rule at [`testing.md`](../../development/testing.md#L15-L25), required worker planning step at [`SKILL.md`](../../../.claude/skills/change-impl-worker/SKILL.md#L192-L198), and all 16 actual `tasks.md` records contain the five-column table. |
| 2. One risk is owned at the lowest adequate layer; higher layers verify only the connection | 是 | The design states this at [`design.md`](design.md#L72-L78); M9 retains `build_kernel`/registry/provider connections while citing lower owners, and M13 retains true-process tests instead of script-text tests at [`M13 tasks`](M13-operational-e2e/tasks.md#L29-L43). |
| 3. M1 first, then non-overlapping M2--M16 test slices with integration audit | 是 | The path ownership matrix is explicit at [`design.md`](design.md#L129-L150); every planned slice has a completed task/progress record. The M9 shared-harness collection failure was repaired in its owner rather than silently skipped. |

Architecture boundaries remain intact: no production `src/` behavior was changed by this unit, and the final Python lane includes the current contract tests. No parallel runtime mechanism or cross-product import was introduced.

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

- **W1 — The final CI formatter gate is red.** [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml#L36-L37) requires `ruff format --check .`, but it exits `1` at the validated snapshot and reports 20 test files that would be reformatted, all changed by this unit (for example [`tests/e2e/test_worktree_stack_lifecycle_e2e.py`](../../../tests/e2e/test_worktree_stack_lifecycle_e2e.py#L1), [`tests/im_service/unit/test_message_runtime_state.py`](../../../tests/im_service/unit/test_message_runtime_state.py#L1), and [`tests/unit/test_auto_mode_gate.py`](../../../tests/unit/test_auto_mode_gate.py#L1)). This directly violates the M2 quality-gate exit criterion and blocks CI. Run Ruff format on the reported files, commit only those formatting changes, then rerun `ruff format --check .` together with the complete Python CI lane.

- **W2 — The M13 resilience critical path only works when the caller manually prepends the repo venv to `PATH`.** The test gates only the opt-in flag and main config at [`test_gateway_im_resilience_critical_path.py`](../../../tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py#L31-L41), then launches the shell script without an environment override at [lines 87-98](../../../tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py#L87-L98). That script invokes bare `python3` for its YAML-dependent config setup at [`scripts/e2e-resilience.sh`](../../../scripts/e2e-resilience.sh#L166-L186). Reproduction with the repository interpreter but ordinary PATH: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .venv/bin/python -m pytest -q ...::test_gateway_recovers_node_online_after_transient_faults` fails in 0.33s with `ModuleNotFoundError: No module named 'yaml'`. The identical command passes (1 passed, 25.19s) only after manually prefixing `.venv/bin` to PATH. This contradicts the M13 claim that resilience has a usable non-proxy live path and differs from the lifecycle test, which explicitly propagates `Path(sys.executable).parent` at [`test_worktree_stack_lifecycle_e2e.py`](../../../tests/e2e/test_worktree_stack_lifecycle_e2e.py#L53-L69). Pass that PATH in the resilience test's `Popen` environment (or pass an explicit interpreter through the script), and add/re-run the standard repo-venv invocation without an external PATH workaround.

### SUGGESTION（可以修）

None.

2 warning(s) found. Fix before PR.

# Round 2

> Targeted closure snapshot: `0b9607147df21e6e11e1c7b27cccba6005ce6ab6 → bde0ed1b050fe934c4461fdcd81e842e83784cbb`
> Fix delta: `ac281030314477c44098d5888506674236a83e5e..bde0ed1b050fe934c4461fdcd81e842e83784cbb`

## Summary

Mode: `targeted-closure`
Focus issues: W1 (final Ruff format gate), W2 (ordinary-PATH resilience invocation)
requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | M17 records exactly the two prior warnings, formats the 20 W1 files, and changes the W2 subprocess environment; both listed exit surfaces were independently re-run. |
| Correctness | `ruff format --check .` passes over 812 files; the opt-in true-stack resilience node passes with the ordinary shell PATH, where `python3` resolves to `/usr/bin/python3`. |
| Coherence | The fix preserves the prior test-only boundary: no `src/`, script, CI, current-spec, or design change is in the fix delta. |

## Focused verification

| Prior issue / requirement | Implementation and boundary | Independent evidence | Status |
|---|---|---|---|
| W1 — CI format gate is executable and green | The delta formats only the 20 reported test files; the CI command remains [`ruff format --check .`](../../../.github/workflows/ci.yml#L36-L37). | `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff format --check .` → `812 files already formatted` (exit 0). `ruff check .` also returned `All checks passed!`. | pass |
| W2 — M13 resilience path runs without caller PATH setup | [`_run_resilience_script`](../../../tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py#L45-L65) prepends `Path(sys.executable).parent` only to the spawned script's `PATH`, so its bare `python3` resolves to the same repository interpreter as pytest. | With the inherited ordinary PATH unchanged (`python3` = `/usr/bin/python3`), `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .venv/bin/python -m pytest -q -rs tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py::test_gateway_recovers_node_online_after_transient_faults` → `1 passed in 24.25s`. | pass |

The focused live run left no matching `e2e-resilience.sh`, verification-worktree, or resilience temporary-worktree process. The two listeners observed afterward were pre-existing user services: the LLM proxy on port 4000 and the main `personal_assistant` process on port 57040; neither command line points to this verification worktree or the test temporary directory.

`./scripts/docs-check` also passed (`223 maintained Markdown sources`, `65 required routes`), and `git diff --check ac2810303..bde0ed1b0` was clean.

## Scope and verification mode

The fix delta changes 23 paths: two M17 records, the 20 W1 formatting-only tests, and the W2 resilience test harness. It contains no `src/`, `scripts/`, `.github/`, `docs/specs/`, `SPEC.md`, dependency, configuration, architecture, cross-machine, or parallel-runtime mechanism change. It therefore does not invalidate the independent full evidence already recorded in Round 1 and does not require escalation to full verification.

The W2 change follows the existing lifecycle-test interpreter-propagation pattern while preserving the M13 contract: a real shell-driven IM/Gateway recovery journey remains the owner of the operational risk, rather than replacing it with a script-text assertion.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

All focused checks passed. Ready for PR.
