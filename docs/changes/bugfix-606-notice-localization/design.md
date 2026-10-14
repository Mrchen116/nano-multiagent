# bugfix-606: As-built Design

> 本文在实现完成后根据实际代码与已确认修复意图整理。

## 实现范围

Base 为 `9ebe12f8553a593f6179784b0276849fb14e5358`。产品改动位于 IM gateway 的 node.system_message handler，以及 Web 的 message.reconciled 类型与 reducer。既有 Messaging.insertMessage 已支持随消息持久化 system_notice 后才发布事件，本次直接复用。

## 最终结构与数据流

认证节点和来源 Agent 的校验沿用既有逻辑。handler 把来源显示名快照与结构化 notice 一起传给 insertMessage；首次 message.created 与历史消息由同一份持久内容构造，无后补 metadata 事件。相同投递身份重试直接取回原消息，不改来源快照、不新增通知事件。

前端 message.reconciled 的完整消息类型包含可选 system_notice，reducer 重建完整快照时保留该字段。既有 formatSystemNotice 按当前 i18n 渲染；无结构化 notice 的历史消息继续展示存储正文。没有新 schema、库、兼容解析或翻译规则。

## 风险、失败与回退

旧版已写入的消息与完整补发事件仍可被前端恢复。未知或历史纯文本通知保持原正文，不猜测其语言或来源。回退对应产品文件即可恢复旧行为；数据库无迁移。

## 验证定位

- `pnpm exec vitest run apps/im-server/tests/e2e/system-notices.test.ts`：真实隔离进程、认证 WS 的首次完整 notice、重复回执、历史语义及唯一持久事件通过。
- 前端 `npx vitest run src/features/chat/chat-stream-reducer.test.ts src/features/chat/components/system-notice-message.test.tsx`：47 tests 通过。
- 修复前服务端首次事件为 null，前端 reconciled 后为 undefined；两个产品断点分别被捕获。
- 完整检查及独立审查追加至 code-review.md。
- 用户验收：待用户亲自体验候选版本，未记录为完成。

## Canonical 文档影响

无 spec delta：恢复 `docs/specs/im/gateway-relay.md` 的“首次完整 message.created”与 `docs/specs/im/web-chat-ux.md` 的当前语言通知契约，未增加新的对外规则。
