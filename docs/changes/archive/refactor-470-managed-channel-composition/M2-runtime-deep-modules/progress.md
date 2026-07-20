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
- Commits: C1=`7e63ce0c2`, C2=`7cb6e5037`, C3=`56352b11e`。
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
- Commits: C1=`790cb4143`, C2=`a06353d8f`, C3=`57b90ad8d`。
- Next: R3 清理旧 runtime 表面、补 owner contract 并执行真实 Gateway 入口验证。

## [Orchestrator scope clarification] R3: 真实 owner contract

- 澄清: M2 原退出标准已要求 runtime/shutdown/heartbeat/cron/unattended 测试从真实 owner import，以及 `InProcessKernelClient` 无 main re-export/alias。
- 执行: orchestrator 于 2026-07-20 确认，直接锚定已迁出 owner 的三条 contract 随 M2 改读 `gateway/runtime.py` 和 `gateway/kernel_client.py`；保留 `build_runtime` 的构造顺序断言在 `main.py`。
- 边界: 保留 `main` 不 re-export `GatewayRuntime` 的断言，因其直接守护 M2 的无 re-export 退出标准；M4 仍负责完整 `main.__all__ == ["main"]` 与 composition policy contract。
- design.md: 未修改；此前 worker 对 Changelog/Milestone 表的越界改动已在 reviewer 反馈循环中回退。

### R3 — 收口入口旧表面并完成真实入口验证

- Context: `main.py` 已不再拥有 runtime、adapter 与 polling runner；直接 class import 会重新形成 test service locator，旧 shim 名也会误导 consumer 对进程内 SDK 边界的理解。
- Decision: entry 改为模块限定消费 `runtime.GatewayRuntime`、`kernel_client.InProcessKernelClient` 和 `heartbeat_runner.PollingHeartbeatRunner`；`GatewayRuntimeState` 保持 entry lifecycle 的本地 owner；cron consumer 及测试术语同步改为 `InProcessKernelClient`。直接锚定 owner 的 contract 从 `main.py` 移至真实模块，入口 contract 明确不导出 `GatewayRuntime`。
- Rationale: 入口保留构造职责而不泄漏成熟模块类型；每个迁出的实现只有一个生产 owner，同时保留既有 Gateway lifecycle 入口。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_runtime_lifecycle.py tests/unit/personal_assistant/test_gateway_runtime_watchdog.py tests/unit/personal_assistant/test_gateway_shutdown_order.py tests/unit/personal_assistant/test_gateway_shutdown_resource_graph.py tests/unit/personal_assistant/test_gateway_shutdown_timeout_isolation.py tests/unit/personal_assistant/test_gateway_internal_dispatch_listener.py tests/unit/personal_assistant/test_cron_polling_runner.py tests/unit/personal_assistant/test_heartbeat_session_trim.py tests/unit/personal_assistant/test_unattended_session_skills.py tests/unit/personal_assistant/test_cron_run_origin.py tests/contract/test_gateway_inbound_ownership_contract.py tests/contract/test_personal_assistant_main_contract.py` → `60 passed`。
  - Entry: `./scripts/e2e-up.sh` 在 worktree 隔离端口启动 IM 与 `python -m personal_assistant.main --foreground --auto-bind`；日志确认 node auto-bind，向 Gateway PID 发送 SIGTERM 后条件轮询得到 `gateway-terminal-state=absent`，随后 `./scripts/e2e-down.sh` 清理 IM/Gateway。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check src/personal_assistant tests/unit/personal_assistant tests/integration tests/contract` → `All checks passed!`；`/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -m 'not e2e'` → `3614 passed, 1 skipped, 20 deselected`。全量回归首次收集到 `test_gateway_relay_lifecycle.py` 的 `GatewayRuntime` 与 `test_heartbeat_im_delivery.py` 的 stream helper 仍从 `main` 导入；两者已改为各自真实 owner 后重跑通过。旧符号扫描未发现 `_KernelClientShim` 或从 `personal_assistant.main` 导入迁出类型的生产/测试路径。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `2d968bb0f` 与 `0c82dccfb`。
- Commits: C1=`0c82dccfb`, C2=`2d968bb0f`, regression-test=`1163a3155`, C3=`eaf60015d`, reviewer-fix=`ef8c255f8`。
- Next: 已集成 M2；等待 M3。
