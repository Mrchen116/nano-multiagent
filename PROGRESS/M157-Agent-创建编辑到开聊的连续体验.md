# M157 Progress — Agent 创建编辑到开聊的连续体验

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M157`
- 已确认 branch：`milestone/M157`
- 已确认约束：仅在该 worktree 实施；不修改 `data/dev-tasks.json`
- 首轮阅读文件：
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
  - `src/IM/frontend/src/app/router.test.tsx`
  - 参考：`TASKS/M164-移除-New-direct-chat-并统一每-Agent-单聊窗口.md`

## 初始根因判断
- `M164` 已移除 workspace 新建 direct chat 入口，但 create success 仍只会回到 detail，缺少“立刻开聊”的强承接动作。
- detail 页虽然已有 `Open direct chat`，但没有足够清楚地解释这是“同一个稳定线程”，也没有解释旧消息与新配置在同一线程中的关系。
- Agents 列表与 Conversations 列表文案对“每 Agent 一个可复用 direct chat”表达还不够直接，新创建 Agent 的后续去向不够明显。

## 执行策略
1. 在 create 成功反馈区补 `Open direct chat` 与稳定线程说明。
2. 在 detail 页侧栏加入 `Start chatting now` 模块，解释同线程复用与 old/new behavior 边界。
3. 在 Agents / Conversations 入口补足可发现性文案。
4. 用前端测试锁定连续体验路径，并更新记录。

## 进度

### R1 收口 create/edit 的立即开聊路径
- Decision:
  - `agent-create-page.tsx` 在创建成功后保留 detail 跳转，同时展示成功说明与 `Open direct chat` CTA，显式说明“每 Agent 一个稳定可复用 direct chat”。
  - `agent-detail-page.tsx` 新增 `Start chatting now` 信息块，解释：开聊会复用同一线程；旧消息留在同一会话；保存后的新行为也在同一线程继续生效。
- Evidence:
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
- Status: DONE

### R2 提升新 Agent 的聊天可发现性
- Decision:
  - `conversation-list.tsx` 改成强调 reusable direct chat，而不是笼统 direct chats。
  - `agents-list-page.tsx` 在列表项中补“Stable direct chat / Open detail to continue in the same reusable direct chat”提示，缩短从 create/edit 到 chat workspace 的理解路径。
  - `chat-layout.test.tsx` 与 `router.test.tsx` 同步锁定新的产品文案，不允许回归出旧语义。
- Evidence:
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
  - `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
  - `src/IM/frontend/src/app/router.test.tsx`
- Status: DONE

### R3 验证、记录与收口
- Tests:
  - 首次执行 `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M157/src/IM/frontend test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts src/features/chat/im-chat-api.test.ts src/app/router.test.tsx`
    - 结果：失败，`sh: vitest: command not found`
  - 执行 `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M157/src/IM/frontend install`
    - 结果：成功，`added 253 packages, and audited 254 packages in 2s`
  - 再次执行同一条测试命令
    - 结果：成功，`7 passed files / 48 passed tests`
  - 执行 `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M157/src/IM/frontend run build`
    - 结果：成功，产出 `dist/index.html`、`dist/assets/index-B_BF_QeE.css`、`dist/assets/index-B2O-HcPw.js`
- Verification notes:
  - `agent-create.test.tsx` 已锁定：创建成功后会给出明确的 direct-chat 连续动作与稳定线程说明。
  - `agent-detail-page.test.tsx` 已锁定：编辑页明确解释同线程复用、旧消息与新配置关系，并可直接开聊。
  - `chat-layout.test.tsx`、`chat-workspace-page.test.ts`、`router.test.tsx` 已锁定：chat workspace 文案强调 reusable direct chat，且没有回归出 New direct chat 语义。
- Status: DONE

## 当前结论
- create/edit 已被收口到更清晰的“现在就开聊”路径。
- 文案层面已明确：每个 Agent 只有一个稳定可复用 direct chat，不存在新 direct chat 入口。
- 聚焦前端测试与构建均已通过；当前实现达到 ready-to-merge 状态。

## 相关验证命令
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M157/src/IM/frontend install`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M157/src/IM/frontend test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts src/features/chat/im-chat-api.test.ts src/app/router.test.tsx`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M157/src/IM/frontend run build`
- 2026-03-14 rerun: focused Vitest suite passed again (`7 passed files / 48 passed tests`).
- 2026-03-14 rerun: frontend build passed again and produced `dist/index.html`, `dist/assets/index-B_BF_QeE.css`, `dist/assets/index-B2O-HcPw.js`.
