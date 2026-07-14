# IM Web Chat UX delta — refactor-460

> 对齐 canonical: `docs/specs/im/web-chat-ux.md`。

## ADDED Requirements

### Requirement: Web IM 实时体验在连接恢复后保持一致且不重复提醒

Web IM 的当前会话、会话列表、未读角标、应用内 toast、桌面通知和 Node/Agent 状态共享同一用户事件连续性。
短暂断网或 IM 连接恢复后,已处理事件不再次表现为新提醒;断线期间遗漏的持久消息通过恢复或刷新与历史一致,
非持久状态重新读取当前权威值。

#### Scenario: 恢复连接不重放已处理提醒
- **GIVEN** 用户已经看过某条 Agent 完成通知,随后浏览器网络短暂中断
- **WHEN** 实时连接恢复
- **THEN** 该历史完成事件不再次弹成桌面通知或应用内 toast

#### Scenario: 断线期间的新消息恢复后可见
- **GIVEN** 浏览器短暂断网期间会话收到新消息
- **WHEN** 浏览器恢复网络
- **THEN** 当前会话或刷新后的历史显示该消息,会话列表预览与未读状态最终一致,不产生重复气泡

#### Scenario: 状态在连接恢复后回到当前值
- **GIVEN** 浏览器断线期间 Gateway 的在线状态发生变化
- **WHEN** 浏览器恢复网络并查看 Chat、Nodes 或 Agents 页面
- **THEN** Node/Agent 状态显示当前权威值,不永久停留在断线前快照

#### Scenario: 切换账号不展示前一账号缓存
- **WHEN** 用户退出账号 A 并登录账号 B
- **THEN** Web IM 只展示 B 的会话、未读、通知与 Node/Agent 状态,不短暂复用 A 的页面数据
