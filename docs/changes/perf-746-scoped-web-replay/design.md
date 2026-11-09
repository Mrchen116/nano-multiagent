# 按当前可见会话回放

## 方案

- 中心复用 `qualifiedUser` 和 `readableConversationIds` 得到当前可读会话，包括成员、公共群、获准的观察者和仍可读的解散历史。浏览器身份由既有鉴权入口持有。
- 固定原有全局 high water。新增 `conversation_events(conversation_id,event_id)` 索引，从可见会话的事件区间挑选最多 2,001 个轻量事件头，按全局 event ID 排序。阈值和 15 分钟窗只看该用户待补的事件。超过阈值或既有窗口要求时返回原有重同步帧。游标为 0 保留原有首次订阅规则。
- 仅在可以回放时按选定事件 ID 批量读取正文，保持事件顺序与现有 Web 协议。一次同步查询与发送之间无 await。回放结束仍推进连接内游标到固定 high water 并发送现有在线状态快照。保留 HTTP 重新鉴权和跨标签去重。现有资格和实时推送契约继续适用，无 canonical delta。

## 验证安排

独立代码审查复查成员、公群、Agent owner、PA owner、撤权和过期窗口，确认覆盖上限和游标边界。性能对照复用合成大量无关私聊，记录 SQLite 计划、读取正文数和实际帧；真实 Gateway 测试验证少量相关事件夹在 2,001 条无关事件中仍回放，真正超限仍按原协议恢复。现有 Web 恢复测试复用。

| Milestone | 依赖 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-replay | 无 | IM Gateway、中心 schema、回归测试 | [reviewer] 本人事件恢复且其他会话不触发刷新。[worker] 授权 parity、行数上限、回放顺序和计划对照。 |
