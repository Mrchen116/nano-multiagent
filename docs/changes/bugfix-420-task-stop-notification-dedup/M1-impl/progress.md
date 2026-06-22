# bugfix-420-M1 — progress

> 单 M1（impl）。改动集中于 background_tasks 的 kill / 通知路径，跨 core+platform。
> TDD 三提交 = 三个 roadpoint：C1 红测 / C2 实现 / C3 文档。
> 退出标准见 design.md Milestone 表 bugfix-420-M1 行。

## R1 (C1) — 红测

### Context
对齐 CC `stopTask.ts:67-95` 两分支：停 bash 抑制 model-facing `<task-notification>`、停 subagent 保留通知但带部分结果。现状 `registry.kill()` 无 `notified` / `result_text` 能力、`task_stop` 对 bash/subagent 无差别 kill、subagent 通知空壳（缺 `<result>`）。先按目标行为写红测钉住契约。

### Decision
写 7 个红测覆盖三层：
- registry：`kill` 扩参 `notified` / `result_text` 携带 + 抑制能力、幂等不破。
- task_stop 工具：bash 同步 kill(notified=True)；subagent 不同步 kill（record 留非终态，交 worker unwind）。
- RuntimeRunner worker：abort 分支走 `on_kill(result_text=最后一段文字)`、无产出 `result_text=None`、自然完成走 `on_complete` 不误标 killed。

### Rationale
契约层（kernel delta-spec）的 4 个 Scenario 都落在「父会话可观察的消息流」，但单测层无法直接观测 IM 消息流，故拆到「registry 状态 + 回调路由 + notified/result_text 字段」三个可单测的接缝上，每个 Scenario 对应一到两个测试。红测先行确保实现不会偷偷改契约。

### Evidence
7 个红测全部按「缺待实现能力」失败（非断言逻辑错），证明测试钉的是新增能力：
- `kill() got an unexpected keyword argument 'result_text'` / `'notified'`（registry 扩参未实现）
- subagent 分支：`record.status == KILLED`（旧行为同步 kill）vs 期望 RUNNING
- `RuntimeRunner.start() got an unexpected keyword argument 'on_kill'`（回调未实现）

### Rollback
`git revert 570baaf5`（纯测试文件，无生产影响）。

### Commits
- `570baaf5` test(bugfix-420/M1): C1 红测 — kill 扩参/幂等、task_stop 分支、RuntimeRunner on_kill 路径

## R2 (C2) — 实现

### Context
按 design.md 4 条关键决策落地，让 R1 红测转绿。改动方向均为 `platform → core`（合规）；不破 `_guard_terminal` 首个终态赢幂等不变量。

### Decision
- **决策 4**：`registry.kill()` 扩参 `notified=False` / `result_text=None`，镜像 `complete()`，`_guard_terminal` 仍在最前。
- **决策 3**：`interfaces.py` 新增 `TaskKillCallback` 协议 + `BackgroundSubagentRunner.start` 加 `on_kill` 形参。
- **决策 2/3**：`runtime_runner._worker` 在 `runtime.run` 返回后判 `controller.is_aborted`：真 → `on_kill(result_text=_extract_assistant_text(turn_result))`；假 → `on_complete`。
- **决策 3**：`agent.py` 新增 `_make_on_kill` → `registry.kill(agent_id, reason="stopped by user", result_text=…)`（`notified=False` 让通知带结果发出）；两处后台 subagent 启动 callsite 加 `on_kill=`。
- **决策 1**：`task_stop.run()` 按 `record.task_type` 分支：SUBAGENT 只 `request_stop`（不同步 kill）；BASH `registry.kill(notified=True)` 抑制通知。
- **协议一致外溢**：`wiring.py` 的 `_NoOpSubagentRunner.start` + `runners.py` 的 `run_subagent_lifecycle` 模板同步加 `on_kill` 形参。

### Rationale
- 停 subagent 不同步 kill 而交 worker unwind：cooperative abort 让 `runtime.run` 返回带累积 messages 的 TurnResult，worker 才能抽到最后一段文字塞进 `<result>`；若 task_stop 同步 kill 会抢在前面被 `_guard_terminal` 挡掉结果（正是本 bug 机制）。
- 用独立 `on_kill` 而非给 `on_complete` 加 `killed: bool`：避免污染 complete 语义、不波及 bash 侧与协议。
- 微调（与 design 文本的偏差，已记 tasks.md / design changelog）：design 写 `controller.is_aborted()`，实际 `run_control.py:70` 是 `@property`，实现用无括号 `controller.is_aborted`；`notifications.py` 无需改 —— `<result>` 已由 `record.result_text` 非空驱动，`result_text=None` 自动省略。

### Evidence
- 退出标准指定命令 `pytest -q tests/unit -k "background_task or task_stop or registry"` → **140 passed**（含 R1 全部转绿）。team-lead 已独立复跑同命令 = 140 passed。
- 整合 `tests/integration/background_tasks/test_task_stop.py` → 3 passed（两个旧断言 buggy 行为的测试更新为新契约：bash `runs.submissions==[]`、subagent worker unwind 后 KILLED 且注入消息含 `<result>subagent done</result>`）。
- 全测试树 `pytest -q -m "not e2e"` → **2722 passed / 1 skipped / 0 failed**。
- `ruff check` + `ruff format --check` 全过；contract（platform→core 边界）绿。

**4 个 reviewer Scenario ↔ 测试映射**：

| Scenario（delta-spec） | 覆盖测试 |
|---|---|
| 停后台 bash 不再发重复通知 | 单测 `test_stop_running_bash_task_kills_synchronously_and_suppresses_notification`（`record.notified is True`）+ 整合 `test_task_stop_kills_running_bash_task`（`runs.submissions==[]` 且 `runs.injections==[]`，确认通知被抑制） |
| 停后台 subagent 通知携带部分结果 | 单测 `test_runtime_runner_aborted_run_invokes_on_kill_with_result`（on_kill `result_text="partial findings here"`）+ 整合 `test_task_stop_kills_running_agent_task`（注入消息含 `<result>subagent done</result>`、`record.result_text=="subagent done"`） |
| 子 agent 无产出时通知省略 result | 单测 `test_runtime_runner_aborted_run_with_no_output_omits_result`（on_kill `result_text=None`）+ `test_kill_result_text_defaults_none`（`notifications.py` 由 `result_text` 非空驱动 `<result>`，None 自动省略，不发空 `<result>`） |
| 停止后任务进 killed 终态且可续跑 | 整合 `test_task_stop_kills_running_agent_task`（worker unwind 后 `record.status==KILLED`）+ `test_kill_is_idempotent_after_terminal`（首个终态赢幂等：二次 kill 不覆盖 error/result_text/notified；resume 依赖的 `_resume_subagent` 对 killed-in-memory 续跑能力不受影响，见 design 决策 2 现状分析） |
| 附：自然完成不被误标 killed（design 风险 3） | `test_runtime_runner_natural_completion_not_misflagged_as_kill`（未 abort → on_complete，绝不 on_kill） |

### Rollback
`git revert 936bb66b`（改动集中、纯逻辑），即恢复 feat-337 原行为；新增参数均有默认值，不破既有调用。

### Commits
- `936bb66b` fix(bugfix-420/M1): task_stop 按任务类型分支去重通知 + subagent 携带部分结果

## R3 (C3) — 文档

### Context
TDD C3 阶段：勾选 tasks、记录与 design 的微调、补 changelog。

### Decision
- `M1-impl/tasks.md` 三个 task 勾选 + 「实现说明（与 design 的微调）」段。
- `design.md` Changelog 段补 M1 impl 落地记录 + 两点微调。

### Rationale
微调（is_aborted 是 property、notifications.py 无需改）和同契约外溢两处（runners.py 模板、整合测试更新）属「design 未点名但实现必须处理」的偏差，需在文档留痕供 verifier / reviewer 对账。

### Evidence
`docs/changes/bugfix-420-task-stop-notification-dedup/M1-impl/tasks.md` 三项均 `[x]`；`design.md` Changelog 段含 bugfix-420-M1 条目。

### Rollback
`git revert 17be6d09`（纯文档）。

### Commits
- `17be6d09` docs(bugfix-420/M1): tasks 勾选 + design changelog（C3）

## 收尾

- M1 三提交已 `--no-ff` 合入 `unit/bugfix-420`（merge `44a34aa2`，无冲突），已 push origin。
- milestone worktree + 本地/远端 milestone 分支已清理（远端原无 milestone 分支）。
- 未碰 main —— main PR 由 orchestrator 收尾。
