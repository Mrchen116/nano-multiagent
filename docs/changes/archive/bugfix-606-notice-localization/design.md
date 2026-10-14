# bugfix-606: As-built Design

> 本文在实现完成后根据实际代码与已确认修复意图整理。

## 实现范围

Base 为 `9ebe12f8553a593f6179784b0276849fb14e5358`。产品改动位于 IM gateway 的 node.system_message handler，以及 Web 的 message.reconciled 类型与 reducer、会话摘要的结构化通知字段与渲染。既有 Messaging.insertMessage 已支持随消息持久化 system_notice 后才发布事件，本次直接复用。

## 最终结构与数据流

认证节点和来源 Agent 的校验沿用既有逻辑。handler 把来源显示名快照与结构化 notice 一起传给 insertMessage；首次 message.created 与历史消息由同一份持久内容构造，无后补 metadata 事件。相同投递身份重试直接取回原消息，不改来源快照、不新增通知事件。

前端 message.reconciled 的完整消息类型包含可选 system_notice，reducer 重建完整快照时保留该字段。既有 formatSystemNotice 按当前 i18n 渲染；无结构化 notice 的历史消息继续展示存储正文。会话 REST 摘要按原最新消息时间关联其持久 notice，Sidebar 复用同一 formatter；普通消息快路径清除前一 notice，语言切换使摘要重新计算。没有新 schema、库、兼容解析或翻译规则。

## 风险、失败与回退

旧版已写入的消息与完整补发事件仍可被前端恢复。未知或历史纯文本通知保持原正文，不猜测其语言或来源。回退对应产品文件即可恢复旧行为；数据库无迁移。

## 验证定位

- `pnpm exec vitest run apps/im-server/tests/e2e/system-notices.test.ts`：真实隔离进程、认证 WS 的首次完整 notice、重复回执、历史语义及唯一持久事件通过。
- 前端 `npx vitest run src/features/chat/chat-stream-reducer.test.ts src/features/chat/components/system-notice-message.test.tsx`：47 tests 通过。
- 修复前服务端首次事件为 null，前端 reconciled 后为 undefined；两个产品断点分别被捕获。
- 完整检查及独立审查追加至 code-review.md。
- 用户验收：2026-10-14 用户确认“这两个都可以合入。”，接受当前候选的时间线与摘要语言一致性。

## Canonical 文档影响

首次完整事件与时间线本地化恢复既有契约；实际浏览器检查发现会话摘要仍显示英文，因此在同一 unit 中增加摘要一致性。最窄 delta 位于 `specs/im/web-chat-ux.md`，用户确认后已归并到 canonical web-chat-ux.md，并更新包入口摘要；保留 main 中 bugfix-607 的输入框行为契约。
