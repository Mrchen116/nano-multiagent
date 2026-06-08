# M12: gateway-config-reconcile — 全量对账 reconcile-on-connect

## 目标

实现 gateway 在 WS bind 完成（含断线重连）后，对本 node 下所有 agent 拉一次 IM 权威 profile
做全量对账，使 enabled/features/cadence/active_hours 收敛到 IM 真值，消除
"关闭 heartbeat 后不重启 gateway 仍持续打 heartbeat" 的 bug C。

## 退出标准

- `[reviewer]` 在 IM 关闭 heartbeat 后无需重启 gateway，数个 tick 内停止打 heartbeat
- `[reviewer]` gateway 断连重连 IM 后，agent 配置（enable/cadence/active_hours）收敛到 IM 真值
- `[worker]` reconcile-on-connect 拉全量 profile 覆盖内存 config 的单测（模拟"漏一次增量推送"场景）
- `[worker]` 对账与增量推送竞态用 `profile_version` 取大的断言
- `[worker]` `pytest -m "not e2e"` 全绿（含 im_service）

## 测试策略

**类型**：纯后端逻辑，无前端。

**测试层级**：
- 单元测试：`tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py`
  - 场景 1：对账时拉到 enabled=False，更新内存 config（模拟漏一次增量推送）
  - 场景 2：对账 profile_version < 现有内存版本 → 保留内存版本（取大）
  - 场景 3：对账 profile_version >= 内存版本 → 更新内存
  - 场景 4：对账在 WS bind 完成（connect_once / 每次 reconnect）后触发
  - 场景 5：对账 HTTP 失败不中断连接生命周期（错误日志，但不 raise 断开 WS）

**真实入口验证**：本 milestone 无 HTTP endpoint 或 CLI 变化；验证通过"模拟漏一次增量推送"
的集成场景（单测中用真实 _IMConfigSyncClient 逻辑）。

## UI 状态矩阵

N/A（纯后端）

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | 红测：reconcile-on-connect 场景 | DONE |
| R2 | 实现：_reconcile_all_agents 方法 + 连接生命周期接线 | DONE |
| R3 | 文档：progress.md + spec.md delta + 全树验证 | DONE |
