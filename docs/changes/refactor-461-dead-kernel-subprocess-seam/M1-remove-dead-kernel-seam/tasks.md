# refactor-461-M1: remove dead kernel seam — Tasks

> 对齐: ../design.md v1

## 目标

Gateway 只保留自身后台进程与进程内 Kernel 的真实拓扑；旧 Kernel subprocess、HTTP health 与配置接口不可再被运行时、测试、脚本或活跃文档复活，同时旧 lifecycle timing 可安全迁移。

## 退出标准

- [ ] `GatewayProcessManager`、可选 `process_manager`、Kernel command/health helper、`BackgroundLaunchResult.health_url` 与 runtime `KernelConfig` 从生产接口删除，不新增替代 seam。
- [ ] `GatewayLifecycleConfig` 维持既有默认值，并逐字段迁移旧三项 timing；canonical save 在裁掉任意 config 的 `kernel:` 前创建不可覆盖且内容一致的 migration backup，失败不覆盖原文件。
- [ ] Gateway 默认 start/stop/restart 只基于 PID/liveness 与 process-group，旧 state 多余 `health_url` 可读、新 state 不写；shutdown 顺序和真实生产 wiring 不变。
- [ ] active scripts、AGENTS、tracked sample configs 与测试叙事不再要求 Kernel API、port、`.api.pid` 或已删除 app；active-scope contract guard 阻止回流且不扫描历史 change/archive。
- [ ] 最窄 config/lifecycle/helper、contract guard、ruff 与 non-e2e 全绿；按 design Runbook 真跑 operator CLI、真栈消息与主动任务，并完成资源清理。

## 测试策略

- 被测行为（来自退出标准）：旧三项 timing 的默认/迁移/逐字段优先级；死字段忽略；canonical save 与 per-file migration backup 的创建、复用、冲突和失败原文件不变；PID-only start/stop/restart 与旧 state extra-field；GatewayRuntime shutdown 顺序；active-scope zero-residue；真栈消息、heartbeat/cron 与 operator lifecycle。
- 已有测试在：`tests/unit/personal_assistant/test_local_store.py`、`test_gateway_launch.py`、`test_gateway_pid_lifecycle.py`、`test_gateway_main_command.py`、`test_gateway_runtime_lifecycle.py`、`test_gateway_shutdown_order.py`、`tests/unit/test_e2e_conftest_finalizer.py`、`tests/unit/test_runtime_helpers.py`（扩展/修正）；新建 `tests/contract/test_no_dead_kernel_subprocess_seam.py`，理由：跨 active source/script/doc/config 文件的架构残留需要聚焦 contract guard。
- 落层/目录/marker：`tests/unit/` 与 `tests/integration/`，marker：无；`tests/contract/`，marker：无；真长驻进程证据由既有 `tests/e2e/`/Runbook 承担，marker：e2e。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree `.e2e-ports.env`、`.gateway-config.yaml`、PID/log/state 与临时 operator config；结论写入 `progress.md`，运行时文件由 `e2e-down.sh`/人工清理。

前端 UI：N/A。本 milestone 不改前端，也无 prototype/reference。

## Roadpoints

### R1 — 收口 Gateway lifecycle 配置与迁移备份

- 状态：DONE
- 步骤：先补 default/legacy/new+legacy/save/backup 红测；再以 `GatewayLifecycleConfig` / `LocalConfig.gateway` 替代 `KernelConfig`，实现 parser-edge 逐字段迁移、canonical save 与所有 config 的一次性原字节 migration backup；机械迁移受影响 fixtures。
- 验证：`test_local_store.py` 覆盖退出标准；最窄受影响 PA tests 全绿；死 Kernel 连接字段不再验证或进入 runtime。

### R2 — 删除 runtime subprocess/health seam 并保持 lifecycle 行为

- 状态：DOING
- 步骤：先把 launch/state/stop/runtime lifecycle 测试改写为 PID/start confirmation 与真实 shutdown 顺序并验红；再删除 manager、optional interface、health state/probe 和 ready 命名，保留 Gateway background process factory、PID/process-group、shim 与关闭顺序。
- 验证：launch/main/pid/runtime/shutdown/build-runtime/reconcile tests 全绿；真实 operator 默认 start/stop/restart 证据满足 Runbook。

### R3 — 清理 active 入口残留并完成真栈验收

- 状态：TODO
- 步骤：先新增 active-scope zero-residue contract guard 并确认红；再清理 AGENTS、e2e/acceptance/fixture scripts、sample configs、e2e finalizer 与 provider error 说明；不扫描/改写历史 change/archive。
- 验证：guard、helper/integration tests、ruff、non-e2e 全绿；`e2e-up/down` 真栈只有 IM + Gateway，消息与 heartbeat/cron 到用户可观察结果，无 `.api.pid`/Kernel app 泄漏。
