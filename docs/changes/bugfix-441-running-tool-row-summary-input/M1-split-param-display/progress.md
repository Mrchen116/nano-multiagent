# bugfix-441-M1 — Progress

## Baseline

- Sync Gate: `unit/bugfix-441` and `origin/unit/bugfix-441` both at `6badaebfa9a43a31e05b3d2cbb44e001b04e7f3c`.
- Worktree: created `/Users/czj/Repos/nano-multiagent/.worktrees/bugfix-441-M1` from `origin/unit/bugfix-441` on branch `milestone/bugfix-441-M1`.
- Baseline tests:
  - `pytest -m "not e2e"` under sandbox: 2970 passed, 1 skipped, 20 deselected, 9 failed. Failures were pre-change process-table/network-permission symptoms (`ps`/`pgrep` denied, web_search provider path).
  - Failing subset rerun unsandboxed: `pytest tests/integration/test_foreground_interrupt_reap.py::test_interrupt_reaps_foreground_subprocess_and_self_heals tests/unit/agent/background_tasks/test_platform_adapters.py::test_shell_runner_runs_in_dedicated_process_group tests/unit/personal_assistant/test_web_search_tool.py::test_web_search_returns_results_when_ddgs_available tests/unit/test_e2e_conftest_finalizer.py` → 10 passed.
  - `npm ci` installed frontend dependencies in the milestone worktree.
  - `npm run test` in `src/IM/frontend`: 60 files / 485 tests passed.
  - `npm run build` in `src/IM/frontend`: passed with existing chunk-size/dynamic-import warnings.

## R1 — presenters and gateway relay

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R2 frontend running gate.

## R2 — frontend running gate and reducer overwrite

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R3 full gates and live IM Web evidence.

## R3 — full gates and live IM Web evidence

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: milestone integration.
