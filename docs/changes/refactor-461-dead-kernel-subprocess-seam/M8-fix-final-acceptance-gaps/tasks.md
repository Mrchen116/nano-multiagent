# refactor-461-M8: Final acceptance gap fixes — Tasks

> 对齐：`../design.md`；Round 7 verifier / reviewer / code-review 后续修复

## 目标

关闭 Round 7 后独立审查确认的三条 ownership / delivery 缺口，并修正修复过程中真实 e2e
暴露的启动轮询回归：Feishu 首次 owner 绑定不得回写过期整份配置；e2e rollback 只能操作本轮
spawn 的同一 process birth；一次性 Cron 在存活 Gateway 的延迟轮询中不得丢失用户任务，同时
Gateway 重启仍不补投离线期间已过期的任务。

## 退出标准

- [x] Feishu owner binder 在 config lock 内从最新 revision 只 patch 自己拥有的 channel
  `ownerOpenId`，不覆盖同时刷新的 token 或 agent 配置。
- [x] e2e-up rollback 对 IM / Gateway 都绑定本轮 PID + process birth；PID reuse 或 identity
  漂移时零信号、保留完整 lifecycle evidence。
- [x] e2e-up 在 Gateway 尚未发布 runtime identity 的等待窗口不调用已删除 helper、不输出
  command-not-found，且仅以无信号 liveness 检查早退。
- [x] `at` 任务在本进程的 Cron service 已启动后即使超过旧 60 秒 grace 才被 tick，也会只投递
  一次；任务若在 service 启动前已经过期，仍不在 restart 后补投。
- [x] affected / static / test naming-size / full non-e2e / real e2e up-down 完成。
- [ ] 交独立 verifier、reviewer 和 final code review。

## 测试策略

- 配置 ownership：`test_gateway_config_mutation_ownership.py` 以真实文件复现 binder 建立后 token
  刷新、旧 binder 回写的 lost update；`test_gateway_feishu_bot_open_id.py` 保留现有绑定行为。
- lifecycle ownership：`test_e2e_up_process_ownership.py` 注入 rollback 时的 PID reuse；
  `test_e2e_up_script.py` 验证延迟 identity 等待的正常输出、timeout rollback、readiness rollback
  与 canonical cwd。
- Cron：新增 `test_cron_scheduler_active_lifetime.py`，用生产 job / state store / scheduler 固化
  107 秒延迟投递与 restart 不补投的对偶场景；现有 schedule primitive、scheduler tick 与 polling
  runner 测试守护底层 / wiring。
- 真实入口：worktree `scripts/e2e-up.sh` 在独立 tmux session 起 IM + Gateway，核对 process
  identity / IM OpenAPI 后以 `scripts/e2e-down.sh` 回收。Cron 的 Agent 工具创建在当前默认安全
  策略会被 bugfix-456 的 classifier 明确拒绝（任务未落库），不将该既有、范围外权限策略误记为
  本 milestone 的调度失败。

## Roadpoints

### R1 — Feishu binder narrow mutation

- [x] C1：补 stale binder snapshot 覆盖新 token 的回归。
- [x] C2：binder 注入 locked latest-config mutation，只改 owner 字段。

### R2 — Rollback process birth binding

- [x] C1：用 fake runtime 复现 rollback 中 Gateway PID reuse 后误停 / 擦除 evidence。
- [x] C2：rollback / evidence cleanup 全部以 spawned PID + birth 为授权条件。

### R3 — One-shot Cron active lifetime

- [x] C1：证明 active Gateway 在 due+107s 仍应投递，而 restart 前已过期任务不能补投。
- [x] C2：CronExecutionService 持有 in-memory active-since fence，CronScheduler 用它区分两类
  无 run-state 的任务。

### R4 — Delayed identity polling

- [x] C1：延迟 runtime identity 的 shell harness 断言 stderr 不含 command-not-found。
- [x] C2：补轻量 liveness helper；保留 rollback 的 Python birth-snapshot 原语。

### R5 — Final gates

- [x] C3：记录 rebase 后的验证与真实 e2e 结论。
- [ ] C4：记录独立 verifier、reviewer 和 final code review 结论。
