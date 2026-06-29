# Verification Report: bugfix-441

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete; 8/8 incident requirements covered |
| Correctness | 7/7 scenarios covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: 10/10 complete. `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/tasks.md` marks every exit criterion complete, including live IM Web UI evidence, all scoped presenters, gateway relay, frontend running gate, reducer overwrite, and broad test/build gates.
- Requirement coverage: covered.
  - Running collapsed rows receive parameter summaries via presenter start detail and Gateway `tool_start` forwarding: `src/agent/platform/tools/builtins/bash.py:95`, `src/personal_assistant/main.py:3697`.
  - Running expanded rows receive parameter detail from builtin/product presenters: `src/agent/platform/tools/builtins/write.py:25`, `src/agent/platform/tools/builtins/agent.py:48`, `src/personal_assistant/tools/web_search.py:47`, `src/personal_assistant/tools/send_message.py:21`, `src/personal_assistant/tools/cron.py:281`.
  - Running result/completion markers are gated in the frontend: `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:263`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:305`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:390`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:431`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:464`.
  - Completion replaces running parameter detail with final result detail through normal reducer merging: `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts:67`.
  - Large parameter content is capped for write/memory start detail: `src/agent/platform/tools/builtins/write.py:31`, `src/agent/platform/tools/builtins/memory.py:51`.
  - `send_message` and `cron` have product-owned presenters and structured GenericCard-compatible detail: `src/personal_assistant/tools/send_message.py:18`, `src/personal_assistant/tools/cron.py:278`.
  - Contract deltas are documented for kernel, gateway, and IM under `docs/changes/bugfix-441-running-tool-row-summary-input/specs/`.
  - Live IM evidence is committed: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/progress.md:51`.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 工具执行中折叠行显示参数摘要 | `src/personal_assistant/main.py:3697` forwards `presentation.summary` into `tool_call.output`; builtin/product presenters emit start summaries, e.g. `src/agent/platform/tools/builtins/bash.py:100` and `src/personal_assistant/tools/web_search.py:48`. | `tests/unit/personal_assistant/test_tool_end_detail_passthrough.py:193`; live UI evidence in `progress.md:55`. | covered |
| 工具执行中展开卡显示参数 detail | `format_start.detail` is present across builtin/product presenters, e.g. `read.py:44`, `bash.py:95`, `agent.py:48`, `send_message.py:21`, `cron.py:281`; Gateway forwards it at `main.py:3700`. | `tests/unit/platform/tools/test_presentation.py:39`; `tests/unit/personal_assistant/test_send_message_tool.py:77`; `tests/unit/personal_assistant/test_cron_tool_closure.py:129`; live UI evidence in `progress.md:56`. | covered |
| 工具执行中不显示结果或完成标记 | `ToolDetailBody` passes `isRunning` at `tool-detail-renderers.tsx:544`; cards gate result regions for web_search, agent, memory, skill_manage, and task_stop. | `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx:454`, `:469`, `:484`, `:499`, `:513`; live UI evidence in `progress.md:64`. | covered |
| 工具完成后显示参数 + 结果全貌,且非 send_message/cron 完成态保持旧路径 | `format_end` paths remain the source of full detail; reducer completion overwrites running `output/detail` when final values arrive. | `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts:139`; presenter end tests in `tests/unit/platform/tools/test_presentation.py:47` and following sections. | covered |
| send_message/cron 完成态有意结构化改善,信息不少于旧裸 JSON | `send_message` end detail includes target/text/status at `send_message.py:49`; `cron` end detail merges params and result fields at `cron.py:296` and `_cron_result_detail` at `cron.py:631`. | `tests/unit/personal_assistant/test_send_message_tool.py:77`; `tests/unit/personal_assistant/test_cron_tool_closure.py:129`. | covered |
| 大字段参数片复用 cap,避免 running event/detail 撑爆链路 | `write` and `memory` start detail call `_enforce_cap`. | `tests/unit/platform/tools/test_presentation_cap.py:42`, `:55`. | covered |
| tool_end 覆盖 tool_start,避免参数片残留或错位 | Reducer spreads final event over existing call, preserving only empty input/output special cases; `detail` is replaced by final detail. | `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts:139`. | covered |

Verification commands run in this verifier worktree:

- `PYTHONDONTWRITEBYTECODE=1 pytest -q tests/unit/platform/tools/test_presentation.py tests/unit/platform/tools/test_presentation_cap.py tests/unit/platform/tools/test_presentation_golden.py tests/unit/personal_assistant/test_web_search_presenter.py tests/unit/personal_assistant/test_send_message_tool.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` -> 96 passed.

Frontend verification note:

- I attempted `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx src/features/chat/v2/chat-stream-reducer.test.ts` in the verifier worktree, but this worktree has no installed `vitest` binary (`/bin/sh: vitest: command not found`). I did not install dependencies or modify dependency state. The submitted milestone evidence records `npm run test` as 60 files / 491 tests passed and `npm run build` passed at `progress.md:52`; the relevant frontend test assertions are committed at `tool-calls-panel.test.tsx:454` and `chat-stream-reducer.test.ts:139`.

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: `format_start` 补参数片 detail, Gateway 镜像转发, 前端 running gate, 结束路径不动 | 是 | Presenter start detail exists in `bash.py:95` and peers; Gateway mirrors summary/detail at `main.py:3697`; frontend gates at `tool-detail-renderers.tsx:544`. |
| 决策 2: 切分由 presenter 自身负责,现有全部工具逐分支对齐,大字段 cap | 是 | Builtin/product presenters own display data; `write.py:31` and `memory.py:51` reuse `_enforce_cap`; tests cover scoped presenters. |
| 决策 3: summary 纯转发,不另造语义 | 是 | Gateway maps `presentation.summary` to `output` without tool-specific logic at `main.py:3697`; tool_end mapping remains analogous at `main.py:3765`. |
| 架构边界: Gateway/PA 只通过 `agent.sdk` 产品接口使用 tool presentation; IM 不反向调用 agent | 是 | Product tools import `ToolPresentationEvent` from `agent.sdk` (`send_message.py:15`, `cron.py:33`, `web_search.py:13`); frontend only consumes IM `ToolCall.detail`. |
| 测试规范: 永久回归落在现有最低层文件,真栈截图作为一次性证据 | 是 | Existing unit/vitest files are extended; live screenshots and metadata are under unit progress/evidence, matching `docs/TESTING_GUIDE.md` temporary evidence guidance. |

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（应该修）

- None.

### SUGGESTION（可以修）

- None.

# Round 2

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 10/10 tasks complete; M2 6/6 tasks complete; incident/design requirements covered |
| Correctness | 10/10 scenarios covered, including round 1 blockers |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: M1 remains 10/10 complete and M2 is 6/6 complete. `docs/changes/bugfix-441-running-tool-row-summary-input/M2-fix-review-findings/tasks.md` marks all exit criteria complete: abnormal reconcile preserves start-side `output`/`detail`/`emoji`, reconcile still forces failed terminal status/reason, stop attribution only overrides `output`, cron in-band failures produce frontend-recognizable failure detail, cron success detail stays structured, and narrow pytest is green.
- Round 1 blocker coverage: covered.
  - Abnormal `run_terminal_reconcile` now stores start-side presentation fields in `running_tool_calls` at `src/personal_assistant/main.py:3698` and re-emits them in synthetic failed `tool_call_completed` payloads at `src/personal_assistant/main.py:3965`. `/stop` attribution content overwrites only `output` at `src/personal_assistant/main.py:3971`; `detail` and `emoji` remain intact.
  - Cron in-band `{ok:false,error}` / enqueue declined / missing-service style failures now map through `_cron_result_detail()` to `status="failed"`, `success=False`, and `error` at `src/personal_assistant/tools/cron.py:631`. The frontend already treats `detail.success === false` as failure at `src/IM/frontend/src/features/chat/v2/components/tool-presentation.ts:65`, so completed cron rows become red/failure-tagged instead of green successes.
- M1 coverage remains intact: tool_start still forwards `output=summary`, `detail`, and `emoji` at `src/personal_assistant/main.py:3716`; tool_end still owns final complete detail at `src/personal_assistant/main.py:3767`; frontend running gates still route known cards through `isRunning` at `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:537`.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| M2: interrupted/stalled/reconciled in-flight tool call preserves start-side `output`/`detail`/`emoji` | Cache stores `output/detail/emoji` at `src/personal_assistant/main.py:3702`; reconcile copies them into failed payloads at `src/personal_assistant/main.py:3965`. | `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py:114` covers bash/agent/web_search and asserts summary/detail/emoji survive. | covered |
| M2: reconcile still closes in-flight calls as failed with `reason` | Synthetic payload sets `status="failed"` and `reason` at `src/personal_assistant/main.py:3956`. | `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py:247` asserts failed closure and map reaping. | covered |
| M2: `/stop` attribution content overrides only output while preserving parameter detail/emoji | Reconcile content becomes `reconcile_output` at `src/personal_assistant/main.py:3931`, then only `stuck_tool_call["output"]` is overwritten at `src/personal_assistant/main.py:3971`. | `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py:198` asserts output is stop content while detail/emoji stay from tool_start. | covered |
| M2: refresh/history replay preserves command/prompt/query after abnormal reconcile | Reconcile emits completed tool_call with retained parameter-side `detail`, so persisted IM replay has command/prompt/query instead of empty rows. | `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py:184` checks command, prompt, and query details. | covered |
| M2: cron `{ok:false,error}` becomes frontend-recognizable failure | `_cron_result_detail()` maps `ok is False` and `error` to `status="failed"`, `success=False`, `error` at `src/personal_assistant/tools/cron.py:633` and `src/personal_assistant/tools/cron.py:651`. | `tests/unit/personal_assistant/test_cron_tool_closure.py:175` asserts `success is False` and error text. Frontend failure predicate is covered by success-false tests in `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx:804`. | covered |
| M2: cron missing service / enqueue declined use same in-band failure shape | `_run_job()` returns `{"ok": False, "error": ...}` for missing service, enqueue exception, and declined ack at `src/personal_assistant/tools/cron.py:485`, `src/personal_assistant/tools/cron.py:497`, and `src/personal_assistant/tools/cron.py:504`. | `tests/unit/personal_assistant/test_cron_tool_closure.py:100` and `tests/unit/personal_assistant/test_cron_tool_closure.py:108` cover the tool outputs; presenter failure test covers the shared `{ok:false,error}` shape. | covered |
| M2: cron success detail stays structured | Success output maps to `status="ok"`, `success=True`, and accepted/requestId at `src/personal_assistant/tools/cron.py:633` and `src/personal_assistant/tools/cron.py:645`. | `tests/unit/personal_assistant/test_cron_tool_closure.py:199` asserts successful run detail. | covered |
| M1: running summary/detail/emoji path still works | `tool_start` forwards summary/detail/emoji to IM at `src/personal_assistant/main.py:3716`; presenter start detail remains in builtin/product presenters. | Round 1 tests/evidence remain committed; `tests/unit/personal_assistant/test_tool_end_detail_passthrough.py:193` still covers start summary/detail. | covered |
| M1: tool_end final detail still overwrites running parameter detail | `tool_end` drops the in-flight cache at `src/personal_assistant/main.py:3743` and emits final presenter detail at `src/personal_assistant/main.py:3795`; reducer replacement remains covered. | `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts:139` covers completed output/detail replacing running values. | covered |
| Architecture/test discipline: no new boundary break or temporary test artifact | M2 changes stay in Gateway/product tool/tests; frontend reuses existing `detail.success === false` predicate. | `git diff --check` passed; M2 narrow pytest passed locally in this verify worktree. | covered |

Verification commands run in this verifier worktree:

- `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` -> 23 passed.
- `git diff --check` -> passed.
- `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx src/features/chat/v2/chat-stream-reducer.test.ts` could not run because this verify worktree has no installed `vitest` binary (`/bin/sh: vitest: command not found`). I did not install dependencies or modify dependency state. M2 does not change frontend code; the relevant frontend failure predicate and row styling tests are already committed, and M1 progress recorded frontend `npm run test` / `npm run build` success.

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: `format_start` parameter presentation is forwarded at start, while completion remains authoritative | 是 | `tool_start` forwards `output/detail/emoji` at `src/personal_assistant/main.py:3716`; `tool_end` still emits final presenter detail at `src/personal_assistant/main.py:3795`. |
| M2 review fix: abnormal reconcile must not erase start-side presentation | 是 | `running_tool_calls` stores start-side `output/detail/emoji` at `src/personal_assistant/main.py:3702`; reconcile re-emits them at `src/personal_assistant/main.py:3965`. |
| M2 review fix: cron in-band failures must use existing frontend failure channel | 是 | Cron presenter emits `success=False` at `src/personal_assistant/tools/cron.py:653`; frontend `isCallFailed()` recognizes `detail.success === false` at `src/IM/frontend/src/features/chat/v2/components/tool-presentation.ts:65`. |
| Gateway remains a pure passthrough/reconcile layer, not a tool-semantic renderer | 是 | Gateway stores and forwards presenter-produced fields without per-tool branching in `src/personal_assistant/main.py:3684` and `src/personal_assistant/main.py:3944`. |
| Product/import boundaries remain aligned with SPEC.md | 是 | M2 code remains in `personal_assistant` and product tool modules; no IM-to-agent or product-to-internal-agent dependency was introduced by the M2 diff. |
| Testing follows `docs/TESTING_GUIDE.md` | 是 | Tests extend existing unit files for the relevant behavior; no temporary acceptance scripts were committed for M2. |

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（应该修）

- None.

### SUGGESTION（可以修）

- None.

# Round 3

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 10/10 tasks complete; M2 6/6 tasks complete; M3 5/5 tasks complete |
| Correctness | 13/13 scenarios covered, including failed start-side detail rendering and M2 reconcile/cron regressions |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: M1 remains 10/10 complete, M2 remains 6/6 complete, and M3 is 5/5 complete. `docs/changes/bugfix-441-running-tool-row-summary-input/M3-fix-failed-detail-rendering/tasks.md` marks all exit criteria complete: failed bespoke cards receive top-level failed state, failed start-side detail hides success markers, interrupted parameters remain visible, running/completed adjacent states do not regress, and failed-with-start-detail vitest coverage is committed.
- M3 requirement coverage: covered.
  - `ToolDetailBody` now passes an `isResultPending` semantic gate into bespoke cards at `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:575`.
  - Failed calls with start-side-only detail are treated as pending when `call.status === "failed"` and the detail lacks terminal/result fields at `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:539` and `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:556`.
  - `agent`, `memory`, `skill_manage`, and `task_stop` cards keep parameter regions visible while hiding success/completion bodies when `isResultPending` is true: `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:305`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:390`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:431`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:464`.
  - M2 reconcile still preserves start-side `output`/`detail`/`emoji` for synthetic failed completions: `src/personal_assistant/main.py:3702`, `src/personal_assistant/main.py:3919`, `src/personal_assistant/main.py:3965`.
  - M2 cron in-band failure shape still produces frontend-recognizable failure detail: `src/personal_assistant/tools/cron.py:485`, `src/personal_assistant/tools/cron.py:504`, `src/personal_assistant/tools/cron.py:631`.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| M3: failed `agent` call with start-side detail keeps prompt visible and does not render `✓ completed` / result body | `hasTerminalDetail("agent")` requires terminal keys such as `status`, `content`, `output_file`, `error`, or `agent_id`; absent those keys, `isResultPending()` hides `AgentCard` result region at `tool-detail-renderers.tsx:543`, `:556`, and `:320`. | `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx:919` asserts the prompt remains visible and `.chat-tool-detail-agent-result` is absent. | covered |
| M3: failed `memory` call with parameter-only detail keeps action/target/content visible and hides success marker | `MemoryCard` renders the parameter-only branch under `isResultPending` at `tool-detail-renderers.tsx:406`; terminal memory failure still uses `success === false` at `:398`. | `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx:934`; success-false terminal failure remains covered at `:813`. | covered |
| M3: failed `skill_manage` call with parameter-only detail keeps action/name visible and hides success marker | `SkillCard` renders action/name without the `✓` branch under `isResultPending` at `tool-detail-renderers.tsx:447`; terminal failure still uses `success === false` at `:436`. | `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx:950`; success-false terminal failure remains covered at `:837`. | covered |
| M3: failed `task_stop` call with start-side `task_id` keeps task id visible and hides `✓ status · task_id` | `TaskStopCard` renders only `taskId` under `isResultPending` at `tool-detail-renderers.tsx:467`; completed branch is still gated at `:474`. | `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx:965`. | covered |
| M3: terminal failed details are not incorrectly hidden | `hasTerminalDetail()` returns true for known result/error fields across web_search/agent/memory/skill_manage/task_stop at `tool-detail-renderers.tsx:539`, so failed result cards keep their existing failure body. | Existing failure-routing and success-false tests remain: `tool-calls-panel.test.tsx:735`, `:767`, `:813`, `:837`. | covered |
| M1: running gate remains intact after M3 refactor | `call.status === "running"` still always returns pending at `tool-detail-renderers.tsx:557`; web_search/agent/memory/skill/task_stop running parameter branches remain gated. | Existing running tests remain green at `tool-calls-panel.test.tsx:454`, `:469`, `:484`, `:499`, `:513`. | covered |
| M1: completed success display does not regress | Pending is false for completed calls; completed branches still render result/completion UI in Agent/Memory/Skill/TaskStop cards. | Existing completed success tests remain green, including memory and skill success assertions at `tool-calls-panel.test.tsx:869` and `:893`; reducer final-detail replacement remains covered by `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts`. | covered |
| M2: abnormal reconcile preserves start-side parameter detail in synthetic failed completions | `running_tool_calls` caches `output`/`detail`/`emoji` at `src/personal_assistant/main.py:3702`; `run_terminal_reconcile` re-emits them at `src/personal_assistant/main.py:3965`. | `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py` passed in this round; cases cover command/prompt/query retention and stop attribution. | covered |
| M2: `/stop` attribution still overwrites only `output`, not parameter detail/emoji | Reconcile output is applied after retained fields and only writes `output` at `src/personal_assistant/main.py:3971`; retained `detail`/`emoji` are not cleared. | `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py` passed in this round. | covered |
| M2: cron missing service / enqueue declined / `{ok:false,error}` are rendered as failures | Runtime returns `{ok:false,error}` at `src/personal_assistant/tools/cron.py:485` and `:504`; presenter maps error to `status="failed"`, `success=False`, and `error` at `src/personal_assistant/tools/cron.py:651`. | `tests/unit/personal_assistant/test_cron_tool_closure.py:100`, `:108`, `:195` passed in this round. | covered |
| M2: cron successful run remains structured | `_cron_result_detail()` keeps success fields such as `success`, `accepted`, and `requestId` at `src/personal_assistant/tools/cron.py:631`. | `tests/unit/personal_assistant/test_cron_tool_closure.py:199` passed in this round. | covered |
| Frontend build/type safety for M3 renderer change | Type flow stays inside existing `ToolDetailCardProps` and `ToolDetailBody`; no API/schema change. | `npm run build` passed in this round. | covered |
| Code hygiene / patch integrity | M3 diff is limited to docs plus frontend renderer/tests; no source/test/config edits were made by verifier. | `git diff --check 12131e86..HEAD` passed; verifier `git status --short` was clean before writing this report. | covered |

Verification commands run in this verifier worktree:

- `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` -> 23 passed.
- `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx src/features/chat/v2/chat-stream-reducer.test.ts` -> 2 files passed, 87 tests passed. The output includes pre-existing React `act(...)` warnings in the approval-gate tests and a `--localstorage-file` warning, but no failures.
- `npm run build` -> passed. Vite emitted existing dynamic-import/chunk-size warnings.
- `git diff --check 12131e86..HEAD` -> passed.

Environment note:

- This fresh verify worktree initially had no frontend `node_modules`, so `npm run test` failed with `vitest: command not found`. Reusing the main worktree binary also failed on Vite config package resolution. I then ran `npm ci --ignore-scripts --no-audit --no-fund` in `src/IM/frontend` to install lockfile dependencies for verification; tracked git status remained clean before the report edit.

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| M3: failed top-level status must participate in expanded-body rendering | 是 | `isResultPending()` combines `call.status` with terminal-detail detection at `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:556`, and `ToolDetailBody` passes the result to bespoke cards at `:575`. |
| M3: failed reconcile keeps parameter area visible while hiding success/completion bodies | 是 | Parameter branches remain in Agent/Memory/Skill/TaskStop cards at `tool-detail-renderers.tsx:315`, `:406`, `:447`, and `:467`; success bodies are behind `!isResultPending` or the completed branch. |
| M3: terminal failed result cards should still render real failure bodies | 是 | `hasTerminalDetail()` recognizes failure/result fields at `tool-detail-renderers.tsx:539`; existing terminal failure tests remain green. |
| M1/M2 design still holds: Gateway remains passthrough/reconcile, frontend owns rendering state only | 是 | Gateway retains presenter fields without per-tool UI semantics at `src/personal_assistant/main.py:3702` and `:3965`; M3 changes are confined to frontend display logic. |
| Architecture boundaries remain aligned with `SPEC.md` | 是 | No new import path crosses package boundaries; IM frontend still consumes `ToolCall.detail` only, and Gateway still sits in `personal_assistant`. |
| Testing follows `docs/TESTING_GUIDE.md` | 是 | M3 extends the existing lowest-layer frontend component test file instead of adding temporary committed scripts; browser screenshot evidence is recorded in progress as ignored/local artifact. |

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（应该修）

- None.

### SUGGESTION（可以修）

- None.
