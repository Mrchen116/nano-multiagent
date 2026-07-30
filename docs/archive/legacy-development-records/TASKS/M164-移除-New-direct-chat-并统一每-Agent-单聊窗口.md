# M164 Task — 移除 New direct chat 并统一每 Agent 单聊窗口

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M164`
- 已确认 branch：`milestone/M164`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 首轮阅读：
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - 参考：`TASKS/M142-聊天工作区指定-Agent-直聊与prompt冻结.md`
  - 参考：`TASKS/M150-修复 Agent 配置变更污染旧直聊会话.md`

## 目标
纠正 M142 引入的错误产品入口：聊天工作区移除 `New direct chat`，保留群聊创建；同一 Agent 的直聊改为复用一个稳定窗口，并让 Agent 创建/编辑后的开聊动作都复用该唯一单聊线程。

## 明确问题
1. `conversation-list.tsx` 仍暴露 `New direct chat` CTA，产品入口与当前要求冲突。
2. 聊天工作区仍保留“从 workspace 新建直聊”的完整面板与状态机，继续鼓励用户手工新建重复直聊。
3. 直聊复用虽然在 `createDirectConversation()` 内做了基本兜底，但缺少“重复直聊折叠/规范化”的明确语义与测试门禁。
4. Agent 设置侧缺少明确的“开聊”入口，无法承接“每 Agent 唯一直聊窗口”的产品路径。

## Scope
- 移除聊天工作区的 `New direct chat` CTA 与对应面板/状态流。
- 保留并验证 `Create group chat` 入口与群聊创建能力不受影响。
- 收敛前端直聊复用语义：同一 Agent 的重复直聊只暴露一个稳定入口，并复用 canonical 线程。
- 在 Agent 设置创建/编辑后的产品路径中提供可复用的开聊入口。
- 补齐聚焦测试，覆盖 CTA 移除、Agent 开聊入口、以及单线程复用语义。
- 更新 `TASKS/M164-*.md` 与 `PROGRESS/M164-*.md`，记录 Roadpoints、验证命令、提交点与回滚说明。

## 非目标
- 不修改 `data/dev-tasks.json`。
- 不新增后端 conversations API 路由。
- 不在本 milestone 内重做 Gateway / runtime prompt 冻结策略。
- 不补新的 Playwright 套件；本 milestone 先完成聚焦前端/接口回归与记录。

## Roadpoints

### R1. 移除 workspace 里的 New direct chat 产品入口
- Status: TODO
- Acceptance:
  - 聊天工作区不再显示 `New direct chat`。
  - `Create group chat` 入口与现有群聊面板继续可用。
  - 相关文案不再误导用户去 conversation list 手工新建多个直聊。
- Tests Plan:
  - `chat-workspace-page.test.ts`
  - `chat-layout.test.tsx`
- DoD:
  - `conversation-list.tsx` / `chat-workspace-page.tsx` / 相关 copy 与测试完成同步调整。

### R2. 收敛为每 Agent 唯一直聊窗口，并把开聊路径迁到 Agent 设置
- Status: TODO
- Acceptance:
  - 同一 Agent 的直聊打开逻辑复用 canonical conversation，而不是继续暴露重复线程。
  - Agent detail（承接 create/edit 后路径）提供 `Open direct chat` 入口并导航到复用线程。
- Tests Plan:
  - `im-chat-api.test.ts`
  - `agent-detail-page` 聚焦测试
- DoD:
  - 直聊复用语义有明确 helper / 断言；Agent 设置页能打开唯一单聊窗口。

### R3. 聚焦验证、记录与收口
- Status: TODO
- Acceptance:
  - 跑完聚焦前端测试与构建验证并记录结果。
  - PROGRESS 写清根因、修复点、验证结果、提交与回滚点。
- Tests Plan:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx`
  - 如新增独立测试文件则一并纳入同一命令
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M164/src/IM/frontend run build`
- DoD:
  - 分支可提交并给出是否 ready-to-merge 的明确结论。

## 回滚点
- 若需要回滚本 milestone，只需撤回：
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `src/IM/frontend/src/features/chat/mock-chat-api.ts`
  - `src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `TASKS/M164-移除-New-direct-chat-并统一每-Agent-单聊窗口.md`
  - `PROGRESS/M164-移除-New-direct-chat-并统一每-Agent-单聊窗口.md`
  - 以及本次构建产物更新（如有）

## 提交计划
- C1: docs/TDD 计划提交
- C2: 入口移除 + 单聊复用实现与测试提交
- C3: PROGRESS/验证收口提交（如需要）
