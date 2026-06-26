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

- Context: Running tool rows already received presenter `emoji`, but `summary` and `detail` were dropped at two points: existing `format_start` methods usually emitted no parameter detail, and Gateway `tool_start` only forwarded `emoji`. M1 requires parameter-side presentation to reach IM before result-side fields exist.
- Decision: Added `format_start.detail` for all scoped builtin presenters plus product `web_search`; added product-owned presenters for `send_message` and `cron`; forwarded Gateway `tool_start` `presentation.summary` to `tool_call.output` and `presentation.detail` to `tool_call.detail`. Large input content in write/memory start detail reuses `_enforce_cap`.
- Rationale: The implementation keeps presenter ownership of display data and leaves `format_end` / `tool_end` behavior unchanged. Gateway stays a pure passthrough pipe, mirroring the existing tool_end mapping for running deltas.
- Evidence:
  - Tests: C1 red: `pytest tests/unit/platform/tools/test_presentation.py tests/unit/platform/tools/test_presentation_cap.py tests/unit/personal_assistant/test_web_search_presenter.py tests/unit/personal_assistant/test_send_message_tool.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` → 18 failed / 64 passed, all failures at missing start detail, missing PA presenters, or missing Gateway start output/detail. C2 green: same command → 82 passed.
  - Entry: Gateway observer unit drives the real `_build_kernel_event_observer` with a `tool_start` event and verifies the IM `tool_call_upserted` payload includes `output` and `detail`. Product presenter tests verify send_message/cron structured display through their actual tool classes.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Permanent regression tests added in existing unit files; true browser IM evidence is scheduled for R3 because R1 does not yet include frontend running gate.
  - Visual/Interaction: N/A
- Rollback: Revert `6102c325` to remove R1 implementation; revert `2d6b846e` to remove the red-test coverage.
- Commits: C1=2d6b846e, C2=6102c325, C3=TODO
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
