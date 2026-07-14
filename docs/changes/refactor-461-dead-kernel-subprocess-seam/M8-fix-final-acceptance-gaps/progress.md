# refactor-461-M8 — Progress

## Baseline

- Context: Round 7 verifier report为 pass，但独立 reviewer 的真实验收发现一次性 `at` Cron 未投递；
  随后的 final code review 另确认 Feishu binder stale whole-config save 和 e2e rollback PID reuse。
- Scope: `src/personal_assistant/{main.py,scheduler/}`、`scripts/e2e-up.sh` 与精确回归；不放宽
  public lifecycle / config transaction 的既有 ownership 边界。

## R1 — Feishu binder narrow mutation

- C1 `13899799e`：真实 config 回归锁定 binder 创建后 token refresh 被旧整份 config 覆盖。
- C2 `3e5c3787a`：`_build_feishu_owner_open_id_binder()` 改为注入 `update_local_config()`，在 lock
  内读取最新 revision，仅更新匹配 enabled Feishu channel 的 `ownerOpenId`；若最新值已由并发 writer
  设置则复用它。写入后同步 adapter 捕获的 channel settings，避免运行期 snapshot 偏离。
- Evidence: `test_gateway_config_mutation_ownership.py` +
  `test_gateway_feishu_bot_open_id.py` → `13 passed`。

## R2 — Rollback process birth binding

- C1 `71edf6750`：fake runtime 在 `/nodes` readiness 前模拟 PID reuse，证明旧 rollback 会向重用的
  Gateway PID 发信号并丢弃该 generation evidence。
- C2 `088aa853b`：记录 spawn 后的 IM / Gateway birth；rollback TERM/KILL 和 lifecycle evidence
  cleanup 都要求当前 snapshot 仍匹配原 birth。漂移时 fail closed，完整 stack evidence 留给后续
  validated teardown。
- Evidence: `test_rollback_reused_gateway_pid_retains_complete_stack` → `1 passed`；其余 e2e-up
  timeout / readiness rollback 由 R5 final gate 重跑。

## R3 — One-shot Cron active lifetime

- Root cause: `_AtSchedule` 的 60 秒 expired grace 本意是禁止 Gateway restart 后回补；但 scheduler
  无法区分“restart 前已过期”与“同一 Gateway 存活、tick 被延迟”。真实 reviewer 任务在 due+107s
  仍 enabled、无 state / runs record；受控生产 scheduler 复现 due+61s 返回空 due jobs。
- C1 `6bb53ffc8`：新增 active-lifetime 对偶回归。
- C2 `1272963a6`：每个 `CronExecutionService` 记录 in-memory `active_since`，生产 tick 将它传给
  `CronScheduler`。未运行的 `at` job 若 due 在 fence 前则 skip（restart contract）；若 due 在 fence
  后则即使超过旧 grace 仍返回原 due instant，state 写入后不会重投。
- Evidence: active-lifetime、schedule primitive、scheduler、scheduler tick、polling runner →
  `48 passed`；Cron/Feishu affected unit bundle → `61 passed`。

## R4 — Delayed identity polling

- Real e2e discovery: M8 R2 删除旧 `process_status()` 后，identity wait loop 仍调用它；正常冷启动
  最终可成功，但 stderr 重复 `process_status: command not found`。
- C1 `8d7ec0f33`：将 delayed identity startup harness 固化为 stderr clean 回归，旧代码失败。
- C2 `0907c1e05`：补仅作无信号 liveness 判断的 helper 给 identity wait path；rollback 继续使用
  `read_gateway_process_snapshot()` 的 PID/birth verification，不降低 teardown signal authority。
- Evidence: targeted delayed identity test → `1 passed in 11.68s`；真实 worktree e2e-up 显示无
  command-not-found，IM / Gateway identity 与 OS birth 一致，e2e-down 已完成回收。

## R5 — Final gates

- Status: IN PROGRESS（等待把旧 integration base rebase 到当前 `origin/main` 后重跑）。
- Affected evidence:
  - Cron / Feishu unit bundle → `61 passed, 2 warnings in 2.90s`。
  - `test_e2e_up_process_ownership.py` → `3 passed in 17.64s`；e2e-up 的 delayed identity、
    timeout rollback、survivor fail-closed、readiness rollback、canonical cwd 五条分别复跑通过。
  - affected Ruff / format、`bash -n scripts/e2e-{up,down,owned-processes}.sh`、
    `git diff --check` 通过。
- Real e2e: 独立 tmux session 的 `e2e-up.sh` 正常启动 ephemeral IM / Gateway；IM OpenAPI
  可访问，IM 与 Gateway identity 的 PID / process-start 均和 OS 一致，stderr 无
  `process_status: command not found`；随后 `e2e-down.sh` 完整回收且无 lifecycle evidence
  残留。
- Full non-e2e: 已运行 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -n auto
  -m "not e2e" -q`。唯一失败是 `test_new_test_files_under_400_lines`；`--lf` 复现为同一项。
  该 guard 以**当前** `origin/main` 比较，但本 integration branch 尚基于 refactor-462 前的
  `d9e4780`，而当前 `origin/main` 的 refactor-462 已删除七个旧超限测试文件。它们均为 branch
  继承文件，非 M8 变更；需先 rebase 当前 unit 到 `origin/main`，再把该 gate 作为最终结果。
