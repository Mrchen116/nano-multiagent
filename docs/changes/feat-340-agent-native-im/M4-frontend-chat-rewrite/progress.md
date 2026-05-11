# feat-340-M4 — Progress

## R1 — chat-api v2 + types

- Context: M4 全部 UI 都要拿到 conversations / messages / mention 候选 / 创建群聊 几个原子操作。旧 `im-chat-api.ts` 把 mock-fallback、binding token、snapshot cache 等糊在一起,直接复用会把 v2 章法搞坏。
- Decision: 在 `features/chat/v2/` 起一份精简 client:`chat-api.ts` 全部走 `authFetch` (M3 提供),`chat-types.ts` 只声明 wire 形态。Actor-first 发送(`{ type:'user', id: self.id }`)由 `useAuthStore().user.id` 注入,不再走 legacy `ensureSelfUser`。`listMentionCandidates` 把 `/im/v1/agents` 与会话 participants 取交集(spec Q8)。
- Rationale: 决策 1 + 决策 10 + spec Q8 都已锁;v2 与 legacy 并行存在,逐步迁可控。`classifyConversationKind` 把 `type+direct_kind+participants` 合并为单 enum,UI 一处分类、KindBadge 直消费。
- Evidence:
  - Tests: `npx vitest run src/features/chat/v2/` 5/5 pass。覆盖 Bearer 注入、列表 / 历史 / 创建消息 / 创建群聊 / mention 交集 5 条主路径。
  - Suite: `npm test` 179/179 pass。
  - Entry: 见 R5 端到端 integration。
- Rollback: 删整个 `src/IM/frontend/src/features/chat/v2/` 目录。
- Commits: C1=7925c0b8, C2=4ea0b981, C3=(本提交)
- Next: R2 — chat-stream-reducer + WS 订阅。
