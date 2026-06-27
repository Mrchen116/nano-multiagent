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
- Commits: C1=2d6b846e, C2=6102c325, C3=61d34415
- Next: R2 frontend running gate.

## R2 — frontend running gate and reducer overwrite

- Context: R1 makes running rows carry presenter `output` + parameter-side `detail`, but `ToolDetailBody` rendered every known card as if detail were final result detail. That made running `web_search` show the completed empty-results state, `agent` show `✓ completed`, and memory/skill/task_stop show success markers before completion.
- Decision: Threaded `call.status === "running"` into the bespoke detail cards and gated only the result/status subregions for `web_search`, `agent`, `memory`, `skill_manage`, and `task_stop`. Completed and failed cards keep their existing render branches. Added a reducer regression that a completion event replaces the running `output/detail` with final `output/detail`.
- Rationale: The gate belongs at the renderer boundary because the protocol correctly distinguishes running vs completed through `ToolCall.status`. This keeps persisted/historical completed messages stable and avoids inventing front-end fallbacks for presenter-owned fields.
- Evidence:
  - Tests: C1 red: `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx src/features/chat/v2/chat-stream-reducer.test.ts` → reducer file 18 passed; panel file 5 new failures / 60 existing passed. Failures matched the intended missing gate: running `web_search` showed "No results"; running `agent` rendered `.chat-tool-detail-agent-result` with `✓ sub-agent completed`; running memory/skill/task_stop showed `✓` completed heads. C2 green: same command → 2 files passed, 83 tests passed.
  - Entry: `ToolDetailBody` now passes `isRunning` to bespoke cards; `chat-stream-reducer.test.ts` covers `tool_call.completed` replacing the running summary/detail, not merging stale parameter detail into the result.
  - Frontend State Matrix: loading/running covered for `web_search`, `agent`, `memory`, `skill_manage`, `task_stop`; empty covered by completed `web_search` empty-state test plus running `web_search` no-empty-state test; default/completed and error states remain covered by existing card tests; long content remains covered by existing long-output tests; missing/nullable result fields covered by running cards that carry only parameter fields.
  - Browser QA: deferred to R3 true IM Web UI run, because R2 is the component-level gate and R3 owns live running/completed screenshots.
  - E2E/Regression: Permanent vitest coverage added for running gate and reducer overwrite. True stack browser evidence still pending R3 before DONE.
  - Visual/Interaction: Running cards now display only parameter text in the expanded body: query, prompt, action/target/content, action/name, or task id. No completed marker or empty-result placeholder renders until status changes.
- Rollback: Revert `fbb0d818` to remove R2 implementation; revert `a73d6bad` to remove R2 red-test coverage.
- Commits: C1=a73d6bad, C2=fbb0d818, C3=this docs commit
- Next: R3 full gates and live IM Web evidence.

## R3 — full gates and live IM Web evidence

- Context: R1/R2 implementation is complete. Full pytest initially exposed one missed contract update in `test_presentation_golden.py`: the golden start tuples still expected `detail=None` for builtin tools. Updating that golden is required because M1 intentionally changes the start-event contract to include parameter detail.
- Decision: Updated the presentation golden start cases to expect parameter-side detail for read/write/edit/bash/web_fetch/agent, while keeping unknown fallback detail as `None`. After the escalated execution limit recovered, started the worktree true stack and drove Chromium through the real IM Web UI for long bash, agent subtask, and web_search running/completed states.
- Rationale: The golden update keeps the broad regression suite aligned with the new M1 contract. The true-stack UI path proves the full presenter -> Gateway -> IM persistence/WS -> React renderer chain, including the running gate that unit tests alone cannot demonstrate.
- Evidence:
  - Tests: `pytest tests/unit/platform/tools/test_presentation_golden.py` → 14 passed. `pytest -m "not e2e"` first R3 run → 6 failed in `tests/unit/platform/tools/test_presentation_golden.py` only; after golden update → 2989 passed, 1 skipped, 20 deselected, 13 warnings. Frontend `npm run test` → 60 files / 491 tests passed. Frontend `npm run build` → passed with existing dynamic-import/chunk-size warnings.
  - Entry: R3 broad gates exercise the full presenter/gateway/frontend test surface added in R1/R2 plus the existing golden contract suite.
  - Frontend State Matrix: Unit/vitest coverage is green for loading/running, empty, default/completed, error, long content, and missing/nullable detail. True browser coverage confirms desktop running/completed states in the real app shell.
  - Browser QA: re-ran true stack from the unit worktree after milestone cleanup, with IM at `http://127.0.0.1:59470`, Gateway `--foreground --auto-bind` pid `60173`, node `wt-unit-bugfix-441-60045`, and Vite at `http://127.0.0.1:50065/` proxying that IM. Chromium drove the authenticated Web IM against `default-agent` (`agent_user_id=21e6945f02d9466d81aa98ebab074073`). Repro metadata is committed at `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/metadata.json`.
  - Browser QA screenshots:
    - bash running: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/bugfix-441-M1-bash-running.png`
    - bash completed: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/bugfix-441-M1-bash-completed.png`
    - agent running: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/bugfix-441-M1-agent-running.png`
    - agent completed: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/bugfix-441-M1-agent-completed.png`
    - web_search running: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/bugfix-441-M1-web-search-running.png`
    - web_search completed: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/bugfix-441-M1-web-search-completed.png`
  - E2E/Regression: bash conversation `e8f1c2c0e3094fbea034bd273da0f53a`, user message `329fefac1b3a4ea39a66ef51bcf538c9`, agent message `b4beac2ef0514022b1c0093e9c612fde`, ran `sleep 20 && echo BUGFIX441_BASH_UNIT_EVIDENCE_RERUN4` and completed with sentinel `BUGFIX441_BASH_UNIT_EVIDENCE_RERUN4`. Agent conversation `216ddf448d15404ea90d4c512329d186`, user message `b1434799ec734f96a50d5d01680ff3ce`, agent message `cf41823b4aed45a99aa0b330e35be3ad`, captured prompt `sleep 25 && echo BUGFIX441_AGENT_UNIT_EVIDENCE_RERUN5` and final sentinel `BUGFIX441_AGENT_UNIT_EVIDENCE_RERUN5`. Web_search conversation `4a6b9fa3f91940efaa7d4308fc0353a2`, user message `e8fa6380844445bb9b793d54c679565e`, running agent message `6bc1901e883d433095da8004513b9c74`, completed agent message `fcd250669fed468f8bf48ee0188ba3c9`, captured query `bugfix-441 running tool row summary input nano-multiagent` and final sentinel `BUGFIX441_WEB_SEARCH_UNIT_EVIDENCE_RERUN4`.
  - Visual/Interaction: bash running screenshot shows `1 tool call · running`, expanded `bash` with command `sleep 20 && echo BUGFIX441_BASH_UNIT_EVIDENCE_RERUN4`, and no output/completion marker. Agent running screenshot shows `1 tool call · running`, expanded `agent` dispatch prompt with `sleep 25 && echo BUGFIX441_AGENT_UNIT_EVIDENCE_RERUN5`, and no completed result marker. Web_search running screenshot shows `1 tool call · running`, expanded query, and no `No results` empty state. Completed screenshots show the same rows after tool completion with parameter plus result detail visible.
- Rollback: Revert `4b55404b` to restore the old golden expectations; revert R2/R1 commits listed above for implementation rollback.
- Commits: C1=4b55404b, C2=live IM Web UI evidence, C3=this docs update
- Next: Merge milestone branch into `unit/bugfix-441`, push, and clean milestone worktree/branch.
