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
