# M153 Progress - Web IM 会话列表与工作区产品化收口

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M153`
- 已确认 branch：`milestone/M153`
- 已确认约束：不创建额外 worktree，只在本分支完成实现、测试、提交。
- 先阅读了以下关键前端文件并据此收口：
  - `src/IM/frontend/src/app/App.tsx`
  - `src/IM/frontend/src/features/chat/chat-overview-page.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - 对应测试：`router.test.tsx`、`chat-layout.test.tsx`、`chat-routes.test.tsx`、`chat-workspace-page.test.ts`、`message-pane.test.tsx`

## 基线判断
- 顶栏存在明显原型文案 `P1-P7 Skeleton`。
- `chat-overview-page` 仍使用“initializing”式占位文案。
- 会话列表说明与卡片层级偏 demo，缺少稳定空态与产品级预览。
- `chat-workspace-page` 的 SSE 合流逻辑把 `message.sent` / `message_created` 一律写成 `is_mine: false`，并且会把带 `sender_type` 的 `message.delivered` 也走 relay synthetic 分支，容易造成本端消息被重绘成对端/agent 视图，形成“只看到一边消息”的观感。

## 执行策略
1. 先替换最外层壳与 overview 文案，去掉 prototype 标签。
2. 再收口会话列表与消息面板空态，把列表/工作区呈现拉到产品可交付水位。
3. 最后修正 SSE 与 optimistic message 的合流语义，补测试并完成 build。

## 进度

### R1 去掉原型标签并升级工作区壳层
- Context:
  - `App.tsx` 顶栏直接向用户展示 `P1-P7 Skeleton`，这是本 milestone 的头号问题。
- Decision:
  - 将顶栏改为正式产品品牌 + workspace 标题 + 商业化描述，不再暴露任何 skeleton 文案。
  - 同时更新 `chat-overview-page.tsx`，避免“initializing”式占位感。
- Rationale:
  - 壳层文案是所有用户第一眼可见区域，必须先去 prototype 痕迹。
- Evidence:
  - `src/IM/frontend/src/app/App.tsx`
  - `src/IM/frontend/src/features/chat/chat-overview-page.tsx`
  - `src/IM/frontend/src/app/router.test.tsx`

### R2 收口会话列表与工作区空态
- Context:
  - 旧版会话列表仍偏说明型 demo，空内容时缺乏真实 inbox 体验。
- Decision:
  - 为会话列表增加会话数、产品化描述、稳定 preview fallback、参与者摘要、空列表态。
  - 为 message pane 增加 workspace 空态与空会话态，替换原 `Select a conversation` 的原型式表达。
- Rationale:
  - M153 的重点是把 chat list/workspace 从原型提升到商业品质，先保证层级、空态、入口解释都稳定。
- Evidence:
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`

### R3 修复 self message / SSE 合流渲染错误
- Context:
  - 前端原实现对 `message.sent` / `message_created` 直接写死 `sender_type: user` 且 `is_mine: false`，会覆盖本地 optimistic message。
  - `message.delivered` 如果 payload 里已经有 `sender_type`，仍然会被误判为 relay synthetic agent message。
- Decision:
  - 在 `chat-workspace-page.tsx` 中新增 stream message builder，统一按 `selfUserId`、`sender_user_id`、`sender_type` 推导 `sender_name` / `is_mine` / `sender_type`。
  - 对 `message.delivered` 先处理“真实消息送达”分支；只有没有 `sender_type` 的事件才继续走 relay synthetic agent 分支。
  - `text_delta` 合流时保留既有附件，并沿用已存在消息的 sender 语义，避免把本端消息错误挪到对侧。
  - 新增测试，覆盖 optimistic self message 在 SSE 回流后仍保持本端展示。
- Rationale:
  - 现场“只看到一边消息”的观感，本质是前端 state reconciliation 把本端消息语义冲掉了；优先在前端修正即可。
- Evidence:
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`

### R4 测试与构建收口
- Tests:
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M153/src/IM/frontend" test -- --run src/app/router.test.tsx src/features/chat/chat-layout.test.tsx src/features/chat/chat-routes.test.tsx src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`
    - 结果：`5 passed`, `29 passed`
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M153/src/IM/frontend" run build`
    - 结果：success
- Additional note:
  - build 过程中暴露既有 mock 数据的 TypeScript 问题：`mock-chat-api.ts` 中 `last_message_at: null` 不符合当前 `ConversationSummary` 类型；已最小修复为 `undefined`，以恢复 frontend build 绿灯。

## 当前结论
- 用户可见原型标签已移除。
- 会话列表、workspace 空态、默认文案已收口到更接近商业产品的呈现。
- 前端已修复 self message 在 SSE 回流时被错误重绘为对侧消息的问题，并阻止带 `sender_type` 的 `message.delivered` 被误做 relay agent synthetic bubble。
- 前端相关测试与 build 已通过，可进入提交与后续合并审查阶段。
