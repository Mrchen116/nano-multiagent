# M164 Progress — 移除 New direct chat 并统一每 Agent 单聊窗口

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M164`
- 已确认 branch：`milestone/M164`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 首轮阅读文件：
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`

## 初始根因判断
- `New direct chat` 入口是 M142 为“指定 Agent 新开直聊”引入的产品流，但当前产品要求已明确回滚：群聊能力保留，不应再暴露独立的“新建直聊”入口。
- 当前 workspace 仍保留一整套 direct-chat 面板与文案，继续引导用户从聊天工作区手工创建新直聊，与“每 Agent 唯一直聊窗口”目标冲突。
- 现有 `createDirectConversation()` 虽然在同 participant pair 下会优先复用已有 conversation，但缺少更明确的 canonical 选择与上层产品入口约束；重复直聊一旦存在，workspace 仍可能继续暴露重复语义。
- Agent 设置页缺少明确开聊 CTA，导致移除 workspace 直聊入口后，需要新的稳定入口承接 create/edit 后的开聊场景。

## 执行策略
1. 先补 `TASKS/M164` 与 `PROGRESS/M164`，明确 Roadpoints、验证命令与回滚边界。
2. 再删掉 workspace 里的 `New direct chat` 入口与相关状态机，同时同步修正文案。
3. 然后收敛直聊 canonical 复用语义，并在 Agent detail 上补 `Open direct chat` 入口承接 create/edit 路径。
4. 最后跑聚焦前端验证，更新 PROGRESS、提交点与 ready-to-merge 结论。

## 进度

### R1 移除 workspace 里的 New direct chat 产品入口
- Context:
  - 待执行。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - 待执行。
- Status: TODO

### R2 收敛每 Agent 唯一直聊窗口，并迁移开聊路径到 Agent 设置
- Context:
  - 待执行。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - 待执行。
- Status: TODO

### R3 聚焦验证、记录与收口
- Tests:
  - 待执行。
- Verification notes:
  - 待执行。
- Commits:
  - C1=`<pending>`
  - C2=`<pending>`
  - C3=`<pending>`
- Status: TODO
