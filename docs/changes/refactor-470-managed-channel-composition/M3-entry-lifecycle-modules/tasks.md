# refactor-470-M3: entry-side lifecycle modules — Tasks

> 对齐: ../design.md v2

## 目标

保持 Gateway 的后台启动、重复启动、停止/重启、节点自动绑定与 IM 重连后收敛行为不变，同时将进程生命周期、IM bootstrap 和 register-ready 编排迁入各自具名 owner，收窄入口模块。

## 退出标准

- [ ] 默认后台启动、重复启动、stop/restart、auto-bind 与 IM reconnect 收敛保持不变。
- [ ] lifecycle state 的安全采纳契约保持；`im_bootstrap` 不承担 channel 或 Agent 编排；on-connected 不捕获 nullable manager。
- [ ] launch/PID/command/auto-bind/reconnect 测试从真实 owner import；聚焦测试与 ruff 通过。

## 测试策略

- 被测行为（来自退出标准）：后台单实例与安全 PID 采纳、stop/restart 的有序进程控制、auto-bind、节点绑定失败后的 degraded heartbeat、register-ready 的 channel/Agent 收敛顺序、CLI 命令分派。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_launch.py`、`test_gateway_pid_lifecycle.py`、`test_auto_bind.py`、`test_gateway_main_command.py`、`test_gateway_reconnect_registration_gate.py`（扩展并迁移 import）；`tests/contract/test_personal_assistant_main_contract.py`（扩展）。
- 落层/目录/marker：`tests/unit/` 与 `tests/contract/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：使用隔离 config 执行 `personal_assistant.main --foreground --auto-bind`，确认 node 自动绑定并可优雅停止。
- 前端 UI：N/A。

## Roadpoints

### R1 — 迁移 IM bootstrap 与 register-ready 编排

- 状态: DONE
- 步骤: 新建 `gateway.im_bootstrap` 和 `gateway.connection_ready`，将 HTTP node binding/auto-bind 与 register ACK 后的错误隔离、channel/Agent 收敛顺序从入口迁出；迁移对应测试 import，并保留真实可观察行为断言。
- 验证: auto-bind 与 reconnect registration 聚焦测试、ruff。

### R2 — 迁移后台进程生命周期 owner

- 状态: TODO
- 步骤: 新建 `gateway.process_lifecycle`，整体迁移后台启动、PID state、锁、进程身份、安全 signal 和 signal handler；迁移 launch/PID 测试 import。
- 验证: launch/PID lifecycle 聚焦测试、ruff。

### R3 — 收窄 CLI 入口并验证真实命令路径

- 状态: TODO
- 步骤: `main.py` 仅保留参数解析与到 lifecycle/composition owner 的模块限定调用；调整入口 contract 与 command tests，并用隔离 config 前台启动完成 auto-bind/关闭验收。
- 验证: command/contract 聚焦测试、隔离 IM + Gateway 真入口启动停止、ruff。
