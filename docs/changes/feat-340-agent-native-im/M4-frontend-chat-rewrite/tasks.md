# feat-340-M4: frontend chat 全面重写 — Tasks

> 对齐: ../design.md v1

## 目标

`src/IM/frontend/src/features/chat/` 全面重写,匹配原型(`docs/.../attachments/prototype/project/im-chat-page.jsx`):

- 桌面两栏(262px 会话栏 + 消息面板)/ 移动堆叠(列表 ↔ 详情)
- 4 类会话渲染:direct-agent / group / agent-network / 含 tool_calls
- 流式 WS 渲染:`message.created` / `message.delta` / `message.completed` / `tool_call.upserted` / `tool_call.completed`
- Tool Calls 面板(状态点 + duration + 折叠 input/output)、Token Chip(70%/90% 预警)、@mention picker、新建群聊模态
- 会话列表分类标签(All/Agent/Group/Network)、实时搜索、会话头部(Avatar + 标题 + 参与者 + Node 状态 chip + Kind badge + ⚙)
- 消费 M3 提供的 `useAuthStore` / `authFetch` / `useTranslation`
- 彻底迁掉 `ensureSelfUser` 对 `/im/v1/users` 的依赖(M1 已删该端点)
- 删 orphan `src/IM/frontend/src/components/workspace-tabs.tsx`

## 退出标准

- [ ] 桌面两栏 + 移动堆叠,像素级对齐原型
- [ ] 4 种会话样式渲染正确
- [ ] 流式 WS 三事件 + tool_call 两事件接通,消息逐字增量出现
- [ ] 群聊 `@` 触发 picker 200ms 内显示;Enter 选中;Esc 关闭
- [ ] 新建群聊真创建一个会话(POST /im/v1/conversations + participants)
- [ ] Token Chip 在 70%/90% 切换颜色
- [ ] `ensureSelfUser` 与 `/im/v1/users` 完全切断
- [ ] `vitest run` 全绿;`tsc -b` 通过
- [ ] 旧 `chat-workspace-page` / 旧 `im-chat-api` 残余代码删除或缩小为兼容 shim 之外的代码

## 测试策略

| 层 | 怎么测 |
|---|---|
| Reducer | 单元测试 `chat-stream-reducer`:输入一串 WS 事件,断言 conversation cache 结构 |
| API client | mock `fetch` / `authFetch`,验证 URL/method/payload/解析(包括 401 行为) |
| 组件交互 | RTL 模拟 keystroke "@" → picker 出现 + ↑↓/Enter/Esc + insert mention |
| 端到端入口 | 在 `chat-workspace.integration.test.tsx` 用 jsdom + 假 WebSocket + 假 fetch,渲染整页 → 触发"打开会话/发消息/收到 delta/收到 tool_call/收到 completed" → 断言 DOM |
| 视觉 | 现有 design-review skill 兜底(本 milestone 不写 snapshot) |

## Roadpoints

### R1 — 新 chat 数据契约 + thin API client

- 步骤: 写 `chat-types.ts`(对齐 M2 WS payload + 后端 message schema)、`chat-api.ts`(authFetch 封装,conversations 列表 / 单会话 / 历史消息 / 创建消息 / 创建群聊 / 列出 mention 候选 agents)、删除 `mock-chat-api.ts` 中无依赖部分
- 验证: 单元测试每个 API 函数(stub fetch);verify URL/method/payload/error;cover 401 路径(authFetch 已经处理)
- 状态: DONE

### R2 — chat-stream-reducer + WS 订阅

- 步骤: 写 `chat-stream.ts`(打开 `/im/ws/user`,带 Authorization,断线重连;转发原始 WS 事件给监听者)+ `chat-stream-reducer.ts`(纯函数,接受一个 conversation 当前 messages 状态 + WS event → 新状态)
- 验证: reducer 100% 单元覆盖(一系列事件 sequence → 期望快照);stream 模块 with mocked WebSocket → 断言连接 URL、消息派发
- 状态: DONE

### R3 — ConversationList + 分类标签 + 搜索 + NewGroupModal

- 步骤: 写 `components/conversation-sidebar.tsx`(列表条目 + Kind Badge + unread + last_preview + 过滤 tabs + 搜索)、`components/new-group-modal.tsx`(选 agents + 群名 + Create)、`components/avatar.tsx`、`components/kind-badge.tsx`
- 验证: RTL 渲染列表过滤 by kind + 搜索串匹配;new group modal 选两 agent + Create → 触发 `onCreate` callback with selected ids 和 name
- 状态: DONE

### R4 — MessagePane + ToolCallsPanel + TokenChip + MentionPicker

- 步骤: 写 `components/message-pane.tsx`(消息列表 + bubble 渲染 + 头部 + composer)、`components/tool-calls-panel.tsx`、`components/token-chip.tsx`、`components/mention-picker.tsx`、`components/node-chip.tsx`(kind-badge R3 已建)
- 验证: RTL 模拟 keystroke "@P" → picker 出现 candidates 过滤;Enter 提交触发 onSend(text);TokenChip 70%/90% 切换 className;ToolCallsPanel 折叠展开
- 状态: DONE

### R5 — chat-workspace-page 重写(组合 + 路由 + 移动响应式)

- 步骤: 重写 `chat-workspace-page.tsx`(react-query 拉 conversations / messages + WS 订阅 + reducer 应用 + 桌面双栏 / 移动堆叠切换 by `useIsMobile`)、清理 `chat-overview-page` / `chat-detail-page` / `chat-layout.test` 旧文件
- 验证: integration test 端到端模拟"登录 → 打开 chat → 选择会话 → 收到流式增量"
- 状态: TODO

### R6 — 切断 legacy /im/v1/users + 删 WorkspaceTabs orphan

- 步骤: 删除 `im-chat-api.ts` 中 `ensureSelfUser` / `listUsersRaw` 等(及其传递引用);确保所有"取自身 user_id"都从 `useAuthStore().user.id` 取;删 `src/IM/frontend/src/components/workspace-tabs.tsx`(M3 worker 标记 orphan)
- 验证: `grep -r ensureSelfUser src/IM/frontend/src` 无业务调用;`grep -r /im/v1/users src/IM/frontend/src` 仅留测试名作回归标记或全无
- 状态: TODO

### R7 — i18n 增量 + tsc + 全套测试 + entry verification

- 步骤: 把 R3/R4 引入的新 t() 文案 key 增量补 `en.json` / `zh.json`(只追加,不重写);跑 tsc + 全套 vitest;手测启动 vite dev(可选)
- 验证: `npx tsc -b` 通过;`npm test` 全套绿;`grep` 无未补 key
- 状态: TODO
