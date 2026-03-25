# M317 Fix stale unread badge after opening direct chat

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M317`，并将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- 基线命令：`cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts`
- 基线结果：存在 2 个既有失败（与 M317 无关）：
  - `chat workspace relay event mapping > uses per-agent identity to keep same-turn multi-agent relay replies distinct`
  - `chat workspace page > keeps same-turn group replies from multiple agents visible instead of collapsing them`

### R1.1 Unread clear semantics align on open conversation
- Context: 待补充
- Decision: 待补充
- Rationale: 待补充
- Evidence:
  - Tests: 待补充
  - Entry: 待补充
- Rollback: 待补充
- Commits: C1=``, C2=``, C3=``
- Next: 先补 stale-badge 回归测试，再对齐前后端 unread 语义。
