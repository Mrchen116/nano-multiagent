# bugfix-442-M1 进度

## 开工

- 已读 fix.md（现象/根因）、AGENTS.md、现有 chat v2 实时流代码与 integration 测试框架。
- 范围：`src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx`
  + `chat-workspace.integration.test.tsx`。
- 基线：integration 测试 17 passed（绿）。

### R1 — v2 侧边栏消费消息流 + 读后刷新

- Context: v2 聊天工作区的用户维流 `attachUserConversationStream.onEvent` 只处理
  node/agent status，不处理 message 事件；读消息也只刷新消息流。两处都不刷新会话
  列表 query `["chat-v2","conversations"]`，导致侧边栏未读/preview/时间/排序停在
  加载快照（fix.md 根因）。
- Decision: 两个触发点都补刷新会话列表，统一靠重拉拿后端真值（后端在收消息时已
  维护好 unread/preview/last_message_at，前端不维护乐观 unread）：
  1. `onEvent` 加分支：`message.sent` / `message_created` / `relay.completed` 事件
     → 250ms 去抖后 `invalidateQueries(["chat-v2","conversations"])`。判据沿用
     toast 模块 `buildNotificationCandidate` 认的同一组事件，保持架构一致。
  2. messagesQuery 成功后 effect（react-query v5 无 useQuery.onSuccess）→ 刷新会话
     列表，读后 unread 清零落地。
- Rationale: 用户维流覆盖所有会话，是驱动侧边栏的正确通道；与会话内 openChatStream
  （只更新打开会话气泡）正交。去抖避免群聊多 agent 同回合 message.delta 风暴下连续
  重拉。
- Evidence:
  - Tests: integration 红测先证缺失（2 failed），实现后 19 passed；全量前端
    `vitest run` 60 files / 487 tests 全绿，无回归。tsc --noEmit 绿。
  - Entry / Browser QA: 真栈 e2e（隔离 IM:54492 + Gateway 连真 LLM，playwright +
    chromium 走真实 UADirect chat），三阶段端到端：
    - PHASE1（会话内）：发消息→agent 回复 "你好，有什么可以帮你的吗？"，侧边栏 preview
      实时从自己的消息更新为 agent 回复。→ 症状②（preview 实时更新）
    - PHASE2（离开会话到 /chat）：第二轮 agent 回复 "好的，请说。"，侧边栏未读角标
      实时 1→2 + preview/时间更新。→ 症状①③（未读出现/增加、preview/时间）
    - PHASE3（点进读）：未读角标 2→清零。→ 症状⑤（读后清零）
    截图：A-in-conv-preview.png / B-unread-badge.png（角标=2 + preview="好的，请说。"）/
    C-after-read.png（角标消失）。修前症状由用户报告截图证实；修后三症状全部不复现。
  - Frontend State Matrix: 有未读/无未读、收到新消息(未打开/正打开)三态真栈覆盖；
    empty/loading/error/viewport/dark 本 fix 不改，N/A。
  - E2E/Regression: `chat-workspace.integration.test.tsx` 两条新 regression（消息事件
    刷新 + 读后刷新），落库。排序④由"重拉整列表 + 后端 order by last_message_at"机制
    保证，单会话场景不单独断言。
  - Visual/Interaction: 见上述截图，viewport 1280x800。
- Rollback: 回退到本 milestone 分支 C2 之前（C1 仅测试）。
- Commits: C1=red test, C2=fix, C3=本次 docs。
- Next: 本 milestone 已完成，回填 fix.md 后集成到 unit 分支。
