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

## R3 — ConversationSidebar + KindBadge + NewGroupModal + Avatar

- Context: 桌面左栏 262px 会话列表 + 4 类过滤标签(All/Agent/Group/Network)+ 实时搜索 + 新建群聊入口;原型 `im-chat-page.jsx` ConvSidebar + NewGroupModal 部分是这一 roadpoint 的视觉契约。
- Decision: 拆出 4 个原子组件:
  - `conversation-sidebar.tsx` 接 `Conversation[]` + active id + onSelect / onNewGroup;内部 useState 管 filter+search;过滤逻辑直接调 `classifyConversationKind`,KindBadge 渲染右侧角标。
  - `new-group-modal.tsx` 接 `agents` 列表 + onClose/onCreate;受控 selected + name;Create 按钮在 selected 为空时 disabled,name 留空时 fallback 拼参与者名称。Radix 暂不引入,先用原生 `<dialog>` 替代项 `<div role="dialog" aria-modal>`(R5 整合时若需要 portal 再换)。
  - `avatar.tsx` 通用头像(initials + optional status dot)被两处复用。
  - `kind-badge.tsx` 把 4 种 ConversationKind 各自一段 i18n key + 一段配色 className。
  - 样式 className 命名 `chat-*` 全部待 R7 增量补 global.css(本 roadpoint 只锁结构 + i18n 文案,不写视觉)。
- Rationale: 决策 4(4 类会话渲染)+ spec Q4(NewGroup 表单字段) + Q8(mention candidates ⊆ participants)。把 sidebar 拆成自治组件,R5 主页面只负责把 `conversations` 状态喂进来,符合 unidirectional dataflow。新群聊不在此 roadpoint 真发 POST(那是 R5 chat-workspace 的事),只 onCreate 回调出 ids+name。
- Evidence:
  - Tests: `npx vitest run src/features/chat/v2/` R1+R2+R3 共 24/24 pass。`conversation-sidebar.test.tsx` 覆盖:渲染 4 条会话 + 过滤 group / 搜索串匹配 / 点击高亮选中。`new-group-modal.test.tsx` 覆盖:勾选两 agent → Create 按钮带 (2) → onCreate(payload.agentIds.length===2,name fallback 为 join)。
  - 实施期把 C1(测试)+ C2(实现)写进了同一个 commit(c7bc7cb7),没有严格走 Red→Green 双提交。下游 reviewer 注意:该 commit 标题是 C1 但 body 含 C2;视为单提交。后续 roadpoint 恢复三提交。
- Rollback: 删 `components/{conversation-sidebar,new-group-modal,avatar,kind-badge}.{tsx,test.tsx}` + i18n key 段。
- Commits: C1+C2=c7bc7cb7 (合并), C3=(本提交)
- Next: R4 — MessagePane + ToolCallsPanel + TokenChip + MentionPicker + NodeChip。

## R4 — MessagePane + ToolCallsPanel + TokenChip + MentionPicker + NodeChip

- Context: 右栏消息面板需要满足:消息列表(含 tool_calls 折叠 sidecar)、composer(Enter 发送/Shift+Enter 换行)、@mention picker(只在 group / agent-network 触发)、头部 token chip(70%/90% 阈值)、node chip(在线/离线 dot)、KindBadge、⚙ Config 入口。原型 `im-chat-page.jsx` line 217-315(MessagePaneView) + line 109-133(MentionDropdown) + line 135-151(NodeChip) 是视觉契约。
- Decision: 拆 5 个原子组件 + 1 个聚合组件:
  - `token-chip.tsx`:三档 variant(normal/warn/critical),pct = context_used/context_window,>=0.9 critical / >=0.7 warn,usage=null 渲染 null。`button` 元素方便 hover tooltip。
  - `tool-calls-panel.tsx`:顶层 toggle 显示 "N tool call(s)" + 任意 running 时显示 running hint;展开后每行单独可折叠 input/output(JSON.stringify)。空数组渲染 null。
  - `mention-picker.tsx`:prefix-startsWith filter(对齐原型);`onMouseDown + preventDefault` 替代 click 防止 textarea 失焦。无匹配渲染 null(避免空 dropdown 推动 layout)。
  - `node-chip.tsx`:online 时 chat-node-chip--online;无 nodeName 渲染 null。
  - `message-pane.tsx`:聚合所有原子。复用 chat-types `classifyConversationKind` 判 isGroup;`MENTION_RE = /@(\w*)$/` 匹配末尾 @ 段,选中时把末段 token 替换为 `@DisplayName ` 并 focus textarea。`latestUsage` 取最后一条带 token_usage 的消息(对齐 spec — 最新状态优先)。Enter 提交 / Shift+Enter 换行。direct conversations 不激活 mention picker,即使输 @ 也不弹。
- Rationale: 决策 5(@mention picker UI 必备)+ 决策 6(tool_call 状态可视化)+ spec Q5(mention 只在 group)+ spec Q7(token chip 三档)。组件全部受控、纯 props,不引入内部 fetch,所以 R5 chat-workspace-page 才是唯一懂 react-query / WS 的地方。
  - prototype 在 button 内层用 div 嵌套(原 JSX);RTL 测 `getByRole("button", { name })` 时按"accessible name"匹配,所以我用 `<button>` 容纳所有 nested span 而非两层 button。
  - tool-call OUTPUT 时 prototype 是字符串;但 wire schema 没强制 string,所以做了 `typeof === 'string'` 兜底 + JSON.stringify(非吞错,JSON.stringify 失败由 React 抛错,合规 §0.2)。
- Evidence:
  - Tests: `npx vitest run src/features/chat/v2/` 45/45 pass;`npx vitest run` 全套 219/219 pass。
  - Coverage: token-chip 4 / tool-calls-panel 4 / mention-picker 4 / node-chip 3 / message-pane 6 = 21 新增 tests。
  - Entry: 整页 integration test 留给 R5(组合 chat-workspace-page)。
- Rollback: 删 `components/{token-chip,tool-calls-panel,mention-picker,node-chip,message-pane}.{tsx,test.tsx}`。
- Commits: C1=d5542102, C2=71d991a5, C3=(本提交)
- Next: R5 — chat-workspace-page 重写(react-query + WS + 桌面 / 移动响应式)。


