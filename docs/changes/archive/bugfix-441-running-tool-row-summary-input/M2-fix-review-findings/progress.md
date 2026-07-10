# bugfix-441-M2 — Progress

## Baseline

- Sync Gate: `unit/bugfix-441` and `origin/unit/bugfix-441` both at `57fa4a072531fdccaed150b7deca93cf54b7877d`.
- Worktree: created `/Users/czj/Repos/nano-multiagent/.worktrees/bugfix-441-M2` from `origin/unit/bugfix-441` on branch `milestone/bugfix-441-M2`.
- Baseline tests: `pytest -q tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py tests/unit/personal_assistant/test_cron_tool_closure.py` -> 19 passed.

## R1 — reviewer blocking fixes

- Context: M1 `tool_start` now forwards `output`/`detail`/`emoji`, but the abnormal reconcile cache still only remembered `name/input`; a stalled/interrupted tool could therefore lose its parameter-side display in the synthetic failed completion payload. Cron also returned in-band failures as `{ok:false,error}` while the presenter emitted no `success:false` signal, so the frontend's existing failure detector could still treat the row as a completed success.
- Decision: Store start-side `output`/`detail`/`emoji` alongside `name/input` in `running_tool_calls`; reconcile re-emits those fields while still forcing `status=failed` and `reason`, and `/stop` attribution content overrides only `output`. Cron result detail now maps `ok` to `success`, and preserves in-band `error` as `success:false` + `error`.
- Rationale: The Gateway remains a passthrough pipe and keeps the same abnormal-close contract: only terminal status/reason are synthesized. The cron change aligns with the frontend's existing generic failure predicate (`detail.success === false`) instead of adding a cron-specific renderer.
- Evidence:
  - Tests: C1 red `pytest -q tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` -> 4 failed / 19 passed, failing exactly on missing reconcile `output/detail` and missing cron `success`. C2 green same command -> 23 passed. Wider PA subset `pytest -q tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py tests/unit/personal_assistant/test_inbound_pipeline_user_interrupt_content.py` -> 35 passed. `git diff --check` -> passed.
  - Entry: Gateway observer unit drives real `_build_kernel_event_observer` events through `tool_start` -> `run_terminal_reconcile` and inspects emitted `node.streaming_delta` payloads. Cron presenter unit drives the actual `CronTool.presenter.format_end` for success and in-band failure outputs.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Permanent regression coverage added in existing unit files. No browser QA required because M2 does not change frontend rendering; it produces the existing frontend-recognized `success:false` failure signal.
  - Visual/Interaction: N/A
- Rollback: Revert `e7347040` to remove implementation and cron expectation update; revert `8e255acf` to remove red tests and M2 planning docs.
- Commits: C1=8e255acf, C2=e7347040, C3=this docs commit
- Next: Merge milestone branch into `unit/bugfix-441`, push, and clean milestone worktree/branch.
