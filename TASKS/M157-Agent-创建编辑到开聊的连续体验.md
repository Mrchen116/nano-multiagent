# M157 Task — Agent 创建编辑到开聊的连续体验

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M157`
- 已确认 branch：`milestone/M157`
- 已确认约束：仅在该 worktree 实施；不修改 `data/dev-tasks.json`
- 复用前序里程碑背景：`M164` 已移除 workspace 级 `New direct chat` 入口，因此本 milestone 聚焦把 Agent create/edit 明确收口到“现在就开聊”的稳定产品路径。

## 目标
把 Agent 创建/编辑后的主动作收敛为“立即进入该 Agent 的稳定直聊窗口”，并在 Settings 与 Chat workspace 中清楚解释：每个 Agent 只有一个可复用 direct chat，不存在新的 direct chat 产品入口。

## 明确问题
1. Agent create 成功后只跳转 detail，缺少明确的立即开聊承接。
2. Agent detail 虽有 `Open direct chat`，但缺少足够明显的“现在就开聊”说明，以及旧消息/新配置如何在同一线程中共存的解释。
3. Agents 列表对“新建后去哪里继续聊”缺少可发现性提示，新 Agent 在聊天工作区的发现链路不够顺。
4. 需要测试锁定连续体验路径，避免回归出“新 direct chat”语义。

## Roadpoints

### R1. 收口 create/edit 的立即开聊路径
- Status: DONE
- Acceptance:
  - 创建成功后出现明确的 `Open direct chat` 后续动作。
  - 编辑页侧栏清楚提示“Start chatting now”。
  - 文案明确 direct chat 是稳定复用线程，而不是新建直聊。
- Tests Plan:
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`

### R2. 提升新 Agent 在聊天工作区/设置侧的可发现性
- Status: DONE
- Acceptance:
  - Conversations 文案强调每个 Agent 的 reusable direct chat。
  - Agents 列表明确提示从 detail 继续进入同一条直聊。
  - 不重新引入 `New direct chat` 语义。
- Tests Plan:
  - `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
  - `src/IM/frontend/src/app/router.test.tsx`

### R3. 验证、记录与收口
- Status: DONE
- Acceptance:
  - 跑完聚焦前端测试。
  - 更新 TASKS/PROGRESS，给出 merge readiness。
- Tests Plan:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M157/src/IM/frontend test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts src/features/chat/im-chat-api.test.ts src/app/router.test.tsx`

## 回滚点
- `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
- `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
- `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
- `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
- `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
- `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
- `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
- `src/IM/frontend/src/app/router.test.tsx`
- `PROGRESS/M157-Agent-创建编辑到开聊的连续体验.md`
