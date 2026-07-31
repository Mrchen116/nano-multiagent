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
  - `conversation-list.tsx` 与 `chat-workspace-page.tsx` 仍保留 workspace 级直聊创建流，继续把“新建直聊”当成聊天工作区主入口。
- Decision:
  - 删除 `ConversationList` 的 `onCreateDirectChat` 能力与 `New direct chat` 按钮。
  - 移除 `chat-workspace-page.tsx` 中整套 direct-chat panel / query / mutation / 状态机，只保留群聊创建路径。
  - 同步修正空态与 starter card 文案，不再暗示用户从 conversation list 手工新建多个 Agent 直聊。
- Rationale:
  - 产品要求已经从“可新建指定 Agent 直聊”切回“每 Agent 唯一单聊窗口”；最小正确修复就是删掉错误入口，而不是继续优化它。
- Evidence:
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
  - `src/IM/frontend/src/app/router.test.tsx`
- Status: DONE

### R2 收敛每 Agent 唯一直聊窗口，并迁移开聊路径到 Agent 设置
- Context:
  - 现有 `createDirectConversation()` 只是在“没有现存直聊时”创建新线程，但对同一 Agent 的重复直聊缺少 canonical 选择规则，且设置页没有稳定开聊入口。
- Decision:
  - 在 `im-chat-api.ts` 引入 `pickCanonicalDirectConversation()`，对同 participant pair 的 direct conversation 统一选择最早创建的线程作为 canonical 直聊窗口。
  - 让 `findStarterConversation()`、`listDiscoverableAgents()`、`createDirectConversation()` 都复用这一 canonical helper，避免重复直聊语义继续扩散。
  - 在 `agent-detail-page.tsx` 新增 `Open direct chat` 按钮，通过 `createDirectConversation({ agentId })` 打开或复用该 Agent 的唯一单聊窗口。
  - 新增 `agent-detail-page.test.tsx`，锁定设置页开聊入口与导航行为。
- Rationale:
  - 不新增后端 API 的前提下，前端可先把“同一 Agent 只认一个 canonical 直聊窗口”收敛成稳定语义，并把产品入口迁到 Agent 设置，满足 create/edit 后复用单聊路径的要求。
- Evidence:
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
- Status: DONE

### R3 聚焦验证、记录与收口
- Tests:
  - 首次执行 `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agent-detail-page.test.tsx`
    - 结果：失败，报错 `sh: vitest: command not found`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend install`
    - 结果：`added 253 packages, and audited 254 packages in 2s`
  - 再次执行 `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agent-detail-page.test.tsx`
    - 结果：`6 passed files / 39 passed tests`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend run build`
    - 结果：成功，产出 `dist/index.html`、`dist/assets/index-CASU4UjZ.css`、`dist/assets/index-QMmm6Xkh.js`
- Verification notes:
  - `chat-workspace-page.test.ts` 已锁定：workspace 不再显示 `New direct chat`，同时保留 `Create group chat`。
  - `im-chat-api.test.ts` 已锁定：同一 Agent 的重复直聊按 canonical 线程复用，而不是任意挑选或继续鼓励新开。
  - `agent-detail-page.test.tsx` 已锁定：设置页存在 `Open direct chat` 并导航到复用线程。
  - 本次未新增后端 API；直聊唯一窗口语义通过前端 canonical 选择与设置页统一入口完成收敛。
- Commits:
  - C1=`dc65fe1` `docs(M164): outline single-thread direct chat plan`
  - C2=`2d6dd78` `fix(M164): remove workspace direct chat entry`
  - C3=`<pending>`
- Status: DONE

## 回滚点
- 若需回滚本 milestone，只需撤回以下文件：
  - `src/IM/frontend/src/app/router.test.tsx`
  - `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `src/IM/frontend/src/features/chat/mock-chat-api.ts`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
  - `src/IM/frontend/dist/index.html`
  - `src/IM/frontend/dist/assets/*`
  - `TASKS/M164-移除-New-direct-chat-并统一每-Agent-单聊窗口.md`
  - `PROGRESS/M164-移除-New-direct-chat-并统一每-Agent-单聊窗口.md`

## 当前结论
- 聊天工作区已移除 `New direct chat`，错误产品流不再出现；群聊创建入口继续保留。
- 同一 Agent 的直聊打开逻辑已收敛为 canonical 单线程复用，设置页提供了稳定的 `Open direct chat` 入口承接 create/edit 后开聊路径。
- 聚焦前端测试与构建验证已通过；当前分支处于可继续收尾提交的状态。

## 待办
- 提交本次 PROGRESS 最终更新，并确认 worktree 是否清洁、是否 ready to merge。

## M146 / M104 复验提示
- 按 milestone 要求，合并到 `main` 后仍需将本修复纳入 M146 / M104 产品复验，重点确认：
  - 聊天工作区没有回归出 `New direct chat`；
  - Agent 创建/编辑后进入的是唯一单聊窗口；
  - 群聊能力与真实浏览器路径不受本次入口删除影响。

## 相关验证命令
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend install`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agent-detail-page.test.tsx`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend run build`
