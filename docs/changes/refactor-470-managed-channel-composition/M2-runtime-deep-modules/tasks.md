# refactor-470-M2: runtime 深模块迁移 — Tasks

> 对齐: ../design.md v2

## 目标

将 `GatewayRuntime`、进程内 Kernel adapter 与 polling heartbeat runner 整体迁移到各自真实 owner，保持 Gateway 启动、heartbeat/cron 主动投递及有序关闭行为不变，并移除 `main.py` 的旧实现名与测试定位器表面。

## 退出标准

- [ ] `GatewayRuntime` 位于 `gateway/runtime.py`，保留 startup、watchdog、共享 shutdown deadline 与资源图语义。
- [ ] `InProcessKernelClient` 位于 `gateway/kernel_client.py`，没有 `_KernelClientShim` 或 `main` re-export/alias。
- [ ] `PollingHeartbeatRunner` 位于 `scheduler/heartbeat_runner.py`，heartbeat/cron polling 行为不变。
- [ ] runtime/shutdown/heartbeat/cron/unattended 测试从真实 owner import，聚焦测试与 ruff 通过。

## 测试策略

- 被测行为（来自退出标准）：Gateway 在 IM 不可达或维护 loop 异常退出时仍保持可用；共享 deadline 按既有资源图关闭所有 owner；heartbeat polling 保持 heartbeat/cron 调度与主动投递；unattended session 沿用 Agent skill scope。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_runtime_lifecycle.py`、`test_gateway_runtime_watchdog.py`、`test_gateway_shutdown_order.py`、`test_gateway_shutdown_resource_graph.py`、`test_gateway_shutdown_timeout_isolation.py`、`test_cron_polling_runner.py`、`test_heartbeat_im_delivery.py`、`test_unattended_session_skills.py`（扩展/迁移 import）；无新建长期测试文件。
- 落层/目录/marker：`tests/unit/personal_assistant/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：用隔离配置从 `python -m personal_assistant.main --foreground` 启动真实 Gateway，确认启动与 SIGTERM 有序退出日志。
- 前端 UI、Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 建立真实 runtime owner

- 状态：TODO
- 步骤：以 owner import 的回归断言固定 `GatewayRuntime` 的启动、watchdog 与 shutdown 资源图；将 runtime 与必要 lifecycle protocols/helpers 迁至 `gateway/runtime.py`，更新 runtime 测试 import。
- 验证：runtime lifecycle/watchdog/shutdown 聚焦测试、Gateway 前台启动与关闭。

### R2 — 迁移 kernel adapter 与 polling runner

- 状态：TODO
- 步骤：以真实 owner import 固定 unattended session capability 投影和 polling heartbeat/cron 行为；将 adapter 更名为 `InProcessKernelClient` 并迁至 `gateway/kernel_client.py`，将 runner 及必要 heartbeat helpers 迁至 `scheduler/heartbeat_runner.py`，更新消费端与测试 import。
- 验证：unattended、heartbeat、cron 聚焦测试、Gateway 前台启动与关闭。

### R3 — 清理旧 runtime 表面并完成回归

- 状态：TODO
- 步骤：删除 `main.py` 中已迁移实现与旧符号，清理失效测试 import/patch 路径；补充 owner-location contract 并运行 M2 聚焦测试和 ruff。
- 验证：无生产或测试路径引用 `_KernelClientShim`、`PollingHeartbeatRunner`/`GatewayRuntime` 的 main 实现；聚焦测试与 ruff 通过。
