# Code Review: bugfix-624-pa-revoked-read-recovery

- review_mode: `full`（Bugfix lite 固定完整 diff）
- verdict: `pass`
- reviewed_at: `2026-10-20T04:50:04Z`
- executed_base / effective_base: `5adb013c2fd7357f2590cf1c7ba551f38bbc673f`
- head / validated_at / effective_through: `c6370007a9541887466903eeaba79aa2534812d0`
- 独立静态审查；未参与受审实现。范围为指定 base..head 的全部 2 个文件、49 行新增及 2 行删除，并核对实际来源刷新、工具读取和恢复 reconcile 调用方。未修改产品代码或测试，未操作生产。

## Findings

```json
[]
```

## 审查结论

未发现需 maintainer 处理的具体缺陷。

- `revokeSource` 在删除 Inbox 条目前，通过持久 fragment 的 `seq` 关联真实来源，再同时按 `agent_id` 与 `target` 撤销 saved read；不依赖新旧模型正文是否含顶层 target。相同 target 下其他 Agent 的 read 不会因目标字符串相同而被清除。原有 Inbox、分片和来源快照撤销继续生效，未改动会话历史。
- `commitRead` 保留原有完整正文 digest、prepared content 和图片数量验证；遇已不存在的 Inbox 行时回滚整个事务并返回 false，因此此前循环中写入的 fragments、consumed、ingestions 均不部分提交。有效 read 继续沿原有分片完整性规则摄取。
- 实际恢复链为 `recover → restorePersonalInputs → refreshPersonalSources/revokeSource → reconcile`。`reconcile` 仅在 `commitRead` 为 true 时追加 `inbox_read_committed`，false 后继续处理后续持久事件；回执从仍存在 Inbox 行关联的 `completedInputs` 获取。本修改可解除孤立 fragment 的已知异常阻断，不将被撤销输入重新记作消费完成。
- 当前 PA 来源控制与 Global Inbox 持久摄取契约已覆盖此行为，无 spec delta。

## 验证与证据边界

- 已核对 `/tmp/bugfix624-red.log`：新增两例在旧实现均以 `Cannot read properties of undefined (reading 'payload')` 失败，原有 9 例通过。
- 已核对 `/tmp/bugfix624-green.log`：Inbox 11/11 通过。新增用例分别覆盖旧消息级 target 投影撤销及另一 Agent 保持可消费，以及已持久孤立 read 的整页回滚、仍有效消息重新读取与摄取。复用该有效窄测证据，没有重复全量。
- 已核对 `/tmp/bugfix624-build.log`：各包构建完成。构建日志中的安装包版本字段仍为 base SHA，不能据此声称该修复已发布或部署。
- 独立执行指定 diff 的 `git diff --check`，通过。
- 本报告不声称 typecheck、完整 backend 测试、真实数据库副本恢复、真实 runtime/model 回复或生产交付已完成；这些由 caller 的独立验证记录负责。生产统计和根因上下文来自 `fix.md`，本审查未直接读取生产数据库。
