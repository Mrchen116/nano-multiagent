# refactor-470-M3 — Progress

## 启动记录

- 已完成 `motivation.md`、`design.md`、项目约定、`LOGBOOK.md`、`docs/TESTING_GUIDE.md` 与现有源码/测试结构阅读。
- 基线：`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_launch.py tests/unit/personal_assistant/test_gateway_pid_lifecycle.py tests/unit/personal_assistant/test_gateway_main_command.py tests/unit/personal_assistant/test_auto_bind.py tests/unit/personal_assistant/test_gateway_reconnect_registration_gate.py tests/contract/test_personal_assistant_main_contract.py`，39 passed。
- 环境说明：M3 worktree 未建立 `.venv`，已确认主仓 `/Users/czj/Repos/nano-multiagent/.venv` 可用；后续测试显式使用该解释器并设置 `PYTHONPATH=src`，不改动工作树配置或产品代码。

### R1 — 迁移 IM bootstrap 与 register-ready 编排

- Context: HTTP node binding/auto-bind 与 register ACK 后的跨 owner 收敛原本落在入口和构造函数闭包中。
- Decision: 将 IM bootstrap client、operator feedback 与 bind token 解析迁入 `gateway.im_bootstrap`；将 binding 失败隔离、managed-channel replay、Agent profile reconcile 的既有顺序迁入 `ConnectionReadyCoordinator`。
- Rationale: bootstrap 只拥有 HTTP binding，coordinator 只拥有跨 owner 顺序；连接 sender 由 IMConnectionManager 在 register ACK 后直接传入，不再捕获尚未构造的 manager。
- Evidence:
  - Tests: 聚焦 `test_auto_bind.py`、`test_gateway_reconnect_registration_gate.py`、`test_gateway_build_runtime.py`、`test_gateway_relay_lifecycle.py` 共 52 passed；完整 `pytest -q -m "not e2e"` 为 3614 passed, 1 skipped, 20 deselected。
  - Entry: R3 统一执行隔离 Gateway 真入口验证。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 既有 auto-bind、register gate 与 binding failure 后仍 reconcile regression 均从真实 owner import 并通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: `git revert aa0cc10a2` 后恢复 bootstrap 与收敛逻辑在入口的位置。
- Commits: C1=7e8a0f52a, C2=aa0cc10a2, C3=cb8a7a4e1。
- Next: R2 迁移后台进程生命周期 owner。

### R2 — 迁移后台进程生命周期 owner

- Context: 后台启动、PID state、进程身份确认、跨进程锁和安全 signal 原先与 runtime composition 混在入口模块中。
- Decision: 将完整生命周期算法迁入 `gateway.process_lifecycle`；`main.py` 仅以 `process_lifecycle` 模块限定名分派 start、stop、restart 与 foreground run。
- Rationale: lifecycle state 与 OS 进程控制是一个共享不变量，必须由同一具名 owner 持有；保持原有 process birth identity、legacy PID 语义校验和 signal 前后复核，避免 PID reuse 误杀。
- Evidence:
  - Tests: `test_gateway_launch.py`、`test_gateway_pid_lifecycle.py`、`test_gateway_relay_lifecycle.py` 共 48 passed；完整 `pytest -q -m "not e2e"` 为 3615 passed, 1 skipped, 20 deselected。
  - Entry: R3 使用隔离 IM + Gateway 真入口统一验证。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: launch/PID lifecycle 测试从 `gateway.process_lifecycle` 导入，并覆盖重复启动、legacy state 安全采纳、优雅 stop/restart 与 process identity 复核。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: `git revert b71c6923b` 后恢复 lifecycle 实现在入口模块的位置。
- Commits: C1=f8e9bd06d, C2=b71c6923b, C3=本提交。
- Next: R3 收窄入口并执行真命令路径验收。

### R3 — 收窄 CLI 入口并验证真实命令路径

- Context: 入口仍须保持 CLI 参数、用户反馈和命令分派，同时禁止以直接导入形成 lifecycle/bootstrap 的事实 re-export。
- Decision: `main.py` 通过 `process_lifecycle` 与 `im_bootstrap` 模块限定名分派；入口 contract 固定该边界，命令测试只验证参数、反馈和分派。
- Rationale: CLI 入口不拥有进程或 IM bootstrap 策略，模块限定调用使 owner 清晰且不会给生产或测试留下旧 private import 路径。
- Evidence:
  - Tests: command/build-runtime/bootstrap/contract 聚焦测试共 38 passed；完整 `pytest -q -m "not e2e"` 为 3615 passed, 1 skipped, 20 deselected；相关 ruff check 通过。
  - Entry: 执行 `./scripts/e2e-up.sh` 启动 worktree 隔离 IM 与 `personal_assistant.main --foreground --auto-bind`；经 IM 认证 API 确认唯一 node 已有 `owner_id`，Gateway 日志记录 `auto-bound to IM`；随后 `./scripts/e2e-down.sh` 优雅停止 Gateway 和 IM，`.gateway-state.json` 与 PID 文件均已清理。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_gateway_main_command.py`、`test_auto_bind.py`、`test_gateway_reconnect_registration_gate.py` 和 `test_personal_assistant_main_contract.py` 覆盖命令分派、auto-bind、register-ready 收敛与入口 owner。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: `git revert bc403745b` 后恢复入口直接导入；`git revert b71c6923b` 可整体回退 lifecycle owner。
- Commits: C1=a91ec5ff6, C2=bc403745b, C3=本提交。
- Next: rebase 到 `origin/unit/refactor-470` 并完成 milestone 集成。
