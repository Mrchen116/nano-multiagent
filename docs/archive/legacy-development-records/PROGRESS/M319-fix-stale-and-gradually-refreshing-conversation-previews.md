# M319 Fix stale and gradually-refreshing conversation previews

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M319`。
- 已将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- 基线命令：`cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx`
- 基线结果：存在 2 个既有失败（与 M319 目标无关）：
  - `chat workspace relay event mapping > uses per-agent identity to keep same-turn multi-agent relay replies distinct`
  - `chat workspace page > keeps same-turn group replies from multiple agents visible instead of collapsing them`

### R1.1 Preview state source-of-truth alignment
- Context: 会话列表预览在打开会话后会停留旧文案，且 `text_delta` 事件使用“旧预览 + delta”拼接，导致可见的逐步追平抖动；预览快照仅在 API 层更新，工作区 SSE 更新路径未同步快照。
- Decision:
  - 在 `ChatWorkspacePage` 增加统一的预览同步函数：每次消息事件后都从会话详情缓存的“最新消息”推导 sidebar 预览，而不是拼接旧 sidebar 文案。
  - 在会话详情加载成功后，立即把最新消息同步到 sidebar 与 preview snapshot，确保打开会话即可对齐最新预览。
  - 导出 `setConversationPreviewSnapshot`，让工作区事件路径与 `ConversationList` 快照读取保持一致数据源。
  - 回归测试补充“stale preview + text_delta 抖动”场景，并更新 NO_REPLY 场景断言以匹配“详情为权威”语义。
- Rationale: 预览应当由“当前会话真实最新消息”单一来源驱动；只要消除对旧 sidebar 文案的增量拼接和跨路径不同步，就能根治“打开后慢慢追平”的表现。
- Evidence:
  - Tests: `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts -t "stale-prefix catch-up"`（通过）
  - Tests: `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx`（新增用例通过；保留 2 个既有无关失败）
  - Entry: 新增 `chat workspace page > keeps sidebar preview aligned to latest detail and avoids stale-prefix catch-up during text deltas` 证明打开会话后预览立即对齐且不再出现旧前缀追平。
- Rollback: 回退到 `b995fea` 可撤销实现，仅保留 C1 红测提交。
- Commits: C1=`b995fea`, C2=`419b46d`, C3=`(this commit)`
- Next: 更新 `data/dev-tasks.json` 里 M319 为 DONE 并附结果摘要。
