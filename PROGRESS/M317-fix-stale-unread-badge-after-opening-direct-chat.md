# M317 Fix stale unread badge after opening direct chat

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M317`，并将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- 基线命令：`cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts`
- 基线结果：存在 2 个既有失败（与 M317 无关）：
  - `chat workspace relay event mapping > uses per-agent identity to keep same-turn multi-agent relay replies distinct`
  - `chat workspace page > keeps same-turn group replies from multiple agents visible instead of collapsing them`

### R1.1 Unread clear semantics align on open conversation
- Context: 前端 `chat-workspace-page` 在进入会话后不会清零当前会话的 sidebar `unread_count`；`im-chat-api.listConversations` 还用“历史非本人消息数”推导未读，导致刷新后仍可能显示 `8 new`。
- Decision:
  - `ChatWorkspacePage` 在 `conversationId` 激活时，立即将当前会话在 React Query `["chat","conversations"]` 缓存中的 `unread_count` 置 0。
  - 后端 `GET /im/v1/conversations/{id}/messages` 新增 `mark_as_read` 查询参数；当 `mark_as_read=true` 且读取最新页时，将该会话 `unread_count` 持久化清零。
  - `im-chat-api.getConversation` 读取会话详情时带上 `mark_as_read=true`，实现“打开并查看最新消息即已读”。
  - `im-chat-api.toConversationSummary` 改为直接信任后端 `conversation.unread_count`，不再用本地消息列表推导未读。
- Rationale: 让 unread 状态单一来源回到后端持久化字段，并用前端缓存即时清零避免用户可见闪烁/残留，确保刷新后语义稳定。
- Evidence:
  - Tests: `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts`（新增 stale-badge 回归用例通过；该文件仍有 2 个基线既有失败，均与 M317 无关）
  - Tests: `pytest tests/im_service/integration/test_messages_api.py -k mark_as_read`（1 passed）
  - Entry: `chat-workspace-page` 回归用例验证“打开会话后角标即时清零 + 重载后保持清零”。
- Rollback: 回退到 `e49b24e` 可撤销实现，仅保留 C1 红测。
- Commits: C1=`e49b24e`, C2=`703fccc`, C3=`(this commit)`
- Next: 推送 C3 与 dev-tasks DONE 状态，交付 milestone M317。
