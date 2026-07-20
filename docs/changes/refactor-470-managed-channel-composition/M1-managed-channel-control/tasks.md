# refactor-470-M1: managed-channel control ownership — Tasks

> 对齐: ../design.md v2

## 目标

将 managed channel 的控制策略从 Gateway 入口收回 `ManagedChannelControl`：由强类型 bindings 接入 IM 连接层，保留既有 manifest/cache、ACK/retry 与 FIFO owner；移除 standalone YAML 到 managed manifest 的非契约迁移。

## 退出标准

- [ ] 在线 apply/reconnect、失败隔离、离线 cached startup 与 register replay 保持既有行为。
- [ ] `ManagedChannelControl` 提供 `start_cached()`、`connection_bindings()`、`close()`；mailbox 只做 typed ephemeral emission，不拥有 durable retry 或 wire FIFO。
- [ ] Agent skill 激活改用正式 public operation；不再从入口穿透 `IMAgentConfigSync` 私有方法。
- [ ] `channels.bootstrap.request` 直接返回空 `items`；legacy YAML migration、export、bootstrap callback 及测试删除。
- [ ] 相关 unit/integration 测试与 ruff 通过。

## 测试策略

- 被测行为（来自退出标准）：bootstrap request 直接返回空 items；fatal owner mismatch 在 receive stack 关闭连接；control bindings 将 apply/reconnect/ACK/status 与 durable store、ChannelManager 正确编排；公开 skill activation 维持 allowlist 语义。
- 已有测试在：`tests/integration/test_channel_bootstrap.py`、`tests/unit/personal_assistant/test_channel_status_ack_handling.py`、`tests/unit/personal_assistant/test_channel_manager.py`、`tests/unit/personal_assistant/test_agent_config_sync.py`（扩展）；新建 `tests/unit/personal_assistant/test_managed_channel_control.py`，理由：它验证新公开 owner 的可观察控制边界，现有文件分别只覆盖 store/manager/transport 层。
- 落层/目录/marker：`tests/unit/`、`tests/integration/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree IM+Gateway 真进程启动并验证 bootstrap/连接路径的命令输出，记录在 `progress.md`。

前端 UI：N/A。

## Roadpoints

### R1 — 固化空 bootstrap 与移除 legacy bridge（TODO）

- 步骤：扩展 bootstrap integration regression，删除 migration/export 与专属测试、transport callback。
- 验证：相关 bootstrap 与 sensitive-config 测试；真实 IM WebSocket bootstrap 请求返回空 items。

### R2 — 建立 managed control 边界与 typed bindings（TODO）

- 步骤：实现 `ManagedChannelControl`、typed bindings/directive 与 upstream mailbox；将 control 策略移出入口并接入 `IMConnectionManager`。
- 验证：新 owner unit、channel manager/status/outbox/reconcile 测试，以及 fatal directive receive-stack close regression。

### R3 — 收口 public skill activation 与入口 wiring（TODO）

- 步骤：提供 `IMAgentConfigSync.ensure_agent_skill_enabled()`，删除私有穿透和 nullable connection closure；由 mailbox 以现有 FIFO 投递 emission。
- 验证：agent config sync/channel 集成测试、相关 ruff；worktree 真 Gateway/IM 入口检查。
