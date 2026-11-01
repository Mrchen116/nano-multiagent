# perf-692：As-built Design

本文在实现后整理。Base 为 `a40d56ff4`。

## 结构与边界

Work.query 用本次请求内的惰性局部函数取得会话列表。只有 list、无固定 target 的 search 和 PA resolve_target 调用该函数，首次取得后本请求复用。固定 target 的来源名称使用已授权会话的同一个标题。

原显式 scope 验证、Agent 可用性、Global 主 session、PA authority、qualifiedUser、目标来源和会话权限检查继续执行。列表模式及跨聊天搜索仍按原规则形成页面，用户可见结果没有新增字段或策略。没有新增长期缓存、工具或持久状态，无 canonical spec delta。

## 同输入证据

精确旧实现 `27aa90acd` 的 Work.query 和已合入 `a40d56ff4` 相同。真实 Work/Messaging 与隔离内存 SQLite，比较 Global/PA × 1/30/300 聊天 × info/describe/read 共 18 组，完整输出全部相等。

| 固定目标 info | 原 SQL / 会话装配 | 新 SQL / 会话装配 |
|---|---:|---:|
| Global，30 聊天 | 698 / 31 | 33 / 1 |
| PA，30 聊天 | 1,555 / 61 | 45 / 1 |
| PA，300 聊天 | 15,055 / 601 | 45 / 1 |

次数仅包含此隔离方法调用，不能解读为生产端到端时延。明确列举或跨聊天搜索依然需要与候选会话数量对应的工作。

## 验证

`conversation-query-hot-path.test.ts` 覆盖跳过列表、撤权、scope、主 session、PA 排除策略和观察者标题。配合 conversation-search、memory-conversation 及原有相关链路共六文件 40 项通过，含真实 IM 子进程与 Relay。IM contracts 类型检查及 diff --check 通过。独立审查与最终 PR 检查另见 code-review.md 和 PR 状态。

## 其余候选

同轮还观察到未到期 heartbeat 会调用 session.ensure。当前探针只证明 RPC 次数，尚未证明重复昂贵执行，而且需要确认 Task 恢复与绑定检查的依赖。本轮不据此改动节律或运行状态。
