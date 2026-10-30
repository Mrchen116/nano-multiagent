# Retired Change Units

本目录保存曾经进入 spec/design、后来在完整交付前被架构演进或后续 change 取代的 unit。

Retired 与 completed history 不同：

- `docs/changes/archive/` 表示变更已经达到可交付状态并进入 current；
- `docs/changes/retired/` 表示该 unit 不应继续实施，内容只能用于理解历史方向；
- 仍有价值但暂未推进的工作继续留在活动区。

| Unit | 退役原因 | 当前入口 |
|---|---|---|
| [`feat-625-auto-review-bounded-retry`](feat-625-auto-review-bounded-retry/spec.md) | 2026-10-29 用户明确废弃独立审核重试交付；未合入 PR #419 内改名为 feat-669，保留原证据，统一所有模型调用的 DSH 恢复由新 unit 承担 | [bugfix-678](../archive/bugfix-678-pa-permission-boundaries/incident.md) |
| [`feat-329-acp-interface-parity`](feat-329-acp-interface-parity/spec.md) | 依赖已删除的 kernel HTTP / ServerClient 架构 | [`SPEC.md`](../../../SPEC.md)、[`kernel specs`](../../specs/kernel/spec.md)、[`CLI specs`](../../specs/cli/spec.md) |
| [`feat-336-generic-channel-architecture`](feat-336-generic-channel-architecture/spec.md) | 被 feat-447 和后续 channel changes 取代 | [`Gateway external channels`](../../specs/gateway/external-channels.md) |
| [`bugfix-494-feishu-sdk-cache-warning`](bugfix-494-feishu-sdk-cache-warning/fix.md) | 2026-10-19 退役：refactor-581 已移除 Python Feishu SDK、ExpiringCache 与对应 seam 测试，旧修复对象不再存在 | [当前 Node SDK 适配器](../../../packages/channels/src/feishu.ts)、[外部渠道契约](../../specs/gateway/external-channels.md) |
| [`feat-444-session-wakeup`](feat-444-session-wakeup/spec.md) | 2026-10-19 退役：原生 Schedule 已覆盖延迟后回到同一主会话，旧方案关于 Cron 隔离会话的前提失效；新消息自动取消、单会话单闹钟等剩余交互若仍需要，应基于原生 Schedule 另立 unit，不再实现旧定时器或固定延迟保证缓存命中的要求 | [Heartbeat 与 Cron](../../specs/gateway/heartbeat-cron.md)、[原生 Schedule 接线](../../../packages/dsh-integration/src/cron-owners.ts) |
| [`refactor-476-permission-transaction-owner`](refactor-476-permission-transaction-owner/motivation.md) | 2026-10-19 退役：refactor-581 已退役 Python AgentEngine、PermissionBroker 与 Coding CLI；审批改由 DSH 服务及 Nano 产品适配承担，旧事务与 CLI 方案不再适用 | [当前审批适配](../../../packages/dsh-integration/src/index.ts)、[Auto 权限规则](../../operations/auto-permissions.md) |
| [`refactor-478-gateway-control-rpc-boundary`](refactor-478-gateway-control-rpc-boundary/motivation.md) | 2026-10-19 退役：TypeScript 重写已统一 IM pending 请求生命周期并分离 Channels 传输，旧 11 套 waiter 与 Python connection 改造对象消失；不据此宣称当前 Node 业务分派无需后续改进 | [IM 请求关联](../../../apps/im-server/src/gateway.ts)、[Channels 传输](../../../packages/channels/src/index.ts)、[当前架构](../../../SPEC.md) |
| [`feat-539-claude-auto-permission-migration`](feat-539-claude-auto-permission-migration/spec.md) | 2026-10-19 退役：旧 Auto 迁移草稿已被 feat-552、refactor-581 与 feat-615 取代，当前支持 CC 工作区快速放行、两阶段分类及逐 Agent 切换 Codex 策略 | [feat-615](../archive/feat-615-agent-approval-strategies/spec.md)、[Auto 权限规则](../../operations/auto-permissions.md) |

Retired unit 不得直接恢复；若仍有用户问题，应以当前代码和 specs 重新立项。
