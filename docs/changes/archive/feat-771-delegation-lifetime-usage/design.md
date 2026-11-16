# feat-771 派工历史累计用量

[需求](spec.md)

## Changelog

## 现状分析

Web 派工图通过 `/work/delegation` 读取中心的 WorkSummaries。SQLite 按活动索引筛选候选，沿会话父链补祖先，随后按窗口查询轮次用量。WorkSync 的追加事务已经维护每轮投影。会话注册固定归属和 scope，PA 主会话替换保留历史。feat-764 的权限校验、活动索引、分页与路径行为继续适用。

## 架构与接口

IM 中心从已投影轮次维护累计。汇总表以根 Agent ID 和会话 ID 为键，空会话键代表此 Agent 的全部主会话。每个已结束的轮次对所属会话贡献一个轮次、零或一个用量报告，以及已报告的 token。主会话轮次同时贡献给该 Agent 的主会话汇总。旧主会话保留同样的归属。派工显示自己的会话汇总。真实 0 通过报告数区分。

结束事实使用持久的 finished_at。新轮次采用事实声明的结束时间、节点观察时间或中心为事件持久化的观察时间。状态变化保留该标记。启动回填先从中心已保存的结束事实补齐缺少标记的旧轮次，按明确 turn ID 匹配，只有 run ID 时沿用会话内 run ID 的关联。初始化与增量随后共用结束标记。结束投影在追加事务内按新旧贡献差量更新。补报、修正和重试不会重复计轮。Agent 删除同时清除该根的汇总。标记补齐、汇总回填和版本标记通过既有 SQLite 启动事务提交。

活动窗口维持候选和祖先分类。候选页继续使用窗口索引。附带的祖先仍按索引判断是否只是路径。读取累计只按当前返回的节点主键查询，主卡片查询 Agent 汇总键。工作 API 继续使用 `usage.total_tokens`、`reported_turns`、`missing_turns`，值的口径改为历史。Web 卡片显式使用「轮累计」，报告缺失和祖先路径说明可以同时出现。 图查询复用面板既有的 Work 更新与恢复刷新。各窗口离开后丢弃独立缓存，切回时读取新响应。

## 风险与回退

首次启用从中心历史轮次一次性构建汇总。若回滚至旧版后启动过服务，重新启用前由部署员按 [条件回填操作](deployment-prompt.md) 恢复。验证在隔离数据库执行。

## 本次审查安排

| 问题 | 能力 | 证据 |
|---|---|---|
| 活动范围与累计是否独立，汇总归属与覆盖是否正确 | 独立代码审查和产品旅程 | 真实隔离 IM Work HTTP 接口对比 2 小时与 3 天，Web 回归先打开三天，模拟新增轮次，再切两小时并切回三天，核对累计使用新响应 |
| 补报、重放、历史初始化是否保持总量 | 独立代码审查 | 真实追加和 SQLite 验证省略时间、补报和历史一致，隔离副本验证重新回填 |
| 请求成本是否随历史轮次增长 | performance-review | 查询计划确认使用会话/Agent 汇总键，活动查询沿用时间索引 |

## 契约层增量

- [Agent Work delta](specs/im/agent-work.md)

## 一次性部署迁移

常规升级由 SQLite 启动事务自动回填。旧版中心回滚后重新启用时，使用 [条件回填操作](deployment-prompt.md)。

## Runbook for Reviewer

IM 使用 `pnpm exec vitest run apps/im-server/tests/e2e/work-summaries.test.ts` 启停隔离 HTTP/WebSocket fixture，派工 GET 为健康与行为入口。Web 用 `pnpm exec vitest run src/IM/frontend/src/features/settings/agents/agent-work-panel.test.tsx` 验证卡片与范围切换。fixture 自行生成身份和会话。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 派工历史累计 | 无 | 1 | IM Work 汇总与 Web 派工卡片 | [reviewer] 窗口只影响活动节点，已报告历史累计可读且归属正确。 [worker] 接口、回填、补报和 Web 回归通过，查询读取汇总键。 |
