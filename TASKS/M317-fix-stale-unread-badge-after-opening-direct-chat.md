# M317 Fix stale unread badge after opening direct chat

## Context
- Milestone: `M317`
- Goal: 修复会话已打开并看过最新消息后，左侧会话列表未读角标（如 `8 new`）仍残留且刷新后复现的问题。
- Scope: `src/IM/frontend/src/features/chat/`, `src/IM/api/routes/messages.py`, `src/IM/application/web_im_service.py`, `src/IM/infra/repositories.py`

## Roadpoints

### R1 Unread clear semantics align on open conversation
- Status: TODO
- Acceptance:
  - 打开并加载目标会话后，左栏对应会话未读角标立即清零。
  - 页面刷新后，同一会话未读角标仍保持清零（后端状态持久化）。
  - 前端 unread 语义与后端 `unread_count` 对齐，不再用“历史非本人消息数”替代。
  - 在既有 `chat-workspace-page.test.ts` 增加回归测试覆盖 stale-badge 场景。
- Tests Plan:
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 增补“打开会话后角标清零并刷新保持清零”的回归用例（先红后绿）。
  - 运行 `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts`。
- DoD:
  - C1/C2/C3 三提交完成。
  - 新增回归测试可稳定复现并在实现后通过。
  - `TASKS`/`PROGRESS` 与 `data/dev-tasks.json` 状态同步。
