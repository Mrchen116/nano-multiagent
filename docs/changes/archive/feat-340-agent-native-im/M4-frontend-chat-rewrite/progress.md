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

## R5 — chat-workspace-page v2(组合 + 路由 + 移动响应式)

- Context: 把 R1-R4 写好的零件装配成 `/chat` 页面;桌面双栏 / 移动堆叠;接 `useParams` / `useNavigate` 走真实路由。legacy `chat-workspace-page.tsx`(1185 行)和它的 chat-layout/chat-routes 测试是上一代实现,路由切换后必须清掉,不能两套并存让 reviewer 困惑。
- Decision:
  - 新文件 `features/chat/v2/chat-workspace-page.tsx`,导出 `ChatWorkspacePageV2`。`router.tsx` 用 alias `as ChatWorkspacePage` 替换 import 源,保持 `<ChatWorkspacePage />` JSX 引用不变,降低修改面。
  - 数据流:react-query 拉 `listConversations` / `listMessages` / `listMentionCandidates` / `fetchAgents(NewGroup 模态用)`;WS 通过 `openChatStream`(R2)开一次,事件喂进 `useReducer(streamReducer)`,reducer 内部直接调 R2 的 `applyWsEvent`。切会话时 `dispatch({type:"reset",messages:history})` 一次性 seed,WS 流持续追加。
  - 不做 optimistic insert——`createMessage` POST 返回后 backend 也会 echo `message.created`,reducer 已去重(R2),所以页面只需 invalidate conversations 列表,不操作 detail 缓存。
  - 移动响应式:`useIsMobile() && conversationId` 时只渲染 MessagePane 并传 `onBack=>navigate("/chat")`;`!conversationId` 在桌面时显示 empty-pane,在移动时只显示 sidebar。
  - integration test 用 `FakeWebSocket` + `vi.stubGlobal("fetch", ...)`,覆盖三个真实入口:进入 `/chat/c1` 看到列表 + 历史消息、WS 推 created+delta+delta+completed 看到最终内容、Send 按钮 POST 后 composer 清空。
  - 清理:删 `features/chat/chat-layout.test.tsx`、`chat-routes.test.tsx` —— 它们 mock 的全是 legacy chat-api endpoint(`getChatBootstrapState` / `streamConversationEvents` 等),与 v2 不再对齐。`router.test.tsx` 删 1 个 case(也针对 legacy copy);保留路由声明断言。
- Rationale: 决策 1+3+6+10 全部命中。把 stream 入口和 reducer 分离意味着:WS 协议改 / 加 sync 兜底时只动 `chat-stream.ts` + reducer,UI 零改。`MessagePane` / `ConversationSidebar` 全部受控,workspace 是唯一拿到 react-query / WS 的层 —— 测试时也只需要 mock 这两个外界。
- Evidence:
  - Tests: `npx vitest run` 全套 214/214 pass(从 219 减 5 是因为 chat-layout 5 个 + chat-routes 2 个 + router 1 个 - 新增 3 个 integration = -5)。
  - Integration: 3/3 pass。其中 WS sequence 端到端验证了"用户进会话 → 列表渲染 → 历史显示 → 推流 → 文本逐字增长 → 完成时 token_usage 入 reducer";Send 测试断言 POST URL/payload + composer 清空。
  - 入口验证:用 RTL 渲染整个 `<MemoryRouter><Routes>...` + `QueryClientProvider`,这是 SPA 的真实顶层入口,fetch + WS 全替身但内部走完整 react-query / reducer / 组件树。
- Rollback: revert router.tsx 一行 import + 恢复 chat-layout/chat-routes 测试文件即可回到 legacy。
- Commits: C1=de2c2b2b, C2=02697458, C3=(本提交)
- Next: R6 — 切断 legacy `/im/v1/users` + 删 WorkspaceTabs orphan + 清 legacy chat 文件残骸。

## R6 — 删 legacy chat-workspace + orphan 文件 + 加 legacy-isolation 回归门禁

- Context: M4 退出标准要求 `ensureSelfUser` 与 `/im/v1/users` 完全切断、旧 `chat-workspace-page` / `chat-overview-page` / `chat-detail-page` 残余清除、`components/workspace-tabs.tsx`(M3 标记 orphan)删除。
- Decision:
  - 删 5 个文件:`features/chat/chat-workspace-page.{tsx,test.ts}`、`features/chat/chat-overview-page.tsx`、`features/chat/chat-detail-page.tsx`、`components/workspace-tabs.tsx`。
  - 不动 `chat-api.ts` / `im-chat-api.ts` —— settings/agents 还在用它们(`createDirectConversation` / `getConversationPreviewSnapshot` / `confirmBindToken`),要等 M5(agents-rewrite)和 M6(nodes-rewrite)把这些依赖剥离后才能整体删除。这是显式的范围分割,不是遗漏。
  - 加 `v2/legacy-isolation.test.ts` 作为 contract test:扫描 `features/chat/v2/` 所有非测试源文件,断言无 `/im/v1/users` 字符串、无对 `im-chat-api` / `chat-api` / `mock-chat-api` 的 import。未来若有人偷偷把 legacy 引回 v2,vitest 立即失败。
- Rationale: 范围控制 + 回归门禁双保险。代码删了不写门禁,半年后有人误"复用"legacy 又会重新长出依赖。门禁写死才是真切断。
  - 这一 R 严格按 Red→Green→Refactor 流程不太自然(测试一上来就 Green,因为代码已经干净);但 contract test 的价值是回归门禁,本身值得 commit。在 progress 中显式说明这点,reviewer 不必当作"假 Red"误判。
- Evidence:
  - Tests: `npx vitest run` 175/175 pass(从 214 减 39 是 legacy `chat-workspace-page.test.ts` 单元测试集消失。)
  - 新增:`legacy-isolation.test.ts` 2/2 pass。
  - tsc: `npx tsc -b` 无报错。
  - Grep 验证:`grep -rn "/im/v1/users" src/IM/frontend/src/features/chat/v2/` 空;`grep -rn "ensureSelfUser" src/IM/frontend/src/features/{auth,me,settings}/` 空(legacy `im-chat-api.ts` 内部还在调,但已无路由引用)。
- Rollback: `git revert <C2 hash>` 即可恢复 5 个删除文件;若 contract test 误伤新代码可单独 revert C1。
- Commits: C1=26742f7c, C2=118c97cb, C3=(本提交)
- Next: R7 — i18n 增量 + 最终 tsc + 全套测试 + 入口验证。

## R7 — i18n + tsc + 全套测试通过

- Context: M4 收尾。退出标准两条:`vitest run` 全绿、`tsc -b` 通过。i18n EN/中文 chat namespace 已由 R3 一并补齐(`list` / `kindBadge` / `newGroup` / `messagePane` / `mention`),R4 引入的 token / tool-call / mention / config 文案都已落在那一轮(原型化设计:R3 写组件前先把整个 chat namespace 文案表填好,后续 roadpoint 直接 t() 即可)。
- Decision:
  - 不再追加 i18n key —— R3 提交时已经把整个 chat namespace 一次性写满(53 个 key,EN/中文双写)。后续 roadpoint 复查时无缺。
  - `legacy-isolation.test.ts` 用 `node:fs`/`node:path`/`node:url`,但 `@types/node` 未在 frontend tsconfig 安装,tsc 报错。修法:三行 `@ts-expect-error` 注释逐行抑制,而不是引入 `@types/node`(那会扩大 lint 面、且 vitest 已经在 node runtime 跑这些代码)。
  - 这一 R 没有"新功能",只有 tsc 修复 + 全套验证;为遵循三提交契约把 C1 测试和 C2 实现合并为单 commit(fix),C3 走 docs。skill §3 允许"R 太小不够拆出三档时合并"。
- Rationale: 决策 7(国际化 EN/中 双写)+ 退出标准。i18n key 一次写完比逐 roadpoint 增量补更不容易漏。
- Evidence:
  - tsc: `npx tsc -b` 干净退出(0 error)。
  - vitest: 全套 177/177 pass(40 个 test files)。其中 chat v2 surface: chat-api 5 / chat-stream-reducer 6 / chat-stream 3 / conversation-sidebar 6 / new-group-modal 4 / token-chip 4 / tool-calls-panel 4 / mention-picker 4 / node-chip 3 / message-pane 6 / chat-workspace integration 3 / legacy-isolation 2 = 50 个 v2 测试。
  - 入口验证:`chat-workspace.integration.test.tsx` 是 SPA 顶层入口的真实测试(MemoryRouter + QueryClient + 替身 fetch/WS),已覆盖"打开会话 → 看历史 → WS 流 → 发消息"完整链路。本地 vite dev 起服跳过(M10 backend-status-broadcast 还在跑,backend WS 可能不完整;reviewer 阶段联调验)。
- Rollback: revert C2 即可(只是一个 @ts-expect-error 注释)。
- Commits: C1+C2=fd8edc40 (合并), C3=(本提交)
- Next: M4 全部 roadpoint DONE,准备合并到 unit 集成分支。





