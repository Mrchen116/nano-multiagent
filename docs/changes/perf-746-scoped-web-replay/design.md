# 按当前可见会话回放

## 方案

- 中心复用 `qualifiedUser` 和 `readableConversationIds` 得到当前可读会话，包括成员、公共群、获准的观察者和仍可读的解散历史。浏览器身份由既有鉴权入口持有。
- 固定原有全局 high water。用 `conversation_events(conversation_id,event_id)` 索引在 `(cursor, top]` 内取任意最多 2,001 个可见事件头，超限探测不排序，找到第 2,001 个即停止。超过 2,000 个可见待补事件时返回原有 `gap_too_large`。正游标若有任何可见待补事件早于 15 分钟截止点，返回原有 `replay_window_expired`，即使所有待补均过期；无可见待补事件时不降级。零游标（显式 resume 与兜底）仍免时间判断，数量按可见事件计。
- 仅在可以回放时按选定事件 ID 批量读取正文并按全局 ID 排序，超限与过期均不读正文。一次同步查询与发送之间无 await。回放结束仍推进连接内游标到固定 high water 并发送现有在线状态快照。保留 HTTP 重新鉴权和跨标签去重。可见窗口及降级结果见 [用户事件契约增量](specs/im/agents-nodes.md)。

## 验证安排

独立代码审查复查成员、公群、Agent owner、PA owner、撤权和过期窗口，确认覆盖上限和游标边界。性能对照覆盖大量无关私聊及大量可见积压，记录 SQLite 计划、读取正文数和实际帧；真实 Gateway 测试验证少量相关事件夹在 2,001 条无关事件中仍回放，真正超限、全部过期、没有可见积压和零游标保持上述恢复规则。现有 Web 恢复测试复用。

| Milestone | 依赖 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-replay | 无 | IM Gateway、中心 schema、回归测试 | [reviewer] 本人事件恢复且其他会话不触发刷新。[worker] 授权 parity、行数上限、回放顺序和计划对照。 |
