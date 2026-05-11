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

## R2 — chat-stream-reducer + WS 订阅

- Context: 原型流式效果(消息逐字 + tool_call running pulse + 完成时 token chip)依赖 M2 的 WS event schema(`message.created/delta/completed`、`tool_call.upserted/completed`)。
- Decision: 拆为两层:`chat-stream-reducer.ts` 纯函数(state + event → state),`chat-stream.ts` 处理 WS 生命周期。Reducer 跳过非 active conversation 的事件;`message.created` 见到重复 id 时去重(防止 optimistic insert + WS echo 双显);unknown 事件类型 / 非 JSON payload 静默丢弃,不抛错。
- Rationale: 决策 3 + 决策 6 + 风险 2。把纯逻辑和 I/O 拆开后,reducer 100% 可单测;`chat-stream` 只测 URL/parse 路径。
  - 不引入 sync 兜底(M4 范围外,决策 3 已经划在 IM 已有 `/im/v1/sync`),M4 只关心活跃会话的 5 个事件类型。
  - WS 认证用 query `access_token=` —— 浏览器 WS handshake 不支持自定义 header,query 是 IM 服务约定的兜底。
- Evidence:
  - Tests: `npx vitest run src/features/chat/v2/` 14/14 pass。覆盖 created/delta/completed 三事件 + tool_call 两事件 + 跨会话隔离 + unknown id 兜底 + WS URL/parse。
- Rollback: 删 `chat-stream.ts` + `chat-stream-reducer.ts` 及其测试。
- Commits: C1=2ad9c1c5 (合并到上一提交), C2=(本提交), C3=(下一提交)
- Next: R3 — ConversationList + 分类标签 + 搜索 + NewGroupModal。
