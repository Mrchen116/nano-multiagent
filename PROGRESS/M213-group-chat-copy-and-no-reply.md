# M213 群聊文案与 NO_REPLY 收口进展

## Milestone summary
- Goal: 修复真实群聊 NO_REPLY 对普通用户的可见残留，并把群聊线程与 mention picker 收口为产品化文案。
- Scope: 仅修改前端聊天相关代码、测试，以及本 milestone 的 TASKS/PROGRESS 记录。
- Non-goals: 不做产品验收，不修改 `data/dev-tasks.json`，不触碰 acceptance 脚本。

### R1 群聊线程与列表隐藏 NO_REPLY 内部态
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M213/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build`
  - Entry: 群聊 SSE 事件不再向线程/预览注入 NO_REPLY 内部态。
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 mention picker 与群聊可见文案产品化
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M213/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build`
  - Entry: picker 与群聊头部仅显示产品化名称/文案，发送 payload 仍保留稳定 token。
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
