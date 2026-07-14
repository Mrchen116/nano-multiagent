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

- Independent product review: Round 8 acceptance `pass` (`99016b4be`) ran the formerly failing global-first
  lifecycle journey against an isolated IM/Gateway stack; default lifecycle evidence remained absent throughout.
- Independent verifier: Round 10 (`5b61904ca`) validated implementation, contracts and a 30-test targeted
  bundle. Its `fail` verdict is solely the then-unrecorded final-gate task rows, not a product/code finding.
- Final code review: the M10 patch review initially confirmed the same-process `--auto-bind` environment leak;
  `6f799b0a9` fixed it and the re-review of `bcad2c850..a4023b6b6` returned `[]`.
- Status: final-gate evidence recorded; docs-only verifier refresh pending.
- Rebase: 当前 unit 已从 refactor-462 前的历史基线 rebase 到 `origin/main`
  `829a3cd15`。唯一冲突是主线已删除、M1 仅更新说明文字的
  `tests/integration/test_provider_error_user_visible.py`；保持主线删除，并从
  `test_no_dead_kernel_subprocess_seam.py` 的 active-entrypoint 清单移除该路径。对应契约
  → `5 passed`。
- Affected evidence:
  - Cron / Feishu unit bundle → `61 passed, 2 warnings in 2.90s`。
  - rebased `test_e2e_up_process_ownership.py` + `test_e2e_up_script.py` →
    `8 passed in 85.71s`，覆盖 delayed identity、timeout rollback、survivor fail-closed、
    readiness rollback、canonical cwd 与 PID-reuse。
  - affected Ruff / format、`bash -n scripts/e2e-{up,down,owned-processes}.sh`、
    `git diff --check` 通过；历史验收 / 验证文档的 4 处行尾空格已机械清理。
- Real e2e: 独立 tmux session 的 `e2e-up.sh` 正常启动 ephemeral IM / Gateway；IM OpenAPI
  可访问，IM 与 Gateway identity 的 PID / process-start 均和 OS 一致，stderr 无
  `process_status: command not found`；随后 `e2e-down.sh` 完整回收且无 lifecycle evidence
  残留。
- Full non-e2e: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e" -q`
  → `3469 passed, 1 skipped, 20 deselected, 16 warnings in 561.04s`，包含 naming/size contract。
  xdist 运行额外暴露 `test_competing_handlers_relay_and_ack_only_the_durable_winner` 的既有测试时序：
  durable winner 已提交时，另一个 handler 可直接读到它而绕开该测试的 `Barrier(2)`，等待者随后
  抛出空消息 `BrokenBarrierError` 并被 handler 映射为 `gateway_not_configured`。该 test 和相关
  IM source 均与 `origin/main` 无 diff；串行 target 连续三次通过，未把范围外测试 harness 修复混入
  refactor-461。
