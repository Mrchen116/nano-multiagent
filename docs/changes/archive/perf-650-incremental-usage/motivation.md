# perf-650: 增量用量计量

## 原始诉求

> 你的范围：审计第1项，usage.read 重复扫描全部子会话及历史。主要所有权 packages/dsh-integration/src/usage.ts、usage.read RPC局部接线、packages/personal-assistant/src/usage.ts及相应用量存储/测试。真实readUsage +400个未变化child，两次调用各observe401次，PA每次turn/end触发根recover；dirty仅合并同时到达事件。报告runtime/findings.md R1与runtime/usage-count.mts/jsonl可复核。
>
> 目标：正常持续运行与重复读取时用量处理成本跟新完成轮次/变化会话相关，避免每轮重新打开全部冷子会话；保留准确token统计、fork继承不重复计量、稳定run id、ACK重试幂等、重启/断线恢复及存量兼容。首次恢复可以有明确且有界的重建成本，但不能每个turn/end都重扫。基于公开DSH能力设计最小增量方案，不预设必须上新数据库/通用缓存框架。
>
> 验收：真实函数、足量不变child、重复读取、单child新turn、根与子并行结束、ACK丢失/重启恢复计数正确。分别报告冷恢复与热增量处理量/耗时。不要修改input-evidence.ts、model-fallback.ts或SingleThread输入查询优化；这两项由另两unit负责。

## 澄清记录

用户通过任务派发已授权独立 perf Full unit、设计和实现、独立门禁、归档、Ready for review PR 与 required CI 全绿；不自动 merge 或部署。目标和范围已确定，无待澄清项。

## 现状痛点

审计基线 `236a4698c7a8a2d03efa00c35049914d2422771d`，本次核实 main `893d903a00dff83c47b08310ed528b71eaae6786`，相关代码仍每次全扫。证据位于 `/Users/czj/.codex/reports/nano-performance-audit-20261023-2247/runtime/findings.md` R1 与 `usage-count.mts/jsonl`：真实 readUsage 配 400 个不变子会话，每次调用显式 observe 401 次，两次累计 802；此外 listDescendants 自身遍历 catalog。该结果是隔离观察次数测量，不是生产 I/O 或耗时占比。

## 目标状态

首次恢复可按可达会话和已有历史线性重建；同一 runtime 正常运行期间，不变的 400 个子会话在第二次及后续读取中不再打开；单子会话完成新轮次只处理该会话新增事实，根与子同时结束均完整计量。正常 PA 读取只传输、写入新增用量。分别量化冷恢复与热增量处理量和耗时，准确性优先于速度。

## 用户侧验收标准（不变性）

用户继续发起普通及带后台子任务的 Agent 工作，使用量保持同一计数口径；断线恢复后最终记录与持续在线一致。本 unit 不改聊天气泡的 token 展示链路、客户端布局或接口权限。

### Requirement: 完成工作按实际用量计量

#### Scenario: 普通与后台工作
- **WHEN** 用户发起普通 Agent 工作及包含后台子任务的工作并等待完成
- **THEN** 用量统计包含实际完成的主任务与子任务消耗，继承历史不重复收费，与变更前计数口径一致。

### Requirement: 恢复不重计或漏计

#### Scenario: 断线与重启恢复
- **WHEN** 用量确认丢失、连接中断或节点重启后恢复连接
- **THEN** 已完成工作最终完整计入一次，已确认的历史不会再次收费，与持续在线的结果一致。

## 影响范围

DSH integration 用量读取与局部 RPC 接线，PA 用量增量读取与既有存储/投递边界，相关测试。无其他 unit 的实现依赖；不改 session.descendants、input-evidence、model-fallback、SingleThread，不优化其他审计项。

## 迁移与回滚策略

原生日志、turn 标识、PA 既有用量表和 IM 幂等键保持兼容。进程重启可从原生日志重建；回滚后旧版本可继续读取相同数据。发现漏计、重计、持久性或安全边界回归时停止交付并修正，不以关闭审核或修改上游换取性能。
