# refactor-470-M2 — Progress

## 启动记录

- 已完成 Sync Gate：本地与 `origin/unit/refactor-470` 均为 `e268399684f7f5b58ab1274887c1e6a110e7f7cd`。
- 已读 motivation、design、项目约定、LOGBOOK、测试规范与现有 runtime/heartbeat/cron/unattended 测试。
- 基线：`/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q` 运行 9 个 M2 聚焦测试文件，`51 passed`。
- 本 milestone 无前端变更、无 prototype/reference。

### R1 — 建立真实 runtime owner

- Context: `GatewayRuntime` 是完整的进程 lifecycle/resource-graph owner，但此前与 entry、composition 代码共处 `main.py`，使 runtime 测试依赖入口作为 service locator。
- Decision: 将完整 runtime、lifecycle protocols、skill-batch helpers 与 IM task await helper 迁至 `gateway/runtime.py`；`main.py` 仅直接消费 `GatewayRuntime` / `GatewayRuntimeLike`。runtime、watchdog、shutdown 与 internal dispatch listener 测试改从真实 owner import。
- Rationale: 保持既有有序关闭、IM watchdog、heartbeat first-connect gate 和 shared deadline 的单一实现，同时消除 `main` 的 test-only runtime 表面。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_runtime_lifecycle.py tests/unit/personal_assistant/test_gateway_runtime_watchdog.py tests/unit/personal_assistant/test_gateway_shutdown_order.py tests/unit/personal_assistant/test_gateway_shutdown_resource_graph.py tests/unit/personal_assistant/test_gateway_shutdown_timeout_isolation.py tests/unit/personal_assistant/test_gateway_internal_dispatch_listener.py` → `23 passed`。
  - Entry: R3 统一执行隔离 Gateway 前台启动与 SIGTERM 退出，避免重复运行时证据。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 上述既有 runtime resource-graph、watchdog 与真实 internal HTTP listener regression 均通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `7cb6e5037` 与 `7e63ce0c2`。
- Commits: C1=`7e63ce0c2`, C2=`7cb6e5037`, C3=pending。
- Next: R2 迁移 kernel adapter 与 polling heartbeat runner。

### R2 — 迁移 kernel adapter 与 polling runner

- Context: heartbeat/cron 的 polling loop 和 Kernel adapter 已各自形成连贯职责，但旧名 `_KernelClientShim` 与实现仍留在 `main.py`，测试无法直接表达真实 owner。
- Decision: 将 adapter 更名为 `InProcessKernelClient` 并迁至 `gateway/kernel_client.py`；将 `PollingHeartbeatRunner`、run completion delivery 与 task exception observer 迁至 `scheduler/heartbeat_runner.py`。构造点与 consumer 均改用新 owner，移除旧定义。
- Rationale: adapter 名称准确表达进程内 SDK 边界，polling runner 则与 heartbeat scheduler 同域；两者各保留原先的 session capability 投影、RunOrigin 映射、cron polling、silent heartbeat cleanup 和异常观测语义。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_cron_polling_runner.py tests/unit/personal_assistant/test_heartbeat_session_trim.py tests/unit/personal_assistant/test_unattended_session_skills.py tests/unit/personal_assistant/test_cron_run_origin.py tests/unit/personal_assistant/test_gateway_shutdown_resource_graph.py` → `26 passed`。
  - Entry: R3 统一执行隔离 Gateway 前台启动与 SIGTERM 退出，避免重复运行时证据。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 上述既有 unattended capability、RunOrigin、heartbeat/cron polling、silent cleanup 和 shutdown resource-graph regression 均通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `a06353d8f` 与 `790cb4143`。
- Commits: C1=`790cb4143`, C2=`a06353d8f`, C3=pending。
- Next: R3 清理旧 runtime 表面、补 owner contract 并执行真实 Gateway 入口验证。
